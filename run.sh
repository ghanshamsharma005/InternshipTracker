#!/usr/bin/env bash
# InternTrack Linux/macOS launcher script

echo "========================================================="
echo "      Starting InternTrack Management System...         "
echo "========================================================="

# Check Python
if ! command -v python3 &> /dev/null
then
    echo "Python3 could not be found. Please install Python 3.9+."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run Flask
echo ""
echo "Starting Flask Application on http://localhost:5000 ..."
echo "Press Ctrl+C to terminate."
echo ""
python3 app.py
