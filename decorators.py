from functools import wraps
from flask import redirect, url_for, abort
from flask_login import current_user


def role_required(*roles):
    """Decorator to restrict route access to specific roles."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))

            # Check if user has required role (case-insensitive comparison)
            user_role = getattr(current_user, 'role', None)
            if not user_role:
                abort(403)  # No role assigned

            # Case-insensitive role matching
            if user_role.lower() not in [r.lower() for r in roles]:
                # For AJAX requests, return JSON error instead of HTML 403
                from flask import request, jsonify
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        "success": False,
                        "message": f"Access denied. Required role: {', '.join(roles)}. Your role: {user_role}"
                    }), 403
                abort(403)  # Forbidden

            return f(*args, **kwargs)

        return decorated_function

    return decorator
