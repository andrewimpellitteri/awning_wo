#!/usr/bin/env python3
# Create a file: scripts/sync_embeddings_minimal.py

import os
import sys
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
    check_deepseek_status,
)
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.embeddings import CustomerEmbedding, WorkOrderEmbedding, ItemEmbedding


def log(message):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def main():
    log("Starting minimal embedding sync...")

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Check status
        log("Checking DeepSeek status...")
        status = check_deepseek_status()
        log(f"API Available: {status.get('api_available', 'Unknown')}")
        log(f"Embed Model: {status.get('embed_model', 'Unknown')}")

        # Check database counts
        log("Checking database counts...")
        customer_count = Customer.query.count()
        work_order_count = WorkOrder.query.count()
        item_count = WorkOrderItem.query.count()

        log(
            f"Found {customer_count} customers, {work_order_count} work orders, {item_count} items"
        )

        # Check embedding counts
        customer_embed_count = CustomerEmbedding.query.count()
        work_order_embed_count = WorkOrderEmbedding.query.count()
        item_embed_count = ItemEmbedding.query.count()

        log(
            f"Found {customer_embed_count} customer embeddings, {work_order_embed_count} work order embeddings, {item_embed_count} item embeddings"
        )

        # Try to sync one customer
        log("Attempting to sync one customer...")
        customer = Customer.query.first()
        if customer:
            log(f"Trying to sync customer {customer.CustID}...")
            try:
                result = sync_customer_embedding(customer.CustID)
                log(f"Sync result: {result}")
            except Exception as e:
                log(f"Error syncing customer: {e}")
                import traceback

                traceback.print_exc()
        else:
            log("No customers found in database")

        log("Minimal sync complete")


if __name__ == "__main__":
    main()
