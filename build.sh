#!/usr/bin/env bash
# Exit on error
set -o errexit

# Upgrade pip and dependencies first
pip install --upgrade pip setuptools wheel

# Install requirements
pip install -r requirements.txt

# If Pillow still fails, install it with specific flags as fallback
if ! pip show pillow > /dev/null 2>&1; then
    echo "Pillow installation failed, trying alternative approach..."
    pip install pillow==10.0.1 --no-cache-dir
fi

# Collect static files
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate
