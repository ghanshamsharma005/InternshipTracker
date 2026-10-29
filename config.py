import os
from datetime import timedelta

# Load local environment variables from .env if present (zero external dependencies)
_base_dir = os.path.abspath(os.path.dirname(__file__))
_env_file = os.path.join(_base_dir, '.env')
if os.path.exists(_env_file):
    try:
        with open(_env_file, 'r', encoding='utf-8-sig') as _f:
            for _line in _f:
                _line = _line.strip().lstrip('\ufeff')
                if not _line or _line.startswith('#') or '=' not in _line:
                    continue
                _k, _v = _line.split('=', 1)
                _k = _k.strip()
                _v = _v.strip().strip("'\"")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v
    except Exception:
        pass

class Config:
    # Secret key for session security (defaults to a development key)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-interntrack-2026'
    
    # Base directory of the application
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Database configuration
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url:
        # Normalize postgres:// to postgresql:// for SQLAlchemy 1.4+ / 2.x compatibility
        if _db_url.startswith('postgres://'):
            _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        # SQLite database configuration (normalized with forward slashes for cross-platform compatibility)
        _db_path = os.path.join(BASE_DIR, "database", "interntrack_v2.db").replace(os.sep, '/')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{_db_path}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload configurations: Use /tmp on Vercel to avoid Read-only filesystem error
    if os.environ.get('VERCEL'):
        UPLOAD_FOLDER = os.path.join('/tmp', 'uploads')
    else:
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB maximum upload size

    # Session & Cookie Security Hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key-2026'
