# Medical terminology coding - ICD, SNOMED, LOINC 


Clinical coding is the process of translating written or recorded clinical information (diagnoses, symptoms, procedures, test results, etc.)
into **standardized codes** from controlled vocabularies.

There are different coding systems. 

| Data element | Coding system | Example code | Meaning |
|--------------|---------------|--------------|---------|
| Diagnosis    | ICD-10-CM     | E11.22.     | Type 2 diabetes mellitus with diabetic chronic kidney disease |
| Problem list | SNOMED CT | 127013003 | Disorder of kidney due to diabetes mellitus |
| Medication | RxNorm / ATC | 860975 | Metformin 500 mg oral tablet |
| Lab test | LOINC | 4548-4 | Hemoglobin A1c measurement |
| Units | UCUM | % | Percent |


<br>

-----------------------------------


### Why clinical coding exists 

Coding serves two different audiences: 

| Purpose      | Typical Users | Code Systems | 
|--------------|---------------|--------------|
| Clinical care (precision, interoperability) | Physicians, EHRs, researchers | SNOMED CT, LOINC, RxNorm, UCUM | 
| Administrative / billing (statistics, reimbursement) | Coders, billing staff, insurers | ICD-10-CM/-AM/-WHO, CPT, HCPCS | 

<br>

-----------------------------------


### SNOMED and ICD

SNOMED and ICD describe medical concepts. They were designed for different purposes, and most hospitals actually use both together.   Think: 

> - SNOMED CT → speaks the language of medicine
> - ICD → speaks the language of payers and statisticians

<br>

| Aspect |  SNOMED CT | ICD-10 / ICD-11 |
|-------|------------|------------------|
| Purpose | Detailed clinical terminology for recording what the clinician sees, thinks, or does | Coded classification for billing, reporting, and statistics |
| Level of detail | Very fine-grained (hundreds of thousands of concepts: disorders, findings, procedures, social context, etc.) | Coarse-grained (tens of thousands of codes grouped for reimbursement & epidemiology) |
| Maintainer | SNOMED International | World Health Organization (WHO) |  
| Use in FHIR | Condition.code, Observation.code, Procedure.code, etc. | Condition.code (for billing/export), Claim.diagnosis |
| Used by | Clinicians, EHR vendors | Hospitals’ billing & coding departments, payers, public-health agencies | 

In modern systems (especially in the U.S, U.K, Australia, etc.):
- the doctor enters data in SNOMED, because it’s precise.
- when the encounter is submitted for billing, software or coders map those SNOMED concepts to the corresponding ICD-10-CM (and CPT/HCPCS for procedures).
- that mapping is often automated via terminology services or handled by certified coders, because one SNOMED concept can map to several ICD codes depending on context.


Large institutions use both layers:
1.	SNOMED CT inside the EHR for clinicians (notes, problem lists, structured data).
2.	ICD-10-CM (U.S.) or ICD-10-AM/ICD-11 internationally for billing, discharge summaries, and public-health reporting.



<br>

-----------------------------------


### So what is HL7 ? 

HL7 is NOT a coding system like SNOMED or ICD — it’s a messaging and data-exchange standard.  

If SNOMED, ICD & LOINC are the words & vocabulary, then HL7 / FHIR are the grammar & structure.  

Example: SNOMED code '59621000' is represented as follows in HL7 FHIR JSON: 

```json
{
  "resourceType": "Condition",
  "code": {
    "coding": [
      {
        "system": "http://snomed.info/sct",
        "code": "59621000",
        "display": "Essential hypertension (disorder)"
      }
    ]
  }
}
```

<br>


There are several generations of HL7 standards:

| Version         |  Era                  |  Example use    | 
|-----------------|-----------------------|-----------------|
| HL7 v2.x.       | 1980s–present         | Simple pipe-delimited hospital messages (ADT, ORM, etc.) |
| HL7 v3 / CDA.   | 2000s                 | XML-based clinical documents (e.g., discharge summaries) |
| HL7 FHIR        | 2010s–now             | Modern REST/JSON-based API standard for healthcare data. |

<br>


