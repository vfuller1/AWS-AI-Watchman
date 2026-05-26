"""
Bronze Layer Router — AWS AI Watchman
Triggered by S3 ObjectCreated events on the Bronze bucket.
Inspects each new file's extension and copies it into the correct
typed sub-folder (manuals/, telemetry/, service-logs/) so downstream
Glue Crawlers and Silver-layer processing can operate on uniform prefixes.

ETL trigger:
  S3 does not allow overlapping notification rules on the same bucket
  (a no-filter rule for the router + a prefix-filtered rule for ETL would
  conflict).  Instead, after routing a PDF to manuals/ this function invokes
  etl_bronze_to_silver directly with InvocationType="Event" (async,
  fire-and-forget — no latency impact on the router's own response).
  The Lambda permission and IAM role for this are already in place.
"""

import json
import os
import urllib.parse
import boto3

s3     = boto3.client("s3")
lambda_client = boto3.client("lambda")

ROUTING_MAP = {
    ".pdf":  "manuals/",
    ".csv":  "telemetry/",
    ".json": "service-logs/",
}
DEFAULT_PREFIX = "unclassified/"

# ARN of the ETL Lambda to invoke after routing a PDF — set in Terraform env vars
ETL_BRONZE_TO_SILVER_ARN = os.environ.get("ETL_BRONZE_TO_SILVER_ARN", "")


def handler(event, context):
    routed = []
    skipped = []

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key    = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        # Skip objects already in a typed sub-folder to prevent re-trigger loops
        if "/" in key:
            skipped.append(key)
            continue

        ext    = "." + key.rsplit(".", 1)[-1].lower() if "." in key else ""
        prefix = ROUTING_MAP.get(ext, DEFAULT_PREFIX)
        dest   = f"{prefix}{key}"

        s3.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": key},
            Key=dest,
        )
        s3.delete_object(Bucket=bucket, Key=key)
        routed.append({"source": key, "destination": dest})

        # Kick off ETL immediately after routing a PDF to manuals/
        # Async invoke — router returns instantly, ETL runs independently
        if ext == ".pdf" and ETL_BRONZE_TO_SILVER_ARN:
            payload = json.dumps({
                "Records": [{
                    "s3": {
                        "bucket": {"name": bucket},
                        "object": {"key": urllib.parse.quote_plus(dest)}
                    }
                }]
            }).encode()
            lambda_client.invoke(
                FunctionName=ETL_BRONZE_TO_SILVER_ARN,
                InvocationType="Event",   # fire-and-forget, no latency impact
                Payload=payload,
            )
            print(json.dumps({"etl_triggered": dest}))

    result = {"routed": routed, "skipped": skipped}
    print(json.dumps(result))
    return {"statusCode": 200, "body": json.dumps(result)}
