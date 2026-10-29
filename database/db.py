import sqlite3
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Initialize the SQLAlchemy object
db = SQLAlchemy()

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Enforces SQLite foreign key constraints only for SQLite database connections.
    Safely ignores PostgreSQL and other database engines.
    """
    if isinstance(dbapi_connection, sqlite3.Connection) or dbapi_connection.__class__.__module__.startswith('sqlite3'):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def init_db(app):
    """
    Initializes SQLAlchemy database connection for the Flask application.
    """
    db.init_app(app)
    
    # Automatically create the database tables (e.g. for any loaded models)
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.error("Database schema initialization / create_all failed: %s", e, exc_info=True)

