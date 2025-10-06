# Generate synthetic patient data 

Pre-requisites: Java 17+

Tip: Open a new terminal & use a new directory - do NOT work within this repo' root. 


### 1. Clone and build 

Clone the Synthea repo: 

```bash 
git clone https://github.com/synthetichealth/synthea
cd synthea 
```

The rest of the instructions assume you are in the Synthea repo root. 

Build (can take up to 10 minutes):

```bash 
./gradlew build
```

<br>

### 2. Generate synthetic patients 

Normally you would generate synthetic patient data as follows: 

```bash 
./run_synthea -p 500 Massachusetts
```

This will create FHIR R4 JSON bundles in the `./output/fhir` folder.  Each file corresponds to a synthetic patient. 

Check you have individual JSON files: 

```bash 
output
├── fhir
│   ├── Andrea7_Beahan375_301c8c78-68e6-fd02-34c3-b84d73a1e064.json
│   ├── Angelina101_McCullough561_80d356ea-52df-6aa3-da0e-1706f82f1f38.json
│   ├── Barry322_Oberbrunner298_b9f64edb-9f75-7807-ca6d-afa95980c030.json
│   ├── Bobby524_Sherlene302_Runte676_623a08b6-eb76-ec2f-2f18-727638d2a324.json
│   ├── Boris111_Barrows492_7b389c8a-3403-bdd7-0996-7b0c8b02bcea.json
│   ├── Brigida296_Brekke496_262adff9-6f87-7736-e11f-467cd21c997b.json
│   ├── Britany225_Gleason633_891653a4-5303-7345-a947-4f9b5b77beae.json
.... 
```

Notes: 

- Check the sizes of these files - they can range from 3MB to 50MB or more. 
- Check that in addition to files representing individual patients, there should also be files starting with "practitionerInformation" and "hospitalInformation".
- You could just as easily have used "Florida"as the location. 
- For locations outside the US, see https://github.com/synthetichealth/synthea-international from which you can also get a feel for what's required to create a custom geography. 

<br>

### 3. Optional: constrain the age range 

You can use the `-a` flag to constrain the patients to an age range. For example, to create synthetic patients between the ages of 70 and 95 (who will therefore have more longitudinal data):

```
./run_synthea -p 200 -a 70-95 Massachusetts
```

<br>

### Next steps 

[Add the FHIR bundles to HAPI FHIR server](./2-hapi-fhir.md)