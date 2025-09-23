from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models.source import Source
from extensions import db
from sqlalchemy import or_
from decorators import role_required

source_bp = Blueprint("source", __name__)


@source_bp.route("/")
@login_required
def source_list():
    """Display all sources with search functionality"""
    search_query = request.args.get("search", "").strip()
    state_filter = request.args.get("state", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Source.query

    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                Source.SSource.contains(search_query),
                Source.SourceCity.contains(search_query),
                Source.SourceState.contains(search_query),
            )
        )

    # Apply state filter
    if state_filter:
        query = query.filter(Source.SourceState.ilike(f"%{state_filter}%"))

    sources = query.paginate(page=page, per_page=per_page, error_out=False)

    # Get unique states for filter dropdown
    states = (
        db.session.query(Source.SourceState)
        .filter(Source.SourceState.isnot(None), Source.SourceState != "")
        .distinct()
        .order_by(Source.SourceState)
        .all()
    )
    unique_states = [state[0] for state in states]

    return render_template(
        "source/list.html",
        sources=sources,
        search_query=search_query,
        state_filter=state_filter,
        unique_states=unique_states,
    )


@source_bp.route("/view/<source_name>")
@login_required
def source_detail(source_name):
    """Display detailed view of a source"""
    source = Source.query.get_or_404(source_name)
    return render_template("source/detail.html", source=source)


@source_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def create_source():
    """Create a new source"""
    if request.method == "POST":
        data = request.form

        if not data.get("SSource"):
            flash("Source name is required", "error")
            return render_template("source/form.html")

        # Check if source already exists
        if Source.query.get(data["SSource"]):
            flash("Source already exists", "error")
            return render_template("source/form.html", form_data=data)

        try:
            source = Source(
                SSource=data["SSource"],
                SourceAddress=data.get("SourceAddress"),
                SourceState=data.get("SourceState"),
                SourceCity=data.get("SourceCity"),
                SourceZip=data.get("SourceZip"),
                SourcePhone=data.get("SourcePhone"),
                SourceFax=data.get("SourceFax"),
                SourceEmail=data.get("SourceEmail"),
            )

            db.session.add(source)
            db.session.commit()

            flash("Source created successfully", "success")
            return redirect(url_for("source.source_detail", source_name=source.SSource))

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating source: {str(e)}", "error")
            return render_template("source/form.html", form_data=data)

    return render_template("source/form.html")


@source_bp.route("/edit/<source_name>", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def edit_source(source_name):
    """Edit an existing source"""
    source = Source.query.get_or_404(source_name)

    if request.method == "POST":
        data = request.form

        try:
            # Update fields if provided in request
            source.SourceAddress = data.get("SourceAddress")
            source.SourceState = data.get("SourceState")
            source.SourceCity = data.get("SourceCity")
            source.SourceZip = data.get("SourceZip")
            source.SourcePhone = data.get("SourcePhone")
            source.SourceFax = data.get("SourceFax")
            source.SourceEmail = data.get("SourceEmail")

            db.session.commit()
            flash("Source updated successfully", "success")
            return redirect(url_for("source.source_detail", source_name=source.SSource))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating source: {str(e)}", "error")

    return render_template("source/form.html", source=source, edit_mode=True)


@source_bp.route("/delete/<source_name>", methods=["POST"])
@login_required
@role_required("admin", "manager")
def delete_source(source_name):
    """Delete a source"""
    source = Source.query.get_or_404(source_name)

    try:
        db.session.delete(source)
        db.session.commit()
        flash("Source deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting source: {str(e)}", "error")

    return redirect(url_for("source.source_list"))


# API endpoints for AJAX requests
@source_bp.route("/api/search")
@login_required
def api_search():
    """API endpoint for searching sources"""
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    sources = (
        Source.query.filter(
            or_(
                Source.SSource.contains(query),
                Source.SourceCity.contains(query),
                Source.SourceState.contains(query),
            )
        )
        .limit(10)
        .all()
    )

    return jsonify(
        [
            {
                "name": source.SSource,
                "city": source.SourceCity,
                "state": source.SourceState,
                "phone": source.clean_phone(),
            }
            for source in sources
        ]
    )


@source_bp.route("/api/states")
@login_required
def api_states():
    """API endpoint to get all unique states"""
    states = (
        db.session.query(Source.SourceState)
        .filter(Source.SourceState.isnot(None), Source.SourceState != "")
        .distinct()
        .order_by(Source.SourceState)
        .all()
    )

    return jsonify([state[0] for state in states])
