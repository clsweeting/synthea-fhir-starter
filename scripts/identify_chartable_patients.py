import os

from collections import defaultdict, Counter
from datetime import datetime

import requests

FHIR_BASE = os.getenv("FHIR_BASE", "http://localhost:8080/fhir")

# Friendly names -> LOINC codes or categories
SIGNAL_MAP = {
    # Blood Pressure panel (SBP/DBP in components)
    "bp_panel": {"codes": ["85354-9", "55284-4"]},           # BP panel LOINC codes
    # Individual vitals/labs
    "sbp":      {"codes": ["8480-6"]},                        # Systolic BP
    "dbp":      {"codes": ["8462-4"]},                        # Diastolic BP
    "hr":       {"codes": ["8867-4"]},                        # Heart rate
    "bmi":      {"codes": ["39156-5"]},                       # BMI
    "chol":     {"codes": ["2093-3"]},                        # Total cholesterol
    "hdl":      {"codes": ["2085-9"]},
    "ldl":      {"codes": ["13457-7"]},
    "tg":       {"codes": ["2571-8"]},                        # Triglycerides
    "a1c":      {"codes": ["4548-4"]},                        # HbA1c
    "glucose":  {"codes": ["2339-0"]},                        # Glucose (serum)
    # Category shortcuts
    "vitals":   {"category": "vital-signs"},
}


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


def list_patients(count=50):
    """
    Yield basic patient records from the FHIR server.

    Parameters
    ----------
    count : int, default=50
        Maximum number of Patient resources to request from the server.

    Yields
    ------
    tuple[str, dict]
        The patient ID and the full Patient resource JSON for each patient.

    Notes
    -----
    This function uses the `fhir_get` helper to request a paginated
    `/Patient?_count={count}` search bundle and yields each resource entry.
    """
    bundle = fhir_get("Patient", params={"_count": count})
    for entry in bundle.get("entry", []):
        resource = entry["resource"]
        yield resource["id"], resource



def get_observation_categories_for_patient(pid, count=1000):
    """
    Retrieve all unique Observation categories available for a given patient.

    Parameters
    ----------
    pid : str
        The patient ID (e.g., "12345") for which to list Observation categories.
    count : int, default=1000
        Maximum number of Observation resources to inspect before stopping.

    Returns
    -------
    set of str
        A set of category codes found among the patient's Observation resources.
        Each code corresponds to `Observation.category.coding[*].code` or
        `Observation.category.text` if no code is available.

    Notes
    -----
    - This function performs a search on `/Observation?patient={pid}` and follows
      pagination links until either all results are retrieved or `count` is reached.
    - FHIR allows multiple categories per Observation; this function collects them all.
    - The categories often correspond to high-level groupings such as
      `"vital-signs"`, `"laboratory"`, `"imaging"`, `"exam"`, or `"survey"`.

    Examples
    --------
    >>> list_observation_categories("12345")
    {'vital-signs', 'laboratory', 'social-history'}
    """
    out = []
    url = "Observation"
    params = {"patient": pid, "_count": 200}
    while True:
        js = fhir_get(url, params=params)
        out.extend([e["resource"] for e in js.get("entry", [])])
        nxt = next((link["url"] for link in js.get("link", []) if link["relation"] == "next"), None)
        if not nxt or len(out) >= count:
            break
        url, params = nxt, None

    cats = set()
    for obs in out:
        for cat in obs.get("category", []):
            coding = cat.get("coding", [])
            for c in coding:
                if code := c.get("code"):
                    cats.add(code)
            if not coding and (txt := cat.get("text")):
                cats.add(txt)
    return cats


def get_observations_for_patient(pid, codes=None, category=None, count=2000):
    """
    Retrieve Observation resources for a given patient from a FHIR server.

    Parameters
    ----------
    pid : str
        The patient ID (e.g., "12345") for which to retrieve observations.
    codes : list of str, optional
        A list of LOINC or other Observation codes to filter results by.
        Example: ["2093-3", "2085-9"] for cholesterol panels.
        If omitted, all observation types for the patient are returned.
    category : str, optional
        FHIR Observation category, such as "vital-signs", "laboratory",
        or "survey". If provided, limits the search to that category.
    count : int, default=2000
        Maximum number of Observation resources to retrieve before stopping.

    Returns
    -------
    list of dict
        A list of FHIR Observation resources in JSON form. Each entry is a
        parsed dictionary corresponding to a single Observation resource.

    Notes
    -----
    - Uses the FHIR `Observation` search endpoint with pagination support.
      Automatically follows any `link.relation == "next"` pages until either
      all pages are retrieved or the specified `count` limit is reached.
    - The query parameters `_count`, `patient`, `code`, and `category`
      are passed to the FHIR API according to the FHIR R4 RESTful search
      specification.
    - This function relies on the `fhir_get` helper, which performs the
      actual HTTP GET requests and returns parsed JSON responses.

    Examples
    --------
    >>> observations = get_observations_for_patient("12345",
    ...     codes=["85354-9"], category="vital-signs", count=500)
    >>> len(observations)
    120
    >>> observations[0]["resourceType"]
    'Observation'
    """
    params = {"patient": pid, "_count": 200}
    if codes:
        params["code"] = ",".join(codes)
    if category:
        params["category"] = category
    out = []
    url = "Observation"
    while True:
        js = fhir_get(url, params=params)
        out.extend([e["resource"] for e in js.get("entry", [])])
        nxt = next((l["url"] for l in js.get("link", []) if l["relation"] == "next"), None)
        if not nxt or len(out) >= count:
            break
        url, params = nxt, None  # follow absolute next link
    return out



def get_observation_counts_for_patient(pid: str,
                                       sample: int = 2000,
                                       page_size: int = 200,
                                       since: str | None = None,
                                       until: str | None = None) -> dict[str, int]:
    """
    Count Observation resources per Category for a given patient.  Note however that categories
    are still quite broad (e.g. "vital-signs", "laboratory", "imaging", etc).
    See also get_observation_codes_per_patient() for a more granular breakdown by LOINC code.

    Parameters
    ----------
    pid : str
        Patient ID (e.g., "12345"). Accepts with or without the "Patient/" prefix.
    sample : int, default=2000
        Maximum number of Observation resources to scan before stopping. Acts as a
        performance guardrail. Set higher to approach a full count.
    page_size : int, default=200
        Number of Observation resources to request per page.
    since : str or None, default=None
        Optional lower bound on Observation date (ISO 8601). Applies as `date=ge{since}`.
    until : str or None, default=None
        Optional upper bound on Observation date (ISO 8601). Applies as `date=le{until}`.

    Returns
    -------
    dict[str, int]
        Mapping from category token to count, e.g.
        `{"vital-signs": 128, "laboratory": 412, "imaging": 9}`.

    Notes
    -----
    - Uses `_elements=category` to minimize payload (avoids `_summary=data` quirks).
    - An Observation can have multiple categories; each category is counted.
    - If a category has no `coding.code`, falls back to `category.text`.
    - For an exact total regardless of volume, either:
        (a) increase `sample` sufficiently, or
        (b) run a second pass per discovered category using
            `/Observation?...&category=<cat>&_summary=count&_total=accurate`.

    Examples
    --------
    >>> get_observation_counts_by_category("60816")
    {'vital-signs': 233, 'laboratory': 412}

    >>> get_observation_counts_by_category("60816", since="2020-01-01", until="2025-10-10")
    {'vital-signs': 87, 'laboratory': 156}
    """
    if isinstance(pid, int):
        pid = str(pid)
    patient_ref = pid if pid.startswith("Patient/") else f"Patient/{pid}"
    params = {"patient": patient_ref, "_count": page_size, "_elements": "category"}
    # Add date filters (allow both ge/le by repeating 'date' in the URL)
    url = "Observation"
    q = [f"patient={patient_ref}", f"_count={page_size}", "_elements=category"]
    if since:
        q.append(f"date=ge{since}")
    if until:
        q.append(f"date=le{until}")
    if len(q) > 3:  # we added date filters; construct URL to preserve duplicate keys
        url = f"Observation?{'&'.join(q)}"
        params = {}  # already encoded in URL

    counts: dict[str, int] = {}
    seen = 0

    while True:
        js = fhir_get(url, params=params if isinstance(url, str) else None)
        for e in js.get("entry", []):
            obs = e.get("resource", {})
            # collect category tokens for this Observation
            toks = set()
            for cat in obs.get("category", []):
                codings = cat.get("coding", [])
                if codings:
                    for c in codings:
                        code = (c.get("code") or "").strip()
                        if code:
                            toks.add(code)
                else:
                    txt = (cat.get("text") or "").strip()
                    if txt:
                        toks.add(txt)
            # increment counts
            for t in toks:
                counts[t] = counts.get(t, 0) + 1

            seen += 1
            if seen >= sample:
                break
        if seen >= sample:
            break
        nxt = next((l["url"] for l in js.get("link", []) if l.get("relation") == "next"), None)
        if not nxt:
            break
        url, params = nxt, None

    return counts




def get_patientids_with_observations(category: str | None = None, page_size: int = 200, max_patients: int | None = None) -> list[str]:
    """
    Return Patient IDs who have at least one Observation in a given category.

    Parameters
    ----------
    category : str or None, default=None
        Observation category token, e.g. ``"laboratory"``, ``"vital-signs"``, ``"imaging"``, ``"survey"``, etc.
        If None, retrieves patients who have *any* Observation.
    page_size : int, default=200
        Number of Patient resources to request per page. Controls paging size of *Patients*, not number of Observations.
    max_patients : int or None, default=None
        Optional hard cap on how many Patient IDs to return across all pages. If None, retrieves all pages.

    Returns
    -------
    list of str
        Patient IDs (e.g., ``["12345", "67890", ...]``) who have at least one Observation in the specified category.

    Notes
    -----
    - Uses FHIR reverse chaining (``_has``) to find Patients who have ``Observation`` resources with 
      ``Observation.subject == Patient`` and ``Observation.category == {category}``.
    - Uses ``_elements=id`` to minimize payload size.
    - This function does *not* count Observations; it only discovers candidate Patients.

    Examples
    --------
    >>> pids = patients_with_observation_category("laboratory", page_size=200, max_patients=1000)
    >>> len(pids)
    1000
    """
    ids: list[str] = []
    url = "Patient"
    params = {"_elements": "id", "_count": page_size}
    if category:
        params["_has:Observation:subject:category"] = category
    else:
        url = "/Patient?_has:Observation:patient:_id"  # any observation

    while True:
        bundle = fhir_get(url, params=params if isinstance(url, str) else None)
        for e in bundle.get("entry", []):
            r = e.get("resource", {})
            pid = r.get("id")
            if pid:
                ids.append(pid)
                if max_patients is not None and len(ids) >= max_patients:
                    return ids
        nxt = next((l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"), None)
        if not nxt:
            break
        url, params = nxt, None
    return ids


def get_chartable_codes_for_patient(pid: str,
                                    min_points: int = 5,
                                    min_span_days: int = 7,
                                    sample: int = 5000,
                                    obs: list[dict] | None = None,
                                    categories: list[str] | None = None) -> list[dict]:
    """
    Identify chartable Observation series (by code) for a patient, with labels/units.

    Parameters
    ----------
    pid : str
        Patient ID (with or without 'Patient/' prefix).
    min_points : int, default=5
        Minimum number of numeric points required per code.
    min_span_days : int, default=7
        Minimum time span (days) required between first and last point per code.
    sample : int, default=5000
        Max observations to scan if `obs` is not provided.
    obs : list of dict or None, default=None
        Optional pre-fetched Observations to analyze. If provided, `categories`
        and `sample` are ignored for fetching.
    categories : list[str] or None, default=None
        If `obs` is None, restrict fetching to these Observation categories
        (e.g., ["laboratory","vital-signs"]). If None, fetch all categories.

    Returns
    -------
    list of dict
        Each item has:
          - code: str
          - label: str
          - units: list[str]
          - count: int
          - span_days: int
        Sorted by count descending.
    """
    patient_ref = pid if str(pid).startswith("Patient/") else f"Patient/{pid}"

    # --- Fetch if not provided ---
    if obs is None:
        if categories:
            obs = []
            for cat in categories:
                obs.extend(get_observations_for_patient(patient_ref, category=cat, count=sample))
        else:
            obs = get_observations_for_patient(patient_ref, count=sample)

    # --- Aggregate numeric points by code (including components) ---
    def _parse_dt(o):
        t = o.get("effectiveDateTime") or o.get("issued")
        if not t:
            return None
        try:
            return datetime.fromisoformat(t.replace("Z", "+00:00"))
        except Exception:
            return None

    points = defaultdict(list)          # code -> list[(dt, value)]
    labels = defaultdict(Counter)       # code -> display strings seen
    units_seen = defaultdict(Counter)   # code -> unit strings seen

    for o in obs:
        dt = _parse_dt(o)
        # top-level value
        vq = o.get("valueQuantity")
        if vq and "value" in vq:
            cc = (o.get("code", {}).get("coding") or [{}])[0]
            code = cc.get("code")
            if code and dt:
                points[code].append((dt, vq["value"]))
                if disp := cc.get("display"): labels[code][disp] += 1
                unit_txt = vq.get("unit") or vq.get("code") or ""
                if unit_txt: units_seen[code][unit_txt] += 1
        # components
        for comp in o.get("component", []):
            vqc = comp.get("valueQuantity")
            if vqc and "value" in vqc:
                cc = (comp.get("code", {}).get("coding") or [{}])[0]
                code = cc.get("code")
                if code and dt:
                    points[code].append((dt, vqc["value"]))
                    if disp := cc.get("display"): labels[code][disp] += 1
                    unit_txt = vqc.get("unit") or vqc.get("code") or ""
                    if unit_txt: units_seen[code][unit_txt] += 1

    out = []
    for code, pts in points.items():
        if len(pts) < min_points:
            continue
        pts.sort(key=lambda x: x[0])
        span_days = (pts[-1][0] - pts[0][0]).days if pts[0][0] and pts[-1][0] else 0
        if span_days < min_span_days:
            continue
        label = (labels[code].most_common(1)[0][0] if labels[code] else f"LOINC {code}")
        units = [u for u, _ in units_seen[code].most_common()] or []
        out.append({"code": code, "label": label, "units": units, "count": len(pts), "span_days": span_days})

    out.sort(key=lambda d: (-d["count"], d["code"]))
    return out



BP_SBP = "8480-6"   # Systolic
BP_DBP = "8462-4"   # Diastolic

LIPIDS   = {"2093-3","2085-9","18262-6","2571-8"}
BMP_LIKE = {"2339-0","2947-0","6298-4","2069-3","20565-8","6299-2","38483-4","49765-1"}
LIVER    = {"1742-6","1920-8","6768-6","1975-2","1751-7","2885-2","10834-0"}
RENAL    = {"38483-4","33914-3"}  # keep special handling below
VITALS   = {"8867-4","9279-1","8302-2","29463-7","39156-5"}

# Survey / SDOH / PRO codes (expand as needed)
SURVEYS  = {"72514-3","55758-7","70274-6","76504-0","63512-8","63586-2","59460-6"}

def group_chartables(chartable_list, include_surveys: bool = False):
    """
    Group chartable LOINC series into sensible chart groups.

    Parameters
    ----------
    chartable_list : list[dict]
        Items with keys: code, label, units, count, span_days.
    include_surveys : bool, default=False
        When False, exclude survey/PRO/SDOH-like codes from chart groups.

    Returns
    -------
    dict[str, list[dict]]
        Mapping of chart title -> list of series dicts.
    """
    by_code = {d["code"]: d for d in chartable_list}

    groups = defaultdict(list)
    used_codes = set()

    # 1) Blood pressure (combine)
    if BP_SBP in by_code and BP_DBP in by_code:
        groups["Blood Pressure (mmHg)"] += [by_code[BP_SBP], by_code[BP_DBP]]
        used_codes.update({BP_SBP, BP_DBP})
    else:
        if BP_SBP in by_code:
            groups["BP (Systolic)"].append(by_code[BP_SBP]); used_codes.add(BP_SBP)
        if BP_DBP in by_code:
            groups["BP (Diastolic)"].append(by_code[BP_DBP]); used_codes.add(BP_DBP)

    # 2) Vitals (separate)
    vit_titles = {
        "8867-4": "Heart Rate (/min)",
        "9279-1": "Respiratory Rate (/min)",
        "8302-2": "Height (cm)",
        "29463-7": "Weight (kg)",
        "39156-5": "BMI (kg/m²)",
    }
    for code, title in vit_titles.items():
        if code in by_code:
            groups[title].append(by_code[code]); used_codes.add(code)

    # 3) Lipids (separate)
    lipid_titles = {
        "2093-3": "Cholesterol (mg/dL)",
        "2085-9": "HDL (mg/dL)",
        "18262-6": "LDL (mg/dL)",
        "2571-8": "Triglycerides (mg/dL)",
    }
    for code, title in lipid_titles.items():
        if code in by_code:
            groups[title].append(by_code[code]); used_codes.add(code)

    # 4) BMP-like chemistries (separate)
    bmp_titles = {
        "2339-0": "Glucose (mg/dL)",
        "2947-0": "Sodium (mmol/L)",
        "6298-4": "Potassium (mmol/L)",
        "2069-3": "Chloride (mmol/L)",
        "20565-8": "CO₂ (mmol/L)",
        "6299-2": "BUN (mg/dL)",
        "38483-4": "Creatinine (mg/dL)",
        "49765-1": "Calcium (mg/dL)",
    }
    for code, title in bmp_titles.items():
        if code in by_code and code not in used_codes:
            groups[title].append(by_code[code]); used_codes.add(code)

    # 5) Renal function (don’t duplicate creatinine if already placed)
    if "38483-4" in by_code and "38483-4" not in used_codes:
        groups["Creatinine (mg/dL)"].append(by_code["38483-4"]); used_codes.add("38483-4")
    if "33914-3" in by_code:
        groups["eGFR (mL/min/1.73m²)"].append(by_code["33914-3"]); used_codes.add("33914-3")

    # 6) Liver panel (separate)
    liver_titles = {
        "1742-6": "ALT (U/L)",
        "1920-8": "AST (U/L)",
        "6768-6": "ALP (U/L)",
        "1975-2": "Bilirubin (mg/dL)",
        "1751-7": "Albumin (g/dL)",
        "2885-2": "Total Protein (g/dL)",
        "10834-0": "Globulin (g/L)",
    }
    for code, title in liver_titles.items():
        if code in by_code and code not in used_codes:
            groups[title].append(by_code[code]); used_codes.add(code)

    # 7) Surveys/PRO/SDOH (optional)
    if include_surveys:
        survey_titles = {
            "72514-3": "Pain score (0–10)",
            "55758-7": "PHQ-2 total",
            "70274-6": "GAD-7 total",
            "76504-0": "HARK total",
            "63512-8": "Household size",
            "63586-2": "Household income (per annum)",
            "59460-6": "Morse fall risk total",
        }
        for code, title in survey_titles.items():
            if code in by_code and code not in used_codes:
                groups[title].append(by_code[code]); used_codes.add(code)

    # 8) Anything else → one chart per code
    for d in chartable_list:
        c = d["code"]
        if c not in used_codes:
            unit = f" ({d['units'][0]})" if d.get("units") else ""
            groups[f"{d['label']}{unit}"].append(d)
            used_codes.add(c)

    return dict(groups)

