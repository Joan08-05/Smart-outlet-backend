#!/usr/bin/env bash
# Build script for Render deployment
# This script runs automatically every time you deploy to Render

# Exit immediately if any command fails
set -o errexit

# Install all required libraries from requirements.txt
pip install -r requirements.txt

# Collect static files (needed for admin panel CSS on Render)
python smart_outlet/manage.py collectstatic --no-input

# Apply all database migrations to PostgreSQL on Render
python smart_outlet/manage.py migrate