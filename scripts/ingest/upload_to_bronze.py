"""
upload_to_bronze.py — AWS AI Watchman
Uploads all files in the local data/ directory to the Bronze S3 bucket.
The Lambda router will automatically move each file into its typed
sub-folder (manuals/, telemetry/, service-logs/) based on extension.

Usage:
    python upload_to_bronze.py
    python upload_to_bronze.py --bucket aws-ai-watchman-dev-bronze-raw
    python upload_to_bronze.py --data-dir data --dry-run
"""

import argparse
import mimetypes
import sys
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    raise SystemExit("Run: pip install -r requirements.txt")

# Default bucket name — matches Terraform output bronze_bucket_name
DEFAULT_BUCKET = "aws-ai-watchman-dev-bronze-raw"

# Extensions we recognise; others still upload but go to unclassified/
KNOWN_EXTENSIONS = {".pdf", ".csv", ".json"}


def _file_label(path: Path) -> str:
    """Human-readable size label."""
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def upload_directory(bucket: str, data_dir: Path, dry_run: bool) -> None:
    files = [f for f in sorted(data_dir.rglob("*")) if f.is_file()]

    if not files:
        print(f"WARN   No files found in {data_dir}  — nothing to upload.")
        return

    print(f"\n{'DRY RUN — ' if dry_run else ''}Uploading {len(files)} file(s) to s3://{bucket}/\n")

    s3 = None if dry_run else boto3.client("s3")
    success = errors = 0

    for fpath in files:
        # S3 key = filename only (Lambda router handles sub-folder placement)
        key = fpath.name
        size_label = _file_label(fpath)
        ext = fpath.suffix.lower()
        content_type, _ = mimetypes.guess_type(str(fpath))
        content_type = content_type or "application/octet-stream"

        routed_to = (
            "manuals/"      if ext == ".pdf"  else
            "telemetry/"    if ext == ".csv"  else
            "service-logs/" if ext == ".json" else
            "unclassified/"
        )

        status = "-> (dry-run)" if dry_run else "-> uploading"
        print(f"  {fpath.name:<45} {size_label:>8}   {status} s3://{bucket}/{key}")
        print(f"  {'':45} {'':>8}   Lambda will route to: {routed_to}")

        if dry_run:
            success += 1
            continue

        try:
            s3.upload_file(
                str(fpath),
                bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            success += 1
        except (BotoCoreError, ClientError) as exc:
            print(f"  ERROR  FAILED: {exc}")
            errors += 1

    print(f"\n{'-' * 60}")
    print(f"  Uploaded : {success}")
    if errors:
        print(f"  Errors   : {errors}")
    if dry_run:
        print("  (Dry run — no files were actually uploaded)")
    print()


def verify_bucket_exists(bucket: str) -> None:
    """Quick head-bucket call to catch credential or name issues early."""
    try:
        boto3.client("s3").head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "404":
            raise SystemExit(
                f"ERROR  Bucket '{bucket}' not found. "
                "Run `terraform apply` first or check the bucket name."
            )
        elif code in ("403", "401"):
            raise SystemExit(
                f"ERROR  Access denied to '{bucket}'. "
                "Check your AWS credentials and IAM permissions."
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload local data files to the Bronze S3 layer."
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"Bronze S3 bucket name (default: {DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Local directory containing files to upload (default: data/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be uploaded without sending anything to S3",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(
            f"ERROR  Data directory '{data_dir}' not found.\n"
            "    Run generate_telemetry.py and generate_maintenance.py first,\n"
            "    then place any OEM PDF manuals in data/."
        )

    if not args.dry_run:
        print(f"Verifying access to s3://{args.bucket}/ …")
        verify_bucket_exists(args.bucket)

    upload_directory(args.bucket, data_dir, args.dry_run)

    if not args.dry_run:
        print(
            f"OK  Upload complete.\n"
            f"    The Bronze Router Lambda will sort files into typed sub-folders.\n"
            f"    Check CloudWatch logs for: /aws/lambda/aws-ai-watchman-dev-bronze-router\n"
            f"\n"
            f"    To run the Glue Crawler and catalogue the schema:\n"
            f"    aws glue start-crawler --name aws-ai-watchman-dev-bronze-crawler\n"
        )


if __name__ == "__main__":
    main()
