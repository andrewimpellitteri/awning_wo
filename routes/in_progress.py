from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from models.work_order import WorkOrder
from models.customer import Customer
from models.source import Source
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from extensions import db
from datetime import datetime

in_progress_bp = Blueprint("in_progress", __name__)


@in_progress_bp.route("/")
@login_required
def in_progress_home():
    return redirect(url_for("in_progress.all_recent"))


# Route for in-progress work orders
@in_progress_bp.route("/list_in_progress")
@login_required
def list_in_progress():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.options(
        joinedload(WorkOrder.customer).joinedload(Customer.source_info)
    ).filter(WorkOrder.ProcessingStatus == True)

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="in_progress",
    )


# Route for recently cleaned or treated work orders
@in_progress_bp.route("/list_recently_cleaned")
@login_required
def list_recently_cleaned():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.options(
        joinedload(WorkOrder.customer).joinedload(Customer.source_info)
    ).filter(
        or_(WorkOrder.Clean.isnot(None), WorkOrder.Treat.isnot(None)),
        WorkOrder.DateCompleted.is_(None),
    )

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="recently_cleaned",
    )


# Route for cleaned work orders
@in_progress_bp.route("/list_cleaned")
@login_required
def list_cleaned():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.options(
        joinedload(WorkOrder.customer).joinedload(Customer.source_info)
    ).filter(
        WorkOrder.Clean.isnot(None),
        WorkOrder.DateCompleted.is_(None),
        WorkOrder.Treat.is_(None),
    )

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="cleaned",
    )


# Route for treated work orders
@in_progress_bp.route("/list_treated")
@login_required
def list_treated():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.options(
        joinedload(WorkOrder.customer).joinedload(Customer.source_info)
    ).filter(
        WorkOrder.Treat.isnot(None),
        WorkOrder.DateCompleted.is_(None),
        or_(WorkOrder.final_location.is_(None), WorkOrder.final_location == ""),
    )

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="treated",
    )


# Route for packaged work orders
@in_progress_bp.route("/list_packaged")
@login_required
def list_packaged():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.options(
        joinedload(WorkOrder.customer).joinedload(Customer.source_info)
    ).filter(
        WorkOrder.final_location.isnot(None),
        WorkOrder.final_location != "",
        WorkOrder.DateCompleted.is_(None),
    )

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="packaged",
    )


# Route for all recent work orders
@in_progress_bp.route("/all_recent")
@login_required
def all_recent():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = WorkOrder.query.options(
        joinedload(WorkOrder.customer).joinedload(Customer.source_info)
    ).filter(
        or_(
            WorkOrder.ProcessingStatus == True,
            WorkOrder.Clean.isnot(None),
            WorkOrder.Treat.isnot(None),
            (WorkOrder.final_location.isnot(None)) & (WorkOrder.final_location != ""),
        ),
        WorkOrder.DateCompleted.is_(None),
    )

    pagination = query.order_by(WorkOrder.updated_at.desc()).paginate(
        page=page, per_page=per_page
    )
    work_orders = pagination.items

    return render_template(
        "in_progress/list.html",
        work_orders=work_orders,
        pagination=pagination,
        tab="all_recent",
    )


@in_progress_bp.route("/treat_work_order/<work_order_no>", methods=["POST"])
@login_required
def treat_work_order(work_order_no):
    work_order = WorkOrder.query.get(work_order_no)
    if not work_order:
        return jsonify({"success": False, "message": "Work order not found"}), 404
    data = request.get_json()
    treat_date = data.get("treatDate")
    if not work_order.Clean:
        return jsonify(
            {
                "success": False,
                "message": "Clean date is required before entering treat date",
            }
        ), 400
    if not treat_date:
        return jsonify({"success": False, "message": "Treat date is required"}), 400
    work_order.Treat = datetime.strptime(treat_date, "%Y-%m-%d").date()

    # Clear queue position when moving to in-progress
    if work_order.QueuePosition is not None:
        work_order.QueuePosition = None

    db.session.commit()
    return jsonify({"success": True})


@in_progress_bp.route("/package_work_order/<work_order_no>", methods=["POST"])
@login_required
def package_work_order(work_order_no):
    work_order = WorkOrder.query.get(work_order_no)
    if not work_order:
        return jsonify({"success": False, "message": "Work order not found"}), 404
    data = request.get_json()
    final_location = data.get("finalLocation")

    if not final_location:
        return jsonify({"success": False, "message": "Final location is required"}), 400

    # Flash warning if Clean or Treat dates are missing (but allow the operation)
    warning = None
    if not work_order.Clean and not work_order.Treat:
        warning = "Warning: Work order packaged without clean or treat dates."
    elif not work_order.Clean:
        warning = "Warning: Work order packaged without clean date."
    elif not work_order.Treat:
        warning = "Warning: Work order packaged without treat date."

    if warning:
        flash(warning, "warning")

    work_order.final_location = final_location

    # Clear queue position when moving to in-progress
    if work_order.QueuePosition is not None:
        work_order.QueuePosition = None

    db.session.commit()
    return jsonify({"success": True, "warning": warning})


@in_progress_bp.route("/complete_work_order/<work_order_no>", methods=["POST"])
@login_required
def complete_work_order(work_order_no):
    if current_user.role == "user":
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    work_order = WorkOrder.query.get(work_order_no)
    if not work_order:
        return jsonify({"success": False, "message": "Work order not found"}), 404
    data = request.get_json()
    date_completed = data.get("dateCompleted")
    if not date_completed:
        return jsonify({"success": False, "message": "Date completed is required"}), 400
    work_order.DateCompleted = datetime.strptime(date_completed, "%Y-%m-%d").date()

    # Clear queue position when completing work order
    if work_order.QueuePosition is not None:
        work_order.QueuePosition = None

    db.session.commit()
    return jsonify({"success": True})
