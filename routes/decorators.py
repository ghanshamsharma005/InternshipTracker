from functools import wraps
from flask import session, redirect, url_for, flash, abort

def login_required(f):
    """
    Decorator to ensure a user is logged in and active before accessing a route.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        from models import User
        from database.db import db
        user = db.session.get(User, session['user_id'])
        if not user or not getattr(user, 'is_active', True):
            session.clear()
            flash('Your account has been deactivated. Please contact administrator.', 'danger')
            return redirect(url_for('auth.login'))
            
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """
    Decorator to restrict access to active users possessing specific roles.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            from models import User
            from database.db import db
            user = db.session.get(User, session['user_id'])
            if not user or not getattr(user, 'is_active', True):
                session.clear()
                flash('Your account has been deactivated. Please contact administrator.', 'danger')
                return redirect(url_for('auth.login'))
                
            if session.get('role') not in roles:
                abort(403)  # HTTP 403 Forbidden
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
