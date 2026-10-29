import os
import sys

# Ensure the root directory of the application is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# WSGI application callable for Vercel Serverless Functions
app = create_app()

