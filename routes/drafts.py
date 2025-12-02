"""
Draft management routes for auto-save functionality.
Handles saving, loading, and deleting user-specific form drafts.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.work_order_draft import WorkOrderDraft
from datetime import datetime

drafts_bp = Blueprint("drafts", __name__, url_prefix="/api/drafts")


@drafts_bp.route("/save", methods=["POST"])
@login_required
def save_draft():
    """
    Save or update a draft for the current user.

    POST body (JSON):
    {
        "form_type": "work_order",
        "form_data": {
            "CustID": "12345",
            "WOName": "Test Order",
            ...
        },
        "draft_id": 123  // Optional: if updating existing draft
    }

    Returns:
        JSON with draft_id and status
    """
    try:
        data = request.get_json()

        if not data or "form_data" not in data:
            return jsonify({"error": "Missing form_data"}), 400

        form_type = data.get("form_type", "work_order")
        form_data = data.get("form_data")
        draft_id = data.get("draft_id")

        # Update existing draft or create new one
        if draft_id:
            draft = WorkOrderDraft.query.filter_by(
                id=draft_id,
                user_id=current_user.id
            ).first()

            if draft:
                draft.form_data = form_data
                draft.updated_at = datetime.utcnow()
            else:
                # Draft not found, create new one
                draft = WorkOrderDraft(
                    user_id=current_user.id,
                    form_type=form_type,
                    form_data=form_data
                )
                db.session.add(draft)
        else:
            # Create new draft
            draft = WorkOrderDraft(
                user_id=current_user.id,
                form_type=form_type,
                form_data=form_data
            )
            db.session.add(draft)

        db.session.commit()

        # Clean up old drafts (keep only 5 most recent)
        WorkOrderDraft.cleanup_old_drafts(current_user.id, keep_most_recent=5)

        return jsonify({
            "success": True,
            "draft_id": draft.id,
            "message": "Draft saved successfully",
            "updated_at": draft.updated_at.isoformat()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "message": "Failed to save draft"
        }), 500


@drafts_bp.route("/list", methods=["GET"])
@login_required
def list_drafts():
    """
    Get all drafts for the current user.

    Query params:
        form_type: Filter by form type (optional)
        limit: Number of drafts to return (default 10)

    Returns:
        JSON array of drafts
    """
    try:
        form_type = request.args.get("form_type")
        limit = int(request.args.get("limit", 10))

        query = WorkOrderDraft.query.filter_by(user_id=current_user.id)

        if form_type:
            query = query.filter_by(form_type=form_type)

        drafts = query.order_by(
            WorkOrderDraft.updated_at.desc()
        ).limit(limit).all()

        return jsonify({
            "success": True,
            "drafts": [draft.to_dict() for draft in drafts]
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to load drafts"
        }), 500


@drafts_bp.route("/<int:draft_id>", methods=["GET"])
@login_required
def get_draft(draft_id):
    """
    Get a specific draft by ID.

    Returns:
        JSON with draft data
    """
    try:
        draft = WorkOrderDraft.query.filter_by(
            id=draft_id,
            user_id=current_user.id
        ).first()

        if not draft:
            return jsonify({
                "error": "Draft not found"
            }), 404

        return jsonify({
            "success": True,
            "draft": draft.to_dict()
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to load draft"
        }), 500


@drafts_bp.route("/<int:draft_id>", methods=["DELETE"])
@login_required
def delete_draft(draft_id):
    """
    Delete a specific draft by ID.

    Returns:
        JSON with success status
    """
    try:
        draft = WorkOrderDraft.query.filter_by(
            id=draft_id,
            user_id=current_user.id
        ).first()

        if not draft:
            return jsonify({
                "error": "Draft not found"
            }), 404

        db.session.delete(draft)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Draft deleted successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "message": "Failed to delete draft"
        }), 500


@drafts_bp.route("/cleanup", methods=["POST"])
@login_required
def cleanup_old_drafts():
    """
    Manually trigger cleanup of old drafts.
    Keeps only the 5 most recent drafts.

    Returns:
        JSON with number of drafts deleted
    """
    try:
        deleted_count = WorkOrderDraft.cleanup_old_drafts(
            current_user.id,
            keep_most_recent=5
        )

        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} old drafts"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": str(e),
            "message": "Failed to cleanup drafts"
        }), 500
