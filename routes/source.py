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
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Source.query

    # Apply search filter
    if search_query:
        term = f"%{search_query}%"
        query = query.filter(
            or_(
                Source.SSource.ilike(term),
                Source.SourceCity.ilike(term),
            )
        )

    sources = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "source/list.html",
        sources=sources,
        search_query=search_query,
    )


@source_bp.route("/view/<source_name>")
@login_required
def source_detail(source_name):
    """Display detailed view of a source"""
    source = Source.query.get_or_404(source_name)
    return render_template("source/detail.html", source=source)


# In routes/source.py


@source_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def create_source():
    """Create a new source"""
    if request.method == "POST":
        data = request.form

        # --- FIX 1: Pass context on validation failure ---
        if not data.get("SSource"):
            flash("Source name is required", "error")
            # Pass user's data and edit_mode back to the template
            return render_template(
                "source/form.html", form_data=data, edit_mode=False
            ), 400

        # Check if source already exists
        if Source.query.get(data["SSource"]):
            flash("Source already exists", "error")
            # This line was good, just adding edit_mode for consistency
            return render_template(
                "source/form.html", form_data=data, edit_mode=False
            ), 400

        try:
            # Helper function to convert empty strings to None
            def clean_field(value):
                """Convert empty strings to None for optional fields"""
                return value.strip() if value and value.strip() else None

            source = Source(
                SSource=data["SSource"],
                SourceAddress=clean_field(data.get("SourceAddress")),
                SourceState=clean_field(data.get("SourceState")),
                SourceCity=clean_field(data.get("SourceCity")),
                SourceZip=clean_field(data.get("SourceZip")),
                SourcePhone=clean_field(data.get("SourcePhone")),
                SourceFax=clean_field(data.get("SourceFax")),
                SourceEmail=clean_field(data.get("SourceEmail")),
            )

            db.session.add(source)
            db.session.commit()

            flash("Source created successfully", "success")
            return redirect(url_for("source.source_detail", source_name=source.SSource))

        except Exception as e:
            db.session.rollback()
            flash(f"Error creating source: {str(e)}", "error")
            # Also adding edit_mode here for consistency
            return render_template(
                "source/form.html", form_data=data, edit_mode=False
            ), 500

    # --- FIX 2: Pass context for the initial GET request ---
    # The form needs these variables even when it's empty.
    return render_template("source/form.html", form_data={}, edit_mode=False)


@source_bp.route("/edit/<source_name>", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def edit_source(source_name):
    """Edit an existing source"""
    source = Source.query.get_or_404(source_name)

    if request.method == "POST":
        data = request.form

        try:
            # Helper function to convert empty strings to None
            def clean_field(value):
                """Convert empty strings to None for optional fields"""
                return value.strip() if value and value.strip() else None

            # Update fields if provided in request
            source.SourceAddress = clean_field(data.get("SourceAddress"))
            source.SourceState = clean_field(data.get("SourceState"))
            source.SourceCity = clean_field(data.get("SourceCity"))
            source.SourceZip = clean_field(data.get("SourceZip"))
            source.SourcePhone = clean_field(data.get("SourcePhone"))
            source.SourceFax = clean_field(data.get("SourceFax"))
            source.SourceEmail = clean_field(data.get("SourceEmail"))

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



