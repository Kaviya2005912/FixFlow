from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user


def login_required_role(*roles):
    """Decorator: user must be logged in AND have one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not current_user.active:
                flash('Your account has been deactivated. Contact an administrator.', 'error')
                return redirect(url_for('auth.login'))
            if roles and current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
