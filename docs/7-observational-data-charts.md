# Creating observational data charts

### What makes good chart data ? 

Observation count ≠ richness of a time series.
A patient with 300 scattered lab values isn’t necessarily better to chart than one with 20 consistent cholesterol readings over years.


For a given visualization (say, cholesterol or BMI trend), you ideally want:

1.	Single code focus (same measurement type) e.g. LOINC 2093-3 = Total Cholesterol

2.	Longitudinal span — measurements over time (not all same day).

3.	Sufficient points — at least 3–5 values spaced apart.

4.	Consistent units — avoid mixing mg/dL vs mmol/L.


### Summary 

| Dimension  | Good chart | Bad chart |
|------------|------------|-----------|
| Same LOINC | ✓ consistent metric | ✗ mixed types |
| Temporal span | ✓ months/years apart | ✗ same-day | 
| Enough points | ✓ ≥3.    | ✗ 1–2     |
| Unit consistency | ✓ single unit    | ✗ mixed units | 


### Script to identify chartable patients 

The functions in `scripts/identify_chartable_patients.py` help: 
- identify patients with observational data 
- group & count the observation types (categories) per patient 
- group & count the actual LOINC codes per patient 
- logically group the observational data series for charting 


Given the output of the above, you can then use the function in `scripts/create_charts.py` to generate PNG charts


### Usage 

Assuming you've created/defined the functions in your REPL (this is a spike after all):

```python 
pid = "173418"                      

# Fetch only obsevations clinical data 
labs   = get_observations_for_patient(pid, category="laboratory")
vitals = get_observations_for_patient(pid, category="vital-signs")
obs = labs + vitals 

# Find chartable codes using the pre-fetched data:
chartables = get_chartable_codes_for_patient(pid, obs=obs)  # ignores 'categories' & 'sample' since obs is provided

# Group (excluding surveys/SDOH - e.g. household size):
groups = group_chartables(chartables, include_surveys=False)

# Render PNGs:
pngs = render_groups_to_png(pid, groups, out_dir="./charts", since=None, until=None)
print(pngs)
```
 