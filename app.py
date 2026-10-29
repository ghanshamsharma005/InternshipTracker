import os
from flask import Flask, send_from_directory, render_template, abort, session, request
from config import Config
from database.db import db, init_db
from routes.main import main_bp

def create_app(config_class=None):
    """
    Application Factory to build and configure the Flask app.
    """
    if config_class is None:
        import sys
        if 'unittest' in sys.modules or os.environ.get('TESTING') == 'True' or os.environ.get('FLASK_ENV') == 'testing':
            from config import TestConfig
            config_class = TestConfig
        else:
            config_class = Config

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure system directories (database and uploads) exist
    raw_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if raw_uri.startswith('sqlite:///') and ':memory:' not in raw_uri:
        db_path = raw_uri.replace('sqlite:///', '')
        if db_path:
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if db_dir:
                try:
                    os.makedirs(db_dir, exist_ok=True)
                except OSError as e:
                    app.logger.warning("Could not create database directory %s: %s", db_dir, e)
    if app.config.get('UPLOAD_FOLDER'):
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        except OSError as e:
            app.logger.warning("Could not create upload directory %s: %s", app.config['UPLOAD_FOLDER'], e)

    # Check for Vercel deployment environment variables
    if os.environ.get('VERCEL'):
        if not os.environ.get('DATABASE_URL'):
            app.logger.warning(
                "Running on Vercel without DATABASE_URL configured. "
                "Serverless filesystem is read-only and ephemeral. "
                "Database writes (including user registration) will fail until a hosted PostgreSQL database is set in Vercel Environment Variables."
            )
        if not os.environ.get('SECRET_KEY'):
            app.logger.warning(
                "Running on Vercel without a custom SECRET_KEY configured. "
                "Set SECRET_KEY in Vercel Environment Variables to secure production user sessions."
            )

    # Import models to register metadata with SQLAlchemy
    import models

    # Initialize extensions
    init_db(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.student import student_bp
    from routes.faculty import faculty_bp
    from routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(admin_bp)

    # Uploaded file serving route with role & ownership authorization
    from routes.decorators import login_required

    @app.route('/uploads/<path:filename>')
    @login_required
    def uploaded_file(filename):
        # Path traversal protection
        upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
        target_path = os.path.abspath(os.path.join(upload_folder, filename))
        if not target_path.startswith(upload_folder):
            abort(403)

        if not os.path.exists(target_path):
            abort(404)

        # Role & Ownership Authorization
        role = session.get('role')
        if role in ['faculty', 'admin']:
            return send_from_directory(upload_folder, filename)
        elif role == 'student':
            from models import Student, Document, ProgressReport
            student = Student.query.filter_by(user_id=session.get('user_id')).first()
            if not student:
                abort(403)
            
            # Check Document ownership
            doc = Document.query.filter_by(file_path=filename).first()
            if doc and doc.student_id == student.id:
                return send_from_directory(upload_folder, filename)
            
            # Check ProgressReport ownership
            rep = ProgressReport.query.filter_by(report_file=filename).first()
            if rep and rep.student_id == student.id:
                return send_from_directory(upload_folder, filename)

            # Check filename naming prefix
            if filename.startswith(f"student_{student.id}_"):
                return send_from_directory(upload_folder, filename)

            # Unauthorized access to another student's file
            abort(403)
        
        abort(403)

    # HTTP Security Headers Middleware
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'self';"
        )
        return response

    # Register error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error("Internal Server Error (500): %s", error, exc_info=True)
        return render_template('errors/500.html'), 500

    return app


# Expose application instance for WSGI / Vercel serverless deployment
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
