import collections 
import os

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



def identify_patients_with_observations(codes=None, category=None, sample=1000, min_points=3):
    """
    Identify patients who have at least a minimum number of Observation resources.

    This function queries the FHIR server for `Observation` resources, optionally
    filtering by LOINC codes or category, and counts how many Observations exist per patient.
    Patients with at least `min_points` Observations are returned (up to 200 by default).
    The function uses paging and may follow `_link.next` URLs until the `sample` limit
    of processed Observation resources is reached.

    Parameters
    ----------
    codes : list of str, optional
        List of Observation LOINC codes to filter by. If provided, only Observations
        matching these codes are considered. If None, all codes are included.
    category : str, optional
        FHIR Observation category token (e.g. ``"vital-signs"`` or ``"laboratory"``).
        If provided, limits the query to that category.
    sample : int, default=1000
        Maximum number of Observation resources to process before stopping.
        This acts as a performance safeguard against extremely large datasets.
    min_points : int, default=3
        Minimum number of Observations a patient must have to be included
        in the returned list.

    Returns
    -------
    tuple[list of str, collections.Counter]
        A tuple containing:
        - **qualified** : list of patient IDs (str) who meet the `min_points` threshold.
          Limited to at most 200 patients.
        - **counts** : a Counter mapping each patient ID to the number of
          Observations found for that patient.

    Notes
    -----
    - This function relies on the helper :func:`fhir_get` to handle pagination
      and execute GET requests against the FHIR server.
    - Some servers may include referenced `Patient` resources via the `_include`
      parameter or via embedded resources, which are also captured if present.
    - The function does not currently de-duplicate Observations across pages,
      but the `_id` field can be used for that if needed.

    Examples
    --------
    >>> pids, counts = include_patients_from_observations(category="vital-signs", min_points=5)
    >>> len(pids)
    12
    >>> counts.most_common(3)
    [('172422', 303), ('170278', 151), ('169697', 141)]
    """
    params = {"_count": 200}
    if codes:
        params["code"] = ",".join(codes)
    if category:
        params["category"] = category

    seen = 0
    counts = collections.Counter()
    patients = {}
    url = "Observation"
    while True:
        js = fhir_get(url, params=params)
        entries = js.get("entry", [])
        for e in entries:
            res = e["resource"]
            subj = res.get("subject", {})
            if subj.get("reference", "").startswith("Patient/"):
                pid = subj["reference"].split("/", 1)[1]
                counts[pid] += 1
        # Also request explicit include (server-dependent)
        # Try to grab included patients if present
        for e in entries:
            r = e.get("resource", {})
            if r.get("resourceType") == "Patient":
                patients[r["id"]] = r

        seen += len([e for e in entries if e.get("resource", {}).get("resourceType") == "Observation"])
        if seen >= sample:
            break
        nxt = next((link["url"] for link in js.get("link", []) if link["relation"] == "next"), None)
        if not nxt:
            break
        url, params = nxt, None

    # Filter by min_points
    qualified = [pid for pid, c in counts.items() if c >= min_points]
    return qualified[:200], counts  # return top list and raw counts



def identify_chartable_patients(codes=None, category=None, sample=2000, min_points=3):
    """
    Identify patients with observation histories suitable for time-series charting.

    This function scans Observation resources from a FHIR server and groups them by
    patient and observation code (LOINC). It counts how many data points exist for
    each (patient, code) pair and estimates the temporal span between the first and
    last measurement. Patients with at least `min_points` observations for a code and
    a timespan greater than `min_span_days` are considered "chartable" — i.e.,
    they have meaningful longitudinal data suitable for plotting trends.

    Parameters
    ----------
    sample : int, default=2000
        The maximum number of Observation resources to retrieve and analyze.
        Larger samples increase accuracy but take longer to fetch.
    min_points : int, default=5
        Minimum number of Observations for a single LOINC code required to consider
        that code as a potential time series for a patient.
    min_span_days : int, default=7
        Minimum duration (in days) between the earliest and latest Observation dates
        for a code to be considered longitudinal rather than a single event.

    Returns
    -------
    dict[str, list[tuple[str, int, int]]]
        A dictionary keyed by patient ID. Each value is a list of tuples in the form:
        `(code, count, span_days)`, where:
        
        - **code** (`str`): The LOINC code or Observation code identifier.
        - **count** (`int`): The number of Observations for that code.
        - **span_days** (`int`): The time span in days between the first and last
          Observation timestamps for that code.

        Example:
        ```
        {
            "60816": [
                ("72514-3", 228, 1125),
                ("74006-8", 216, 831),
                ("33914-3", 44, 1100)
            ],
            "170278": [
                ("29463-7", 12, 180),
                ("8867-4", 8, 120)
            ]
        }
        ```

    Notes
    -----
    - The function relies on the global `fhir_get` helper to query the FHIR endpoint.
    - It assumes Observations include `effectiveDateTime` or `issued` timestamps
      in ISO 8601 format and that the server supports pagination.
    - Only patients with at least one qualifying (code, count, span) combination
      are included in the output.
    - To ensure diversity, increase the `sample` parameter; smaller samples often
      yield results dominated by a single high-volume patient.

    See Also
    --------
    include_patients_from_observations : Simpler count-based patient inclusion filter.
    get_observations_for_patient : Retrieve full Observation data for a single patient.

    Examples
    --------
    >>> chartable_patients(sample=5000, min_points=10, min_span_days=30)
    {
        "60816": [("72514-3", 228, 1125), ("74006-8", 216, 831)],
        "170278": [("29463-7", 12, 180)]
    }
    """
    qualified = collections.defaultdict(list)
    js_counts = identify_patients_with_observations(codes=codes, category=category,
                                                  sample=sample, min_points=min_points)[1]

    # For each high-count patient, fetch all their observations
    for pid, cnt in js_counts.most_common(100):
        obs = get_observations_for_patient(pid, codes=codes, category=category)
        # group by LOINC code
        by_code = collections.defaultdict(list)
        for o in obs:
            code = o.get("code", {}).get("coding", [{}])[0].get("code")
            val = o.get("valueQuantity", {}).get("value")
            t = o.get("effectiveDateTime")
            if code and val and t:
                try:
                    dt = datetime.fromisoformat(t.replace("Z","+00:00"))
                except:
                    continue
                by_code[code].append((dt, val))

        # rank codes by number of points and time span
        chartable_codes = []
        for c, pts in by_code.items():
            if len(pts) >= min_points:
                pts.sort(key=lambda x: x[0])
                span_days = (pts[-1][0] - pts[0][0]).days
                if span_days > 30:  # at least 1 month apart
                    chartable_codes.append((c, len(pts), span_days))

        if chartable_codes:
            qualified[pid] = sorted(chartable_codes, key=lambda x: x[1], reverse=True)
    return qualified


