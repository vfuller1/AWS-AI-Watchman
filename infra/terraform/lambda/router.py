"""
Bronze Layer Router — AWS AI Watchman
Triggered by S3 ObjectCreated events on the Bronze bucket.
Inspects each new file's extension and copies it into the correct
typed sub-folder (manuals/, telemetry/, service-logs/) so downstream
Glue Crawlers and Silver-layer processing can operate on uniform prefixes.
"""

import json
import urllib.parse
import boto3

s3 = boto3.client("s3")

ROUTING_MAP = {
    ".pdf":  "manuals/",
    ".csv":  "telemetry/",
    ".json": "service-logs/",
}
DEFAULT_PREFIX = "unclassified/"


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

    result = {"routed": routed, "skipped": skipped}
    print(json.dumps(result))
    return {"statusCode": 200, "body": json.dumps(result)}
