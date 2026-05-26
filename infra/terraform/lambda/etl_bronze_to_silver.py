"""
AWS AI Watchman - ETL Lambda: Bronze -> Silver
==============================================
Triggered automatically when a PDF lands in s3://bronze-raw/manuals/.
Extracts text page-by-page using pypdf, then writes a structured JSON
document to s3://silver-cleaned/manuals/.

Triggered by: S3 ObjectCreated — filter prefix=manuals/, suffix=.pdf
"""

import io
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone

import boto3
import pypdf

SILVER_BUCKET = os.environ["SILVER_BUCKET"]
s3 = boto3.client("s3")


def extract_text(pdf_bytes: bytes) -> list:
    """Return list of {page, text} dicts using pypdf."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    sections = []
    for i, page in enumerate(reader.pages, 1):
        raw = page.extract_text() or ""
        cleaned = re.sub(r"\n{3,}", "\n\n", raw.strip())
        if cleaned:
            sections.append({"page": i, "text": cleaned})
    return sections


def handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        if not key.endswith(".pdf"):
            print(f"Skipping non-PDF: {key}")
            continue

        print(f"Processing s3://{bucket}/{key}")

        # Download from Bronze
        pdf_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        print(f"  Downloaded {len(pdf_bytes) / 1024:.1f} KB")

        # Extract text
        sections = extract_text(pdf_bytes)
        full_text = "\n\n".join(s["text"] for s in sections)
        print(f"  Extracted {len(sections)} pages, {len(full_text)} chars")

        # Equipment ID from filename: manuals/CAT-EX_service_manual.pdf -> CAT-EX
        filename = key.split("/")[-1]
        equipment_id = filename.replace("_service_manual.pdf", "")

        silver_doc = {
            "source_bucket": bucket,
            "source_key": key,
            "equipment_id": equipment_id,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "pages": len(sections),
            "sections": sections,
            "full_text": full_text,
            "char_count": len(full_text),
        }

        # Write to Silver
        silver_key = f"manuals/{equipment_id}_service_manual.json"
        s3.put_object(
            Bucket=SILVER_BUCKET,
            Key=silver_key,
            Body=json.dumps(silver_doc, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"  -> s3://{SILVER_BUCKET}/{silver_key}")

    return {"statusCode": 200}
