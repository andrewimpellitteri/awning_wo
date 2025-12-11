#!/usr/bin/env python3
"""
Embedding Sync Script for DeepSeek + Local Embeddings

This script synchronizes embeddings for all customers, work orders, and items
in the database using local sentence-transformers embeddings.

Usage:
    python scripts/sync_embeddings.py [--type TYPE] [--batch-size N]

Options:
    --type TYPE       Sync only specific type: customers, work_orders, items, or all (default: all)
    --batch-size N    Number of records to process in each batch (default: 100)
    --verbose         Print detailed progress

Environment Variables:
    TEST_DB           PostgreSQL connection string for the database
    DEEPSEEK_API_KEY  DeepSeek API key (for chat, not embeddings)
    LOCAL_EMBED_MODEL Local embedding model (default: all-MiniLM-L6-v2)

Example:
    export TEST_DB="postgresql://user:pass@localhost:5432/dbname"
    python scripts/sync_embeddings.py --type customers --verbose
"""

import os
import sys
import argparse
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from services.rag_service import (
    sync_customer_embedding,
    sync_work_order_embedding,
    sync_item_embedding,
    check_deepseek_status,  # Changed from check_ollama_status
    DeepSeekError,  # Changed from OllamaError
)
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding


def log(message, verbose=True):
    """Print timestamped log message."""
    if verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")


def sync_customers(verbose=False):
    """Sync embeddings for all customers."""
    log("Starting customer embedding sync...", verbose)

    customers = Customer.query.all()
    total = len(customers)
    synced = 0
    failed = 0

    for i, customer in enumerate(customers, 1):
        try:
            if sync_customer_embedding(customer.CustID):
                synced += 1
            else:
                failed += 1
                log(f"  Failed to sync customer {customer.CustID}", verbose)
        except Exception as e:
            failed += 1
            log(f"  Error syncing customer {customer.CustID}: {e}", verbose)

        if verbose and i % 50 == 0:
            log(f"  Progress: {i}/{total} customers processed")

    log(f"Customer sync complete: {synced} synced, {failed} failed", verbose)
    return synced, failed


def sync_work_orders(verbose=False):
    """Sync embeddings for all work orders."""
    log("Starting work order embedding sync...", verbose)

    work_orders = WorkOrder.query.all()
    total = len(work_orders)
    synced = 0
    failed = 0

    for i, wo in enumerate(work_orders, 1):
        try:
            if sync_work_order_embedding(wo.WorkOrderNo):
                synced += 1
            else:
                failed += 1
                log(f"  Failed to sync work order {wo.WorkOrderNo}", verbose)
        except Exception as e:
            failed += 1
            log(f"  Error syncing work order {wo.WorkOrderNo}: {e}", verbose)

        if verbose and i % 50 == 0:
            log(f"  Progress: {i}/{total} work orders processed")

    log(f"Work order sync complete: {synced} synced, {failed} failed", verbose)
    return synced, failed


def sync_items(verbose=False):
    """Sync embeddings for all work order items."""
    log("Starting item embedding sync...", verbose)

    items = WorkOrderItem.query.all()
    total = len(items)
    synced = 0
    failed = 0

    for i, item in enumerate(items, 1):
        try:
            if sync_item_embedding(item.id):
                synced += 1
            else:
                failed += 1
                log(f"  Failed to sync item {item.id}", verbose)
        except Exception as e:
            failed += 1
            log(f"  Error syncing item {item.id}: {e}", verbose)

        if verbose and i % 100 == 0:
            log(f"  Progress: {i}/{total} items processed")

    log(f"Item sync complete: {synced} synced, {failed} failed", verbose)
    return synced, failed


def print_status():
    """Print current DeepSeek and embedding status."""
    status = check_deepseek_status()  # Changed from check_ollama_status

    print("\n=== DeepSeek Status ===")
    print(f"API Available: {'Yes' if status['api_available'] else 'No'}")
    print(f"API Configured: {'Yes' if status['api_configured'] else 'No'}")
    print(
        f"Chat Model ({status['chat_model']}): {'Available' if status.get('chat_model_available') else 'Unknown'}"
    )

    print("\n=== Local Embedding Status ===")
    print(f"Embed Model: {status['embed_model']}")
    print(f"Embed Model Local: {'Yes' if status['embed_model_local'] else 'No'}")
    print(f"Embed Dimension: {status['embed_dimension']}")

    print("\n=== Embedding Counts ===")
    print(f"Customers: {CustomerEmbedding.query.count()}")
    print(f"Work Orders: {WorkOrderEmbedding.query.count()}")
    print(f"Items: {ItemEmbedding.query.count()}")

    print("\n=== Database Record Counts ===")
    print(f"Total Customers: {Customer.query.count()}")
    print(f"Total Work Orders: {WorkOrder.query.count()}")
    print(f"Total Items: {WorkOrderItem.query.count()}")


def main():
    parser = argparse.ArgumentParser(description="Sync embeddings for RAG chatbot")
    parser.add_argument(
        "--type",
        choices=["customers", "work_orders", "items", "all"],
        default="all",
        help="Type of records to sync (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print detailed progress"
    )
    parser.add_argument(
        "--status", action="store_true", help="Print current status and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Check status without syncing"
    )

    args = parser.parse_args()

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Check DeepSeek status first
        status = check_deepseek_status()  # Changed from check_ollama_status

        if args.status or args.dry_run:
            print_status()
            if args.dry_run:
                print("\nDry run complete. No embeddings were synced.")
            return

        # For local embeddings, we don't need to check if a service is running
        # But we should check if the API key is configured for chat functionality
        if not status["api_configured"]:
            print("WARNING: DEEPSEEK_API_KEY is not configured")
            print(
                "Chat functionality will not work, but embeddings will still be synced"
            )
            response = input("Continue with embedding sync? (y/n): ")
            if response.lower() != "y":
                sys.exit(1)

        log("Starting embedding sync...", args.verbose)
        start_time = time.time()

        stats = {
            "customers_synced": 0,
            "customers_failed": 0,
            "work_orders_synced": 0,
            "work_orders_failed": 0,
            "items_synced": 0,
            "items_failed": 0,
        }

        try:
            if args.type in ["customers", "all"]:
                synced, failed = sync_customers(args.verbose)
                stats["customers_synced"] = synced
                stats["customers_failed"] = failed

            if args.type in ["work_orders", "all"]:
                synced, failed = sync_work_orders(args.verbose)
                stats["work_orders_synced"] = synced
                stats["work_orders_failed"] = failed

            if args.type in ["items", "all"]:
                synced, failed = sync_items(args.verbose)
                stats["items_synced"] = synced
                stats["items_failed"] = failed

        except KeyboardInterrupt:
            log("\nSync interrupted by user", args.verbose)
            sys.exit(1)

        elapsed = time.time() - start_time

        print("\n=== Sync Complete ===")
        print(f"Time elapsed: {elapsed}")
