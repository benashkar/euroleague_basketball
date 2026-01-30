#!/bin/bash
# Startup script: Run scraper to populate data, then start web server

echo "=== Running scraper to fetch latest data ==="
python daily_scraper.py

echo "=== Looking up hometowns from Wikipedia ==="
python hometown_lookup_fixed.py || true

echo "=== Joining data for dashboard ==="
python join_data.py

echo "=== Starting web server ==="
exec gunicorn dashboard:app --bind 0.0.0.0:5000
