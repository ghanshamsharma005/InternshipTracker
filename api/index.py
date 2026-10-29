import os
import sys

# Ensure the root directory of the application is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Initialize the Flask application
flask_app = create_app()


class VercelPathNormalizer:
    """
    WSGI middleware to normalize PATH_INFO for Vercel Serverless deployments.

    When Vercel rewrites incoming traffic to /api/index (or /api/index.py),
    Vercel's edge router can pass the rewrite destination in PATH_INFO, or provide
    the original requested path via HTTP_X_MATCHED_PATH or REQUEST_URI.
    This middleware restores the original requested path into environ['PATH_INFO']
    so Flask routes match correctly instead of triggering a 404 error.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Prefer HTTP_X_MATCHED_PATH if provided by Vercel's edge router
        matched_path = environ.get('HTTP_X_MATCHED_PATH', '')
        if matched_path:
            clean_path = matched_path.split('?')[0]
            if clean_path.startswith('/api/index.py'):
                clean_path = clean_path[len('/api/index.py'):] or '/'
            elif clean_path.startswith('/api/index'):
                clean_path = clean_path[len('/api/index'):] or '/'
            if clean_path:
                environ['PATH_INFO'] = clean_path
                return self.wsgi_app(environ, start_response)

        # 2. Check if PATH_INFO begins with /api/index.py or /api/index
        path_info = environ.get('PATH_INFO', '')
        if path_info.startswith('/api/index.py'):
            environ['PATH_INFO'] = path_info[len('/api/index.py'):] or '/'
        elif path_info.startswith('/api/index'):
            environ['PATH_INFO'] = path_info[len('/api/index'):] or '/'

        # 3. Fallback: Check REQUEST_URI or RAW_URI if PATH_INFO is missing or points to the function
        current_path = environ.get('PATH_INFO', '')
        if current_path in ('', '/api/index', '/api/index.py'):
            req_uri = environ.get('REQUEST_URI', '') or environ.get('RAW_URI', '')
            if req_uri:
                clean_uri = req_uri.split('?')[0]
                if clean_uri.startswith('/api/index.py'):
                    clean_uri = clean_uri[len('/api/index.py'):] or '/'
                elif clean_uri.startswith('/api/index'):
                    clean_uri = clean_uri[len('/api/index'):] or '/'
                if clean_uri:
                    environ['PATH_INFO'] = clean_uri

        return self.wsgi_app(environ, start_response)


# Apply WSGI middleware wrapper
flask_app.wsgi_app = VercelPathNormalizer(flask_app.wsgi_app)

# Expose WSGI application callable for Vercel Serverless Functions
app = flask_app


