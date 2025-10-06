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

The function in `scripts/identify_chartable_patients.py` does as its name says. 

 See the docstring for details. 

 