import os 
import re

from dataclasses import dataclass
from typing import Iterable, Dict, List, Tuple
from collections import defaultdict
from datetime import datetime

import matplotlib.pyplot as plt
import requests


FHIR_BASE = os.getenv("FHIR_BASE", "http://localhost:8080/fhir")


def fhir_get(path, params=None):
    """
    Retrieve a FHIR resource or search bundle via HTTP GET.

    Parameters
    ----------
    path : str
        Either a full URL or a relative FHIR path (e.g., 'Patient', 'Observation/123').
    params : dict, optional
        Query parameters to include in the GET request, such as `_count`, `code`, or `category`.

    Returns
    -------
    dict
        Parsed JSON response from the FHIR server.

    Raises
    ------
    requests.HTTPError
        If the request fails with a non-2xx HTTP status.
    """
    url = path if path.startswith("http") else f"{FHIR_BASE.rstrip('/')}/{path.lstrip('/')}"
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


# Optional but recommended for robust ISO parsing (handles timezone/no-T)
try:
    from dateutil import parser as dtparser
except Exception:
    dtparser = None


@dataclass(frozen=True)
class SeriesSpec:
    """Definition of a single series to plot."""
    code: str
    label: str | None = None
    unit_hint: str | None = None  # optional unit hint from your chartable list


def _parse_when(obs: dict) -> datetime | None:
    """Parse effective/issued into a datetime, robustly."""
    t = obs.get("effectiveDateTime") or obs.get("issued")
    if not t:
        return None
    try:
        if dtparser:
            return dtparser.parse(t)
        # minimal fallback: accept 'Z' or with offset
        return datetime.fromisoformat(t.replace("Z", "+00:00"))
    except Exception:
        return None




def _safe_filename(name: str) -> str:
    """
    Make a filesystem-safe filename from a chart title.

    - Replaces path separators (/ and \) with underscores
    - Keeps alnum, space, dash, underscore, dot, parentheses, plus, and hash
    - Collapses multiple underscores
    - Strips leading/trailing whitespace/underscores
    """
    # Replace path separators explicitly
    name = name.replace(os.sep, "_")
    if os.altsep:
        name = name.replace(os.altsep, "_")
    # Whitelist
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_.()+#")
    cleaned = "".join(ch if ch in allowed else "_" for ch in name)
    # Collapse runs of underscores/spaces and trim
    cleaned = re.sub(r"[ _]+", "_", cleaned).strip(" _")
    return cleaned or "chart"


def fetch_timeseries_for_codes(pid: str,
                               codes: Iterable[str],
                               page_size: int = 200,
                               since: str | None = None,
                               until: str | None = None) -> Dict[str, List[Tuple[datetime, float, str]]]:
    """
    Fetch numeric Observation points (valueQuantity) for a patient and a set of LOINC codes.

    Parameters
    ----------
    pid : str
        Patient id, with or without 'Patient/' prefix.
    codes : iterable of str
        LOINC codes to fetch; both top-level Observation.valueQuantity and
        component.valueQuantity are collected.
    page_size : int, default=200
        Page size for Observation search.
    since, until : str or None
        Optional ISO 8601 bounds, applied to Observation 'date' search param.

    Returns
    -------
    dict
        Mapping: code -> list of tuples (dt, value, unit_string)

    Notes
    -----
    - Uses `_elements` projection to keep payload light.
    - Token filters are fully-qualified for LOINC (system+code).
    """
    patient_ref = pid if str(pid).startswith("Patient/") else f"Patient/{pid}"
    code_tokens = ",".join([f"http://loinc.org|{c}" for c in set(codes)])

    fields = "id,code,subject,effectiveDateTime,issued,valueQuantity,component"
    base_q = [f"patient={patient_ref}", f"_count={page_size}", f"_elements={fields}", f"code={code_tokens}"]
    if since:
        base_q.append(f"date=ge{since}")
    if until:
        base_q.append(f"date=le{until}")
    url = f"Observation?{'&'.join(base_q)}"

    out: Dict[str, List[Tuple[datetime, float, str]]] = defaultdict(list)
    while True:
        bundle = fhir_get(url, params={})
        for e in bundle.get("entry", []):
            o = e.get("resource", {})
            dt = _parse_when(o)
            if not dt:
                continue

            # top-level numeric value
            vq = o.get("valueQuantity")
            if vq is not None and "value" in vq:
                cc = (o.get("code", {}).get("coding") or [{}])[0]
                ccode = cc.get("code")
                if ccode in codes:
                    unit = vq.get("unit") or vq.get("code") or ""
                    out[ccode].append((dt, float(vq["value"]), unit))

            # component numeric values
            for comp in o.get("component", []):
                vqc = comp.get("valueQuantity")
                if vqc is None or "value" not in vqc:
                    continue
                cc = (comp.get("code", {}).get("coding") or [{}])[0]
                ccode = cc.get("code")
                if ccode in codes:
                    unit = vqc.get("unit") or vqc.get("code") or ""
                    out[ccode].append((dt, float(vqc["value"]), unit))

        nxt = next((l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"), None)
        if not nxt:
            break
        url = nxt  # absolute next link; params must be None/empty in fhir_get

    # sort each series by time
    for c in list(out.keys()):
        out[c].sort(key=lambda t: t[0])

    return out


def render_groups_to_png(pid: str,
                         groups: Dict[str, List[dict]],
                         out_dir: str = "./charts",
                         since: str | None = None,
                         until: str | None = None,
                         dpi: int = 120) -> Dict[str, str]:
    """
    Render one PNG per chart group (single axes/figure, multiple lines allowed).

    Parameters
    ----------
    pid : str
        Patient id (with or without 'Patient/' prefix).
    groups : dict
        Mapping: chart title -> list of series dicts; each series dict
        should contain keys 'code', and optionally 'label' and 'units' (list).
        (Compatible with the output of `group_chartables(...)`.)
    out_dir : str, default="./charts"
        Directory to write PNG files into. Created if missing.
    since, until : str or None
        Optional ISO bounds to restrict fetched Observations.
    dpi : int, default=120
        PNG resolution.

    Returns
    -------
    dict
        Mapping: chart title -> PNG filepath
    """
    os.makedirs(out_dir, exist_ok=True)

    # 1) Collect all codes we need to fetch
    needed_codes = set()
    series_meta: Dict[str, SeriesSpec] = {}
    for title, series_list in groups.items():
        for s in series_list:
            code = s["code"]
            label = s.get("label")
            unit_hint = (s.get("units") or [None])[0]
            series_meta[code] = SeriesSpec(code=code, label=label, unit_hint=unit_hint)
            needed_codes.add(code)

    # 2) Fetch all time-series points for the union of codes
    data_by_code = fetch_timeseries_for_codes(pid, needed_codes, since=since, until=until)

    # 3) Render each chart group
    paths: Dict[str, str] = {}
    for title, series_list in groups.items():
        # prepare the figure (single axes)
        fig, ax = plt.subplots(figsize=(8, 4.5))  # one chart per figure; no subplots

        plotted_any = False
        legend_labels = []

        for s in series_list:
            code = s["code"]
            meta = series_meta[code]
            rows = data_by_code.get(code, [])
            if not rows:
                continue

            xs = [dt for dt, _, _ in rows]
            ys = [val for _, val, _ in rows]

            # Choose a series label: prefer human label; else fall back to code
            ser_label = meta.label or f"LOINC {code}"

            # Plot (no explicit colors/styles)
            ax.plot(xs, ys, marker="o", linewidth=1.5, markersize=3, label=ser_label)
            plotted_any = True
            legend_labels.append(ser_label)

        # If nothing plotted, skip file
        if not plotted_any:
            plt.close(fig)
            continue

        # Titles & axes
        ax.set_title(title)
        ax.set_xlabel("Date")
        ax.set_ylabel("Value")
        ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)

        # Legend only if multiple series present
        if len(legend_labels) > 1:
            ax.legend(loc="best", frameon=False)

        fig.autofmt_xdate()  # readable datetime ticks

        # Save
        fname = _safe_filename(title) or "chart"
        path = os.path.join(out_dir, f"{fname}.png")
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        paths[title] = path

    return paths

