# Datasets

This document restates the dataset sources from the development plan and records how they are loaded in this codebase.

## Medical coding reference data

The schema (`icd10_codes`, `procedure_codes`) is designed to hold the full official CMS ICD-10-CM and HCPCS release files. Loading the full releases requires downloading and converting the official CMS fixed-width or XML files into the CSV schema below, which is outside the scope of a local development environment.

For local development, testing, and demos, this repository ships curated sample sets covering common diagnosis and procedure categories:

- `backend/data/reference/icd10_sample.csv` (columns: `code, short_description, long_description, chapter, category`)
- `backend/data/reference/hcpcs_sample.csv` (columns: `code, description, category, is_sample_only`)

Load them with:

```
python -m scripts.load_reference_codes --icd10 data/reference/icd10_sample.csv --hcpcs data/reference/hcpcs_sample.csv
```

The script generates a sentence-transformers embedding for each code description and stores it in the `embedding` pgvector column, enabling cosine similarity search against clinical text.

To load a full official CMS release instead: download the current ICD-10-CM code tables from cms.gov and the current HCPCS Level II quarterly release, convert each to the same CSV column layout, and point `--icd10` / `--hcpcs` at the converted files. No code changes are required.

CPT codes are copyrighted by the American Medical Association and are not redistributed in full. `hcpcs_sample.csv` includes a small set of widely documented E/M codes (for example 99213, 99214) flagged `is_sample_only=true` for illustrative use only.

## Doctor-patient dialogue and clinical note data

`backend/data/seed/sample_encounters.json` contains a small set of synthetic doctor-patient transcripts paired with SOAP notes, built in the internal `encounters` / `soap_notes` schema. The content is informed by the structure of MTS-Dialog and ACI-BENCH (transcript plus Subjective/Objective/Assessment/Plan sections) but is entirely synthetic; no real patient data is used.

Load it with:

```
python -m scripts.seed_encounters
```

This creates a demo organization, a demo clinician user, and one patient/encounter/SOAP note per record.

To use the real MTS-Dialog or ACI-BENCH datasets (for prompt engineering or evaluation in later phases), download them from Hugging Face (`har1/MTS_Dialogue-Clinical_Note`, `mkieffer/ACI-Bench`) and map their fields into the same JSON shape used by `sample_encounters.json`.

## Data handling rule

No real patient data is used in development, staging, or demo environments. Only the curated sample reference codes and the synthetic seed encounters above are loaded outside of a properly secured, access-controlled, compliant production environment.
