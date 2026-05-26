"""
AWS AI Watchman - ETL Lambda: Silver -> Gold + KB Ingestion Trigger
===================================================================
Triggered automatically when a Silver JSON file lands in
s3://silver-cleaned/manuals/.  Chunks the full_text into overlapping
segments and writes individual .txt files to s3://gold-vector-ready/manuals/.

If the Knowledge Base is enabled (KB_ID env var is set), automatically
calls bedrock-agent:StartIngestionJob after all chunks are written.

Triggered by: S3 ObjectCreated — filter prefix=manuals/, suffix=.json
No external dependencies — pure Python + boto3.
"""

import json
import os
import re
import urllib.parse

import boto3

GOLD_BUCKET = os.environ["GOLD_BUCKET"]
KB_ID = os.environ.get("KB_ID", "")
DS_ID = os.environ.get("DS_ID", "")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

CHUNK_SIZE = 2000   # characters (~512 tokens)
OVERLAP = 200       # characters of context carried between chunks

s3 = boto3.client("s3")


def split_chunks(text: str) -> list:
    """Split text into overlapping chunks on natural boundaries."""
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        if end < n:
            search_from = start + int(CHUNK_SIZE * 0.8)
            best = end
            idx = text.rfind("\n\n", search_from, end)
            if idx != -1:
                best = idx + 2
            else:
                idx = text.rfind("\n", search_from, end)
                if idx != -1:
                    best = idx + 1
                else:
                    m = None
                    for m in re.finditer(r"[.!?]\s+", text[search_from:end]):
                        pass
                    if m:
                        best = search_from + m.end()
            end = best
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(start + 1, end - OVERLAP)
    return chunks


def format_chunk(equipment_id, source_key, chunk_index, total, text):
    source_file = source_key.split("/")[-1]
    return (
        f"[METADATA]\n"
        f"Equipment: {equipment_id}\n"
        f"Source: {source_file}\n"
        f"Chunk: {chunk_index} of {total}\n"
        f"[CONTENT]\n"
        f"{text}"
    )


def handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        if not key.endswith(".json"):
            print(f"Skipping non-JSON: {key}")
            continue

        print(f"Processing s3://{bucket}/{key}")

        # Load Silver document
        obj = s3.get_object(Bucket=bucket, Key=key)
        doc = json.loads(obj["Body"].read())

        equipment_id = doc.get("equipment_id", "UNKNOWN")
        full_text = doc.get("full_text", "")

        if not full_text:
            print(f"  WARNING: no text content, skipping")
            continue

        # Chunk and write to Gold
        chunks = split_chunks(full_text)
        total = len(chunks)
        print(f"  {len(full_text)} chars -> {total} chunks")

        for i, chunk_text in enumerate(chunks, 1):
            gold_content = format_chunk(equipment_id, key, i, total, chunk_text)
            gold_key = f"manuals/{equipment_id}_chunk_{i:04d}.txt"
            s3.put_object(
                Bucket=GOLD_BUCKET,
                Key=gold_key,
                Body=gold_content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )

        print(f"  -> s3://{GOLD_BUCKET}/manuals/{equipment_id}_chunk_*.txt ({total} files)")

        # Trigger KB ingestion if Knowledge Base is enabled
        if KB_ID and DS_ID:
            try:
                agent = boto3.client("bedrock-agent", region_name=AWS_REGION)
                resp = agent.start_ingestion_job(
                    knowledgeBaseId=KB_ID,
                    dataSourceId=DS_ID,
                    description=f"Auto-ingestion triggered by {equipment_id} ETL",
                )
                job_id = resp["ingestionJob"]["ingestionJobId"]
                print(f"  KB ingestion started: {job_id}")
            except Exception as exc:
                # Non-fatal: Gold data is written, ingestion can be retried manually
                print(f"  WARNING: KB ingestion trigger failed: {exc}")
        else:
            print("  KB disabled (KB_ID not set) - skipping ingestion trigger")

    return {"statusCode": 200}
