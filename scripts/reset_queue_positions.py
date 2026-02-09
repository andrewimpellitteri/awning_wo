#!/usr/bin/env python3
"""
One-time script to reset queue positions after deploying the FIFO ordering fix.

This script clears all queue positions and re-initializes them using the corrected
FIFO ordering logic. It should be run once after deploying the queue fix.

Usage:
    python scripts/reset_queue_positions.py          # Reset the queue
    python scripts/reset_queue_positions.py --preview   # Preview only, don't change anything
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from extensions import db
from models.work_order import WorkOrder
from sqlalchemy import and_, or_
from routes.queue import initialize_queue_positions_for_unassigned


def preview_queue():
    """Show current queue state without making changes."""
    with app.app_context():
        base_filter = and_(
            WorkOrder.DateCompleted.is_(None),
            WorkOrder.Clean.is_(None),
            WorkOrder.Treat.is_(None),
            WorkOrder.Quote == 'Approved'
        )

        # Get all orders in queue
        orders = WorkOrder.query.filter(base_filter).order_by(
            WorkOrder.QueuePosition.asc().nullslast()
        ).all()

        print(f"\n{'='*80}")
        print(f"CURRENT QUEUE STATE ({len(orders)} orders)")
        print(f"{'='*80}\n")

        # Group by priority
        firm_rush = [o for o in orders if o.FirmRush]
        rush = [o for o in orders if o.RushOrder and not o.FirmRush]
        regular = [o for o in orders if not o.RushOrder and not o.FirmRush]

        def print_orders(title, order_list):
            print(f"\n{title} ({len(order_list)} orders):")
            print("-" * 70)
            if not order_list:
                print("  (none)")
                return
            for o in order_list[:20]:  # Show first 20
                pos = o.QueuePosition if o.QueuePosition else "NULL"
                print(f"  Pos {pos:>4} | {o.WorkOrderNo:<10} | {str(o.DateIn):<12} | {(o.WOName or '')[:30]}")
            if len(order_list) > 20:
                print(f"  ... and {len(order_list) - 20} more")

        print_orders("FIRM RUSH (sorted by DateRequired)", firm_rush)
        print_orders("RUSH (should be sorted by DateIn - FIFO)", rush)
        print_orders("REGULAR (should be sorted by DateIn - FIFO)", regular)

        # Check for FIFO violations in regular orders
        print(f"\n{'='*80}")
        print("FIFO VIOLATIONS (regular orders out of DateIn order):")
        print("-" * 70)

        violations = []
        sorted_regular = sorted(regular, key=lambda o: o.QueuePosition or 9999)
        for i, o in enumerate(sorted_regular[:-1]):
            next_o = sorted_regular[i + 1]
            if o.DateIn and next_o.DateIn and o.DateIn > next_o.DateIn:
                violations.append((o, next_o))

        if violations:
            for curr, next_o in violations[:10]:
                print(f"  {curr.WOName[:25]:<25} (DateIn: {curr.DateIn}, Pos: {curr.QueuePosition})")
                print(f"    is BEFORE")
                print(f"  {next_o.WOName[:25]:<25} (DateIn: {next_o.DateIn}, Pos: {next_o.QueuePosition})")
                print()
            if len(violations) > 10:
                print(f"  ... and {len(violations) - 10} more violations")
        else:
            print("  No FIFO violations found!")

        print(f"\n{'='*80}\n")
        return True


def reset_queue_positions():
    """Reset all queue positions and re-initialize with correct FIFO ordering."""
    with app.app_context():
        try:
            # Base filter for queue-eligible orders
            base_filter = and_(
                WorkOrder.DateCompleted.is_(None),
                WorkOrder.Clean.is_(None),
                WorkOrder.Treat.is_(None),
                WorkOrder.Quote == 'Approved'
            )

            # Count current queue
            total_in_queue = WorkOrder.query.filter(base_filter).count()
            print(f"Found {total_in_queue} work orders in queue")

            if total_in_queue == 0:
                print("No work orders in queue, nothing to reset")
                return True

            # Clear all existing queue positions
            cleared = WorkOrder.query.filter(base_filter).update(
                {WorkOrder.QueuePosition: None}
            )
            db.session.commit()
            print(f"Cleared {cleared} queue positions")

            # Re-initialize with correct FIFO ordering
            initialized = initialize_queue_positions_for_unassigned()
            print(f"Re-initialized {initialized} queue positions with correct FIFO ordering")

            # Verify the result
            firm_rush_count = WorkOrder.query.filter(
                base_filter,
                WorkOrder.FirmRush == True
            ).count()
            rush_count = WorkOrder.query.filter(
                base_filter,
                WorkOrder.RushOrder == True,
                or_(WorkOrder.FirmRush == False, WorkOrder.FirmRush.is_(None))
            ).count()
            regular_count = WorkOrder.query.filter(
                base_filter,
                or_(WorkOrder.RushOrder == False, WorkOrder.RushOrder.is_(None)),
                or_(WorkOrder.FirmRush == False, WorkOrder.FirmRush.is_(None))
            ).count()

            print(f"\nQueue summary:")
            print(f"  Firm Rush: {firm_rush_count}")
            print(f"  Rush: {rush_count}")
            print(f"  Regular: {regular_count}")
            print(f"  Total: {firm_rush_count + rush_count + regular_count}")

            print("\nQueue reset complete!")
            return True

        except Exception as e:
            db.session.rollback()
            print(f"ERROR: Failed to reset queue positions: {e}")
            return False


if __name__ == "__main__":
    if "--preview" in sys.argv:
        success = preview_queue()
    else:
        success = reset_queue_positions()
    sys.exit(0 if success else 1)
