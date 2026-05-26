#!/usr/bin/env python3
"""
AWS AI Watchman - Bronze to Silver ETL: PDF Manuals
=====================================================
Downloads PDF manuals from the Bronze S3 bucket (manuals/ prefix),
extracts clean text using pdfplumber, and writes structured JSON
documents to the Silver bucket.

Silver schema per manual:
  {
    "source_key":    "manuals/CAT-EX_service_manual.pdf",
    "equipment_id":  "CAT-EX",
    "model":         "Caterpillar 320 Hydraulic Excavator",
    "processed_at":  "2026-05-25T18:00:00Z",
    "pages":         22,
    "sections": [
      {"page": 1, "text": "..."},
      ...
    ],
    "full_text":     "concatenated clean text for chunking"
  }

Usage:
    python bronze_to_silver.py
    python bronze_to_silver.py --bronze-bucket my-bucket --silver-bucket my-silver
    python bronze_to_silver.py --dry-run
"""

import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pdfplumber
from botocore.exceptions import ClientError

BRONZE_BUCKET = "aws-ai-watchman-dev-bronze-raw"
SILVER_BUCKET = "aws-ai-watchman-dev-silver-cleaned"
BRONZE_PREFIX = "manuals/"
SILVER_PREFIX = "manuals/"

# Equipment ID extraction from filename: "CAT-EX_service_manual.pdf" -> "CAT-EX"
EQUIPMENT_ID_RE = re.compile(r"^manuals/([A-Z]+-[A-Z]+)_service_manual\.pdf$")


def list_bronze_manuals(s3, bucket: str) -> list:
    """Return list of PDF keys under the manuals/ prefix."""
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=BRONZE_PREFIX)
    return [
        obj["Key"]
        for obj in resp.get("Contents", [])
        if obj["Key"].endswith(".pdf")
    ]


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Use pdfplumber to extract text page by page.
    Returns {"pages": int, "sections": [...], "full_text": str}
    """
    sections = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            raw = page.extract_text() or ""
            # Normalise whitespace — collapse multiple blank lines to one
            cleaned = re.sub(r"\n{3,}", "\n\n", raw.strip())
            if cleaned:
                sections.append({"page": i, "text": cleaned})

    full_text = "\n\n".join(s["text"] for s in sections)
    return {
        "pages": len(sections),
        "sections": sections,
        "full_text": full_text,
    }


def infer_equipment_info(key: str, full_text: str) -> dict:
    """
    Extract equipment ID and model from the key or fallback to text search.
    """
    m = EQUIPMENT_ID_RE.match(key)
    equipment_id = m.group(1) if m else "UNKNOWN"

    # Pull model name from first non-empty line of extracted text
    model = "Unknown Model"
    for line in full_text.splitlines():
        line = line.strip()
        if len(line) > 10 and not line.lower().startswith("service"):
            model = line[:100]
            break

    return {"equipment_id": equipment_id, "model": model}


def process_manual(s3, bronze_bucket: str, silver_bucket: str, key: str, dry_run: bool) -> dict:
    """Download one PDF, extract text, write Silver JSON. Returns summary dict."""
    print(f"  Processing {key} ...")

    # Download from Bronze
    obj = s3.get_object(Bucket=bronze_bucket, Key=key)
    pdf_bytes = obj["Body"].read()
    print(f"    Downloaded {len(pdf_bytes) / 1024:.1f} KB")

    # Extract text
    extracted = extract_text_from_pdf(pdf_bytes)
    print(f"    Extracted {extracted['pages']} pages, {len(extracted['full_text'])} chars")

    # Build Silver document
    info = infer_equipment_info(key, extracted["full_text"])
    silver_doc = {
        "source_bucket": bronze_bucket,
        "source_key": key,
        "equipment_id": info["equipment_id"],
        "model": info["model"],
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "pages": extracted["pages"],
        "sections": extracted["sections"],
        "full_text": extracted["full_text"],
        "char_count": len(extracted["full_text"]),
    }

    # Write to Silver
    filename = Path(key).stem + ".json"
    silver_key = SILVER_PREFIX + filename
    payload = json.dumps(silver_doc, ensure_ascii=False, indent=2)

    if dry_run:
        print(f"    [DRY RUN] would write s3://{silver_bucket}/{silver_key}")
    else:
        s3.put_object(
            Bucket=silver_bucket,
            Key=silver_key,
            Body=payload.encode("utf-8"),
            ContentType="application/json",
        )
        print(f"    Wrote s3://{silver_bucket}/{silver_key} ({len(payload) / 1024:.1f} KB)")

    return {
        "source_key": key,
        "silver_key": silver_key,
        "equipment_id": info["equipment_id"],
        "pages": extracted["pages"],
        "chars": len(extracted["full_text"]),
    }


def main():
    parser = argparse.ArgumentParser(description="Bronze -> Silver ETL: PDF Manuals")
    parser.add_argument("--bronze-bucket", default=BRONZE_BUCKET)
    parser.add_argument("--silver-bucket", default=SILVER_BUCKET)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dry-run", action="store_true", help="Skip S3 writes")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)

    # Discover PDFs in Bronze
    keys = list_bronze_manuals(s3, args.bronze_bucket)
    if not keys:
        print(f"No PDFs found under s3://{args.bronze_bucket}/{BRONZE_PREFIX}")
        print("Run: python scripts/ingest/generate_manuals.py && python scripts/ingest/upload_to_bronze.py")
        sys.exit(1)

    print(f"Found {len(keys)} PDF(s) in s3://{args.bronze_bucket}/{BRONZE_PREFIX}")
    print()

    results = []
    errors = []
    for key in keys:
        try:
            r = process_manual(s3, args.bronze_bucket, args.silver_bucket, key, args.dry_run)
            results.append(r)
        except Exception as exc:
            print(f"  ERROR processing {key}: {exc}")
            errors.append({"key": key, "error": str(exc)})

    print()
    print("-" * 60)
    print(f"Processed : {len(results)} manuals")
    if errors:
        print(f"Errors    : {len(errors)}")
        for e in errors:
            print(f"  {e['key']}: {e['error']}")
    print()
    for r in results:
        print(f"  {r['equipment_id']:10s} | {r['pages']:3d} pages | {r['chars']:6d} chars | {r['silver_key']}")

    print()
    if not args.dry_run:
        print("OK  Silver layer updated.")
        print("    Next: python scripts/etl/silver_to_gold.py")
    else:
        print("DRY RUN complete — no files written.")


if __name__ == "__main__":
    main()
