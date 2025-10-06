# Synthetic patient data served from HAPI FHIR

This repo provides guidance on creating synthetic patient data & serving it from a FHIR API.  If nothing else, it will hopefully provide a first step for developers to familiarize themselves with some of the technologies used when working with EMR (electronic medical records) systems. 

This could be useful for the development of an LLM Agent which creates a patient summary based on their prior visits & hospital records; or to add a chart note based on a patient meeting.  An LLM Agent is NOT included in this repo. 


## Standards & tech stack 

Standards: 
- [FHIR](https://www.hl7.org/fhir/overview.html) - Fast Healthcare Interoperability Resources
- [DICOM](https://www.dicomstandard.org/) - Digital Imaging and Communications in Medicine 
- [SMART](https://docs.smarthealthit.org/) (optional) - Authentication & authorization for FHIR. 

Technologies: 
- [Synthea](https://synthea.mitre.org/) - open-source synthetic patient data generator
- [HAPI FHIR](https://hapifhir.io/) - open-source FHIR server (Java but we will use the docker version)
- [Orthanc](https://www.orthanc-server.com/) - open-source DICOM server 


## Pre-requisites: 

* Java 17+ for Synthea (we are using Java 21)
* Docker for running HAPI FHIR server 
* Python 3.12+ for charting functions.   Poetry for dependency management. 


## Guide:

1. [Generate synthetic dataset using Synthea](./docs/1-synthea-dataset.md) 
2. [Load & serve FHIR bundles into HAPI FHIR server](./docs/2-hapi-fhir.md)
3. [Use HAPI FHIR with Postgres](./docs/3-hapi-fhir-with-postgres.md) for data persistence & larger patient sets  
4. [Connect an LLM with a FHIR MCP server](./docs/4-fhir-mcp-server.md)
5. [Generate charts using FHIR observational data](./docs/5-observational-data-charts.md)


## To do:

- DICOM images using Orthanc 
- Test HAPI FHIR's GraphQL API  