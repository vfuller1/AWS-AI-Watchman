#!/usr/bin/env python3
"""
AWS AI Watchman - Silver to Gold ETL: Manual Chunking
======================================================
Reads extracted-text JSON from the Silver bucket, chunks the content
into overlapping segments suitable for Bedrock Knowledge Base vector
ingestion, and writes individual .txt files to the Gold bucket.

Chunking strategy:
  - Target size: 512 tokens (~2,000 characters, ~350 words)
  - Overlap:     10% (50 tokens / 200 characters)
  - Split on:    section boundaries first, then paragraph breaks, then sentences
  - Metadata:    equipment_id, source manual, chunk index embedded in filename

Gold file naming: manuals/{equipment_id}_chunk_{n:04d}.txt
Gold file format:
  [METADATA]
  Equipment: CAT-EX | Caterpillar 320 Hydraulic Excavator
  Source: CAT-EX_service_manual.pdf
  Chunk: 3 of 18
  [CONTENT]
  <text content>

Bedrock Knowledge Base ingests these .txt files and embeds them with
Titan Embed Text v2 into the OpenSearch Serverless vector index.

Usage:
    python silver_to_gold.py
    python silver_to_gold.py --chunk-size 2000 --overlap 200
    python silver_to_gold.py --dry-run
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import boto3

SILVER_BUCKET = "aws-ai-watchman-dev-silver-cleaned"
GOLD_BUCKET = "aws-ai-watchman-dev-gold-vector-ready"
SILVER_PREFIX = "manuals/"
GOLD_PREFIX = "manuals/"

DEFAULT_CHUNK_SIZE = 2000   # characters (~350 words, ~512 tokens)
DEFAULT_OVERLAP = 200       # characters of context carried between chunks


# ---------------------------------------------------------------------------
# Chunking logic
# ---------------------------------------------------------------------------
def split_into_chunks(text: str, chunk_size: int, overlap: int) -> list:
    """
    Split text into overlapping chunks, preferring section/paragraph boundaries.

    Priority order:
      1. Double newline (paragraph / section break)
      2. Single newline
      3. Sentence end (. or ? or !)
      4. Hard cut at chunk_size

    Each chunk carries `overlap` characters from the previous chunk as context.
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len:
            # Try to break at a nice boundary within the last 20% of the chunk
            search_from = start + int(chunk_size * 0.8)
            best_break = end

            # 1. Paragraph break (\n\n)
            idx = text.rfind("\n\n", search_from, end)
            if idx != -1:
                best_break = idx + 2
            else:
                # 2. Single newline
                idx = text.rfind("\n", search_from, end)
                if idx != -1:
                    best_break = idx + 1
                else:
                    # 3. Sentence boundary
                    m = None
                    for m in re.finditer(r"[.!?]\s+", text[search_from:end]):
                        pass
                    if m:
                        best_break = search_from + m.end()

            end = best_break

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(chunk_text)

        # Next chunk starts with overlap from this chunk's end
        start = max(start + 1, end - overlap)

    return chunks


def format_gold_chunk(
    equipment_id: str,
    model: str,
    source_key: str,
    chunk_index: int,
    total_chunks: int,
    text: str,
) -> str:
    """
    Wrap chunk text with metadata header for Knowledge Base context.
    The metadata helps the LLM understand which document/equipment a
    retrieved chunk came from.
    """
    source_filename = source_key.split("/")[-1]
    return "\n".join([
        "[METADATA]",
        f"Equipment: {equipment_id} | {model}",
        f"Source: {source_filename}",
        f"Chunk: {chunk_index} of {total_chunks}",
        "[CONTENT]",
        text,
    ])


# ---------------------------------------------------------------------------
# ETL pipeline
# ---------------------------------------------------------------------------
def list_silver_manuals(s3, bucket: str) -> list:
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=SILVER_PREFIX)
    return [
        obj["Key"]
        for obj in resp.get("Contents", [])
        if obj["Key"].endswith(".json")
    ]


def process_manual(
    s3,
    silver_bucket: str,
    gold_bucket: str,
    key: str,
    chunk_size: int,
    overlap: int,
    dry_run: bool,
) -> dict:
    print(f"  Processing {key} ...")

    # Read Silver JSON
    obj = s3.get_object(Bucket=silver_bucket, Key=key)
    doc = json.loads(obj["Body"].read())

    equipment_id = doc.get("equipment_id", "UNKNOWN")
    model = doc.get("model", "Unknown Model")
    source_key = doc.get("source_key", key)
    full_text = doc.get("full_text", "")

    if not full_text:
        print(f"    WARNING: no text content in {key}, skipping")
        return {"key": key, "chunks": 0, "skipped": True}

    # Chunk the text
    raw_chunks = split_into_chunks(full_text, chunk_size, overlap)
    total = len(raw_chunks)
    print(f"    {len(full_text)} chars -> {total} chunks ({chunk_size} char target, {overlap} overlap)")

    # Write each chunk to Gold
    written = 0
    for i, chunk_text in enumerate(raw_chunks, 1):
        gold_content = format_gold_chunk(
            equipment_id=equipment_id,
            model=model,
            source_key=source_key,
            chunk_index=i,
            total_chunks=total,
            text=chunk_text,
        )
        gold_key = f"{GOLD_PREFIX}{equipment_id}_chunk_{i:04d}.txt"

        if dry_run:
            print(f"    [DRY RUN] would write s3://{gold_bucket}/{gold_key} ({len(gold_content)} chars)")
        else:
            s3.put_object(
                Bucket=gold_bucket,
                Key=gold_key,
                Body=gold_content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
        written += 1

    if not dry_run:
        print(f"    Wrote {written} chunks to s3://{gold_bucket}/{GOLD_PREFIX}{equipment_id}_chunk_*.txt")

    return {
        "key": key,
        "equipment_id": equipment_id,
        "model": model,
        "input_chars": len(full_text),
        "chunks": total,
        "skipped": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Silver -> Gold ETL: chunk manuals for KB ingestion")
    parser.add_argument("--silver-bucket", default=SILVER_BUCKET)
    parser.add_argument("--gold-bucket", default=GOLD_BUCKET)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                        help=f"Target chunk size in characters (default {DEFAULT_CHUNK_SIZE})")
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP,
                        help=f"Overlap between chunks in characters (default {DEFAULT_OVERLAP})")
    parser.add_argument("--dry-run", action="store_true", help="Skip S3 writes")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)

    # Discover Silver JSON files
    keys = list_silver_manuals(s3, args.silver_bucket)
    if not keys:
        print(f"No JSON files found under s3://{args.silver_bucket}/{SILVER_PREFIX}")
        print("Run: python scripts/etl/bronze_to_silver.py")
        sys.exit(1)

    print(f"Found {len(keys)} extracted manual(s) in Silver")
    print(f"Chunking: {args.chunk_size} chars target, {args.overlap} chars overlap")
    print()

    results = []
    errors = []
    for key in keys:
        try:
            r = process_manual(
                s3, args.silver_bucket, args.gold_bucket,
                key, args.chunk_size, args.overlap, args.dry_run
            )
            results.append(r)
        except Exception as exc:
            print(f"  ERROR: {key}: {exc}")
            errors.append({"key": key, "error": str(exc)})

    # Summary
    total_chunks = sum(r["chunks"] for r in results if not r.get("skipped"))
    print()
    print("-" * 60)
    print(f"Manuals processed : {len(results)}")
    print(f"Total chunks      : {total_chunks}")
    if errors:
        print(f"Errors            : {len(errors)}")
    print()
    for r in results:
        if not r.get("skipped"):
            print(f"  {r['equipment_id']:10s} | {r['input_chars']:6d} chars | {r['chunks']:3d} chunks")

    print()
    if not args.dry_run:
        print(f"OK  Gold layer ready: {total_chunks} document chunks in s3://{args.gold_bucket}/{GOLD_PREFIX}")
        print()
        print("Next steps:")
        print("  1. Enable KB:  terraform apply -var=enable_bedrock_kb=true")
        print("  2. Trigger ingestion job from the AWS Console or:")
        print("     aws bedrock-agent start-ingestion-job \\")
        print("       --knowledge-base-id <KB_ID> \\")
        print("       --data-source-id <DS_ID>")
    else:
        print("DRY RUN complete — no files written.")


if __name__ == "__main__":
    main()
