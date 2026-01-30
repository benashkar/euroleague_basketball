#!/bin/bash
# Startup script: Run scraper to populate data, then start web server

echo "=== Running scraper to fetch latest data ==="
python daily_scraper.py --full

echo "=== Starting web server ==="
exec gunicorn dashboard:app --bind 0.0.0.0:5000
