# HAPI FHIR with Postgres 

Let's use Postgres to reduce the memory load on the HAPI FHIR server. Less risk of OOM errors. And also mitigate the need to reload FHIR data bundles, by using a volume mount. 



### 1. Run HAPI FHIR with Postgres 

A docker-compose.yml has been included: 

```bash 
docker compose up -d
```

To restart the whole stack: 

```bash 
docker compose down
docker compose up -d
```

To destroy the volume mount (i.e. postgres data)
```
docker compose down -v 
```

<br>

-------------------------


### 2. Upload your synthetic patient data 

Copy the included script `scripts/upload-fhir.sh` to the root of your Synthea repo, chmod it and run it.  It will upload the infrastructure files & then then synthetic patient data. 

<br>

--------------------------

### 3. Query like an EMR

List some patients: 

```bash 
curl "http://localhost:8080/fhir/Patient?_count=3"
```

Get the conditions for a specific patient

```bash 
# replace '{id}' with the ID of an actual patient 
curl "http://localhost:8080/fhir/Condition?patient={id}"
```

Recent labs (Observations) for the patient

```bash 
curl "http://localhost:8080/fhir/Observation?patient={id}&category=laboratory&_sort=-date&_count=10"
```

Medication orders

```bash 
curl "http://localhost:8080/fhir/MedicationRequest?patient={id}"
```




