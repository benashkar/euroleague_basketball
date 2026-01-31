# =============================================================================
# DOCKERFILE FOR EUROLEAGUE SCRAPER
# =============================================================================
#
# PURPOSE:
#     Creates a containerized environment to run the EuroLeague scraper.
#     This ensures consistent behavior across different machines.
#
# HOW TO USE:
#     Build the image:
#         docker build -t euroleague-scraper .
#
#     Run a one-time scrape:
#         docker run euroleague-scraper python daily_scraper.py
#
#     Run with data persistence (saves output to your machine):
#         docker run -v $(pwd)/output:/app/output euroleague-scraper python daily_scraper.py
#
#     Run the dashboard:
#         docker run -p 5000:5000 euroleague-scraper python dashboard.py
#
#     Interactive shell:
#         docker run -it euroleague-scraper bash
#
# WHY USE DOCKER:
#     1. Works the same on any machine (Windows, Mac, Linux)
#     2. No need to install Python or dependencies on your machine
#     3. Easy to deploy to cloud servers
#     4. Isolated environment won't conflict with other projects
#
# =============================================================================

# -----------------------------------------------------------------------------
# Base Image
# -----------------------------------------------------------------------------
# We use the official Python slim image for a smaller container size.
# "slim" removes unnecessary packages but keeps what Python needs.
# Version 3.11 matches our development environment.
FROM python:3.11-slim

# -----------------------------------------------------------------------------
# Set Working Directory
# -----------------------------------------------------------------------------
# This is where our code will live inside the container.
# All subsequent commands will run relative to this directory.
WORKDIR /app

# -----------------------------------------------------------------------------
# Install System Dependencies
# -----------------------------------------------------------------------------
# Some Python packages need system libraries to build properly.
# We install them here, then clean up to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # gcc is needed to compile some Python packages
    gcc \
    # Clean up package lists to reduce image size
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Copy Requirements First (for Docker Layer Caching)
# -----------------------------------------------------------------------------
# Docker caches each layer. By copying requirements.txt first and installing
# dependencies before copying our code, we avoid reinstalling packages
# every time we change our code.
COPY requirements.txt .

# -----------------------------------------------------------------------------
# Install Python Dependencies
# -----------------------------------------------------------------------------
# --no-cache-dir: Don't save the download cache (smaller image)
# --upgrade pip: Ensure we have the latest pip
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Copy Application Code
# -----------------------------------------------------------------------------
# Now copy the rest of our code into the container.
# The .dockerignore file controls what gets excluded.
COPY . .

# -----------------------------------------------------------------------------
# Create Output Directory
# -----------------------------------------------------------------------------
# Ensure the output directory exists for saving JSON files.
RUN mkdir -p /app/output/json /app/logs

# -----------------------------------------------------------------------------
# Pre-populate Data During Build
# -----------------------------------------------------------------------------
# Run the scraper during build to bake data into the image.
# This enables instant cold starts (web server starts immediately).
# Data refreshes with each new deployment.
RUN echo "=== Building: Fetching player data ===" && \
    python daily_scraper.py && \
    echo "=== Building: Looking up hometowns ===" && \
    (python hometown_lookup_fixed.py || true) && \
    echo "=== Building: Joining data ===" && \
    python join_data.py && \
    echo "=== Build complete: Data ready ==="

# -----------------------------------------------------------------------------
# Set Environment Variables
# -----------------------------------------------------------------------------
# PYTHONUNBUFFERED=1: Print output immediately (don't buffer)
# This is important for seeing logs in real-time.
ENV PYTHONUNBUFFERED=1

# TZ: Set timezone (adjust to your local time)
ENV TZ=UTC

# -----------------------------------------------------------------------------
# Expose Port (for Dashboard)
# -----------------------------------------------------------------------------
# The dashboard runs on port 5000.
# EXPOSE doesn't publish the port, it documents which ports to publish.
EXPOSE 5000

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
# Docker can periodically check if the container is healthy.
# This runs every 30 seconds and checks if Python is working.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; print('OK')" || exit 1

# -----------------------------------------------------------------------------
# Make startup script executable
# -----------------------------------------------------------------------------
RUN chmod +x start.sh

# -----------------------------------------------------------------------------
# Default Command
# -----------------------------------------------------------------------------
# This runs when you start the container without specifying a command.
# The startup script runs the scraper first to populate data, then starts gunicorn.
# For scraping only, override with: docker run <image> python daily_scraper.py --recent
CMD ["./start.sh"]
