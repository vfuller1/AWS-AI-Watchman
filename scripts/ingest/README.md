# Data Ingestion — Bronze Layer

Populates the Bronze S3 layer with synthetic telemetry, maintenance records,
and real OEM manuals for the AWS AI Watchman lakehouse.

## Setup

```bash
cd scripts/ingest
pip install -r requirements.txt
```

Make sure your AWS credentials are active (`aws configure` or env vars).

---

## Step 1 — Generate synthetic data

**IoT sensor telemetry (1 000 readings, 30-day window):**
```bash
python generate_telemetry.py
```

**Maintenance service logs (1 000 records, 12-month window):**
```bash
python generate_maintenance.py
```

Both scripts write CSV files into the `data/` folder.

Optional flags:
```bash
python generate_telemetry.py --rows 5000 --days 60
python generate_maintenance.py --rows 2000
```

---

## Step 2 — Add OEM manuals

Download 5–10 real, publicly available heavy-equipment PDFs and drop them
into the `data/` folder. Good sources:

| Equipment | URL |
|---|---|
| CAT 320 Excavator | https://www.cat.com/en_US/support/operations/operators-manuals.html |
| Genie Z-45 Boom Lift | https://www.genielift.com/en/resources/manuals |
| JLG 450AJ | https://www.jlg.com/en/support/manuals |
| John Deere 700K Dozer | https://techpubs.deere.com |
| Komatsu FG25 Forklift | https://www.komatsu.com/en/support/service-manuals |

The Lambda router will automatically file PDFs under `manuals/` in the
Bronze bucket when they are uploaded.

---

## Step 3 — Preview upload (dry run)

```bash
python upload_to_bronze.py --dry-run
```

---

## Step 4 — Upload to Bronze S3

```bash
python upload_to_bronze.py
```

The Bronze Router Lambda fires on each `ObjectCreated` event and routes
the file into the correct typed sub-folder:

| Extension | Destination |
|---|---|
| `.pdf` | `manuals/` |
| `.csv` | `telemetry/` |
| `.json` | `service-logs/` |
| other | `unclassified/` |

Check Lambda routing logs:
```bash
aws logs tail /aws/lambda/aws-ai-watchman-dev-bronze-router --follow
```

---

## Step 5 — Run the Glue Crawler

Once data is in Bronze, run the crawler **on-demand** to infer schema and
populate the Glue Data Catalog:

```bash
aws glue start-crawler --name aws-ai-watchman-dev-bronze-crawler
aws glue get-crawler --name aws-ai-watchman-dev-bronze-crawler \
  --query 'Crawler.State'
```

When state returns `READY`, your Bronze schema is catalogued.

---

## Interview talking point

> *"For the Bronze ingestion pipeline I deliberately avoided Kinesis and Glue
> Streaming — both would cost dollars per hour for a POC with no real-time
> requirement. Instead I used direct S3 PUT via Boto3 for fractions of a penny,
> an on-demand Glue Crawler that runs in minutes and costs under a dollar, and
> a Lambda router on the free tier to auto-classify files by type. Total ingestion
> cost for this dataset: under $0.05."*
