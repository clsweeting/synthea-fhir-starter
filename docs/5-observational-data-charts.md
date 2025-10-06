# Creating observational data charts

Use the function to find pateints with most observabtioanldata: 

```python 
include_patients_from_observations()
(['1607',
  '169697',
  '170278',
  '115532',
  '171283',
  '171530',
  '171899',
  '172422',
  '173350'],
 Counter({
     '172422': 303,
     '170278': 151,
     '169697': 141,
     '171283': 137,
     '171530': 97,
     '171899': 88,
     '1607': 60,
     '173350': 17,
     '115532': 4,
     '1809': 1,
     '60816': 1
 }))
```

The list ([...]) → The IDs of patients who have at least one Observation resource.
So you can use those IDs to fetch or plot data, e.g. get_observations_for_patient('172422').
	•	The Counter → How many Observations were found for each patient.
For example:
	•	Patient 172422 has 303 Observations
	•	Patient 170278 has 151
	•	Patient 169697 has 141, etc.

So that tells you which patients have the richest data — exactly what you’d want if you plan to visualize trends or lab results.


### How to use this data

```python 
ids, counts = include_patients_from_observations()
rich_patients = [pid for pid, c in counts.items() if c > 100]

print("Patients with >100 observations:", rich_patients)
```

Now tha tyou know who has th emost rich data, put in yor charting code: 

```
for pid in rich_patients[:3]:  # just a few
    png = plot_and_encode(pid)
    if png:
        attach_docref(pid, png)
```


You’re exactly right:
→ Observation count ≠ richness of a time series.
A patient with 300 scattered lab values isn’t necessarily better to chart than one with 20 consistent cholesterol readings over years.

Let’s unpack this and design a robust way to find patients with good “chartable” data 👇



## Define what “chartable” means

For a given visualization (say, cholesterol or BMI trend), you ideally want:
	1.	Single code focus (same measurement type)
e.g. LOINC 2093-3 = Total Cholesterol
	2.	Longitudinal span — measurements over time (not all same day).
	3.	Sufficient points — at least 3–5 values spaced apart.
	4.	Consistent units — avoid mixing mg/dL vs mmol/L.


## What makes good chart data 

| Dimension  | Good chart | Bad chart |
|------------|------------|-----------|
| Same LOINC | ✓ consistent metric | ✗ mixed types |
| Temporal span | ✓ months/years apart | ✗ same-day | 
| Enough points | ✓ ≥3.    | ✗ 1–2     |
| Unit consistency | ✓ single unit    | ✗ mixed units | 

