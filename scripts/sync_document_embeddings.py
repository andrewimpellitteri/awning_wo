#!/usr/bin/env python3
"""
Script to sync document embeddings from S3 work order files using AWS Textract OCR.

This script extracts text from images and PDFs attached to work orders,
creates embeddings, and stores them for RAG search.

Usage:
    # Sync all documents that don't have embeddings yet
    python scripts/sync_document_embeddings.py

    # Show stats only (don't process)
    python scripts/sync_document_embeddings.py --stats

    # Process specific work order
    python scripts/sync_document_embeddings.py --work-order WO12345

    # Process specific file by ID
    python scripts/sync_document_embeddings.py --file-id 123

    # Re-process all (including already embedded)
    python scripts/sync_document_embeddings.py --force

Environment Variables:
    DATABASE_URL       PostgreSQL connection string
    AWS_ACCESS_KEY_ID  AWS credentials
    AWS_SECRET_ACCESS_KEY
    AWS_S3_BUCKET     S3 bucket name
    AWS_REGION        AWS region (default: us-east-1)
"""

import os
import sys
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models.work_order_file import WorkOrderFile
from models.embeddings import DocumentEmbedding
from services.document_ocr_service import (
    sync_document_embedding,
    sync_all_document_embeddings,
    get_document_stats,
    is_ocr_supported,
)


def print_stats():
    """Print current document embedding statistics."""
    stats = get_document_stats()

    print("\n=== Document Embedding Statistics ===")
    print(f"Total S3 files:     {stats['total_s3_files']}")
    print(f"Already embedded:   {stats['total_embedded']}")
    print(f"Pending:            {stats['pending']}")
    print(f"Average confidence: {stats['average_confidence']}%")

    if stats['by_method']:
        print("\nBy OCR method:")
        for method, count in stats['by_method'].items():
            print(f"  {method or 'unknown'}: {count}")

    # Show file type breakdown
    s3_files = WorkOrderFile.query.filter(
        WorkOrderFile.file_path.like('s3://%')
    ).all()

    ext_counts = {}
    for f in s3_files:
        ext = os.path.splitext(f.filename)[1].lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    print("\nFile types in S3:")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        supported = "✓" if is_ocr_supported(f"test{ext}") else "✗"
        print(f"  {ext or '(no ext)'}: {count} {supported}")

    print()


def sync_single_file(file_id: int):
    """Sync embedding for a single file."""
    wo_file = WorkOrderFile.query.get(file_id)
    if not wo_file:
        print(f"File not found: {file_id}")
        return False

    print(f"Processing: {wo_file.filename} (WO: {wo_file.WorkOrderNo})")
    success = sync_document_embedding(file_id)

    if success:
        print("✓ Successfully processed")
    else:
        print("✗ Failed to process")

    return success


def sync_work_order_files(work_order_no: str):
    """Sync embeddings for all files in a work order."""
    files = WorkOrderFile.query.filter_by(WorkOrderNo=work_order_no).all()

    if not files:
        print(f"No files found for work order: {work_order_no}")
        return

    print(f"Found {len(files)} files for work order {work_order_no}")

    success_count = 0
    for wo_file in files:
        if not wo_file.file_path.startswith('s3://'):
            print(f"  Skipping (not on S3): {wo_file.filename}")
            continue

        if not is_ocr_supported(wo_file.filename):
            print(f"  Skipping (unsupported type): {wo_file.filename}")
            continue

        print(f"  Processing: {wo_file.filename}")
        if sync_document_embedding(wo_file.id):
            success_count += 1

    print(f"\nProcessed {success_count}/{len(files)} files successfully")


def sync_all(force: bool = False):
    """Sync all pending documents."""
    if force:
        # Delete existing embeddings and re-process
        print("Force mode: Deleting existing embeddings...")
        DocumentEmbedding.query.delete()
        db.session.commit()

    print("Syncing document embeddings...")
    print("This may take a while for large document collections.\n")

    stats = sync_all_document_embeddings()

    print("\n=== Sync Results ===")
    print(f"Total files:        {stats['total_files']}")
    print(f"Processed:          {stats['processed']}")
    print(f"Skipped:            {stats['skipped']}")
    print(f"Failed:             {stats['failed']}")
    print(f"Already embedded:   {stats['already_embedded']}")

    if stats['errors']:
        print("\nErrors encountered:")
        for err in stats['errors'][:10]:
            print(f"  - {err}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more errors")


def main():
    parser = argparse.ArgumentParser(
        description="Sync document embeddings from S3 files using AWS Textract OCR"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics only, don't process"
    )
    parser.add_argument(
        "--file-id",
        type=int,
        help="Process a specific file by ID"
    )
    parser.add_argument(
        "--work-order",
        type=str,
        help="Process all files for a specific work order"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process all files, even if already embedded"
    )

    args = parser.parse_args()

    # Create Flask app context
    app = create_app()
    with app.app_context():
        print("=== Document Embedding Sync ===")
        print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[-1] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else 'local'}")
        print(f"S3 Bucket: {os.environ.get('AWS_S3_BUCKET', 'not set')}")

        if args.stats:
            print_stats()
        elif args.file_id:
            sync_single_file(args.file_id)
        elif args.work_order:
            sync_work_order_files(args.work_order)
        else:
            sync_all(force=args.force)


if __name__ == "__main__":
    main()
