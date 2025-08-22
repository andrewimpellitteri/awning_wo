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
            if current_user.role not in roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)

        return decorated_function

    return decorator
