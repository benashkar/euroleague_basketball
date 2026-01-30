# EuroLeague American Players Tracker - Developer Guide

Welcome! This guide will help you understand, maintain, and extend the EuroLeague scraper project.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Getting Started](#getting-started)
3. [Project Structure](#project-structure)
4. [How the Scraping Works](#how-the-scraping-works)
5. [Running the Scripts](#running-the-scripts)
6. [GitHub Actions (Automation)](#github-actions-automation)
7. [Testing](#testing)
8. [Web Dashboard](#web-dashboard)
9. [Docker](#docker)
10. [Alerts and Monitoring](#alerts-and-monitoring)
11. [Common Tasks](#common-tasks)
12. [Troubleshooting](#troubleshooting)

---

## Project Overview

### What This Project Does

This project tracks American basketball players in the EuroLeague. It:

1. **Scrapes player data** from the EuroLeague API (names, teams, stats)
2. **Identifies American players** by nationality code (USA/US)
3. **Looks up hometown info** on Wikipedia (city, state, college)
4. **Collects game statistics** (box scores for each game)
5. **Combines everything** into unified JSON files
6. **Runs daily** via GitHub Actions to keep data fresh

### Why It Exists

Local news sites want to cover their hometown players who are now playing in Europe. This tool helps them find and track those players.

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git (for version control)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd euroleague_basketball

# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Quick Test

```bash
# Run a quick scrape (recent games only)
python daily_scraper.py --recent

# Check the output
ls output/json/
```

---

## Project Structure

```
euroleague_basketball/
├── daily_scraper.py          # Main scraper - fetches all data from API
├── hometown_lookup_fixed.py  # Looks up hometowns on Wikipedia
├── join_data.py              # Combines all data sources
├── dashboard.py              # Web dashboard to view data
├── alerts.py                 # Slack/email notifications
│
├── config/
│   ├── logging_config.py     # Centralized logging setup
│   └── settings.py           # Configuration settings
│
├── tests/
│   ├── test_daily_scraper.py   # Tests for scraper functions
│   └── test_hometown_lookup.py # Tests for Wikipedia lookup
│
├── output/
│   └── json/                 # Where all output files go
│       ├── clubs_*.json
│       ├── players_*.json
│       ├── american_players_*.json
│       ├── schedule_*.json
│       ├── american_hometowns_*.json
│       └── unified_american_players_*.json
│
├── .github/
│   └── workflows/
│       ├── daily-scrape.yml      # Runs daily at 6 AM UTC
│       └── weekly_full_scrape.yml # Runs weekly on Sundays
│
├── Dockerfile                # Docker container definition
├── docker-compose.yml        # Docker service definitions
├── requirements.txt          # Python dependencies
└── DEVELOPER_GUIDE.md        # This file!
```

---

## How the Scraping Works

### Data Flow

```
EuroLeague API  →  daily_scraper.py  →  JSON files
                          ↓
Wikipedia API   →  hometown_lookup_fixed.py  →  JSON files
                          ↓
                    join_data.py  →  unified JSON
```

### Step by Step

1. **daily_scraper.py**:
   - Calls `/v2/competitions/E/seasons/E2024/clubs` for teams
   - Calls `/v2/competitions/E/seasons/E2024/people` for players (includes nationality!)
   - Calls `/v2/competitions/E/seasons/E2024/games` for schedule
   - For each game, calls `/games/{code}/stats` for box scores
   - Filters for American players and saves everything to JSON

2. **hometown_lookup_fixed.py**:
   - Reads the American players JSON
   - Searches Wikipedia for each player
   - Parses the "infobox" in their article for birth_place, college
   - Saves hometown data to JSON

3. **join_data.py**:
   - Loads all the separate JSON files
   - Combines them by player code into one unified record
   - Saves the final comprehensive dataset

---

## Running the Scripts

### Daily Scraper

```bash
# Full scrape (all 330 games) - takes a while
python daily_scraper.py

# Recent games only (last 7 days) - faster
python daily_scraper.py --recent

# Today's games only
python daily_scraper.py --today

# Skip box scores (fastest, just rosters/schedule)
python daily_scraper.py --no-boxscores
```

### Hometown Lookup

```bash
# Run after daily_scraper.py
python hometown_lookup_fixed.py
```

### Join Data

```bash
# Run after both scrapers
python join_data.py
```

### Full Pipeline

```bash
# Run everything in sequence
python daily_scraper.py --recent && python hometown_lookup_fixed.py && python join_data.py
```

---

## GitHub Actions (Automation)

### How It Works

GitHub Actions automatically runs our scripts on a schedule:

- **Daily scrape**: Every day at 6 AM UTC
- **Weekly full scrape**: Every Sunday at 2 AM UTC

### Configuration Files

- `.github/workflows/daily-scrape.yml`
- `.github/workflows/weekly_full_scrape.yml`

### Manual Trigger

You can manually trigger a scrape from GitHub:
1. Go to the repository on GitHub
2. Click "Actions" tab
3. Select the workflow
4. Click "Run workflow"

### Viewing Results

1. Go to Actions tab
2. Click on a workflow run
3. View logs and the summary

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_daily_scraper.py -v

# Run with coverage report
python -m pytest tests/ -v --cov=.
```

### Writing New Tests

Tests are in the `tests/` directory. Name them `test_*.py`.

```python
def test_my_function():
    """Describe what this tests."""
    result = my_function("input")
    assert result == "expected_output"
```

---

## Web Dashboard

### Starting the Dashboard

```bash
python dashboard.py
```

Then open http://localhost:5000 in your browser.

### Features

- View all American players with stats
- Filter by team, state
- Search by name
- Click a player to see their game log

---

## Docker

### Why Docker?

Docker packages everything into a container that works the same on any machine. No need to install Python or dependencies.

### Basic Commands

```bash
# Build the image
docker build -t euroleague-scraper .

# Run a scrape
docker run -v $(pwd)/output:/app/output euroleague-scraper python daily_scraper.py --recent

# Run the dashboard
docker run -p 5000:5000 euroleague-scraper python dashboard.py
```

### Using Docker Compose

```bash
# Start dashboard
docker-compose up dashboard

# Run full scrape
docker-compose run full-scrape

# Run tests
docker-compose run tests
```

---

## Alerts and Monitoring

### Setting Up Slack Alerts

1. Create a Slack webhook URL
2. Set the environment variable:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx"
   ```

### Setting Up Email Alerts

```bash
export EMAIL_USERNAME="your@gmail.com"
export EMAIL_PASSWORD="your-app-password"
export EMAIL_TO="recipient@email.com"
```

### Using Alerts in Code

```python
from alerts import send_success_alert, send_failure_alert

try:
    # ... your code ...
    send_success_alert("Daily Scrape", {"players": 100})
except Exception as e:
    send_failure_alert("Daily Scrape", str(e))
```

---

## Common Tasks

### Adding a New Data Field

1. Find where the data comes from in the API response
2. Add extraction in `daily_scraper.py`
3. Add to the unified record in `join_data.py`
4. Update tests

### Changing the Scrape Schedule

Edit `.github/workflows/daily-scrape.yml`:
```yaml
schedule:
  - cron: '0 6 * * *'  # Change this cron expression
```

Cron format: `minute hour day month weekday`

### Adding a New API Endpoint

1. Add a new `fetch_` function in `daily_scraper.py`
2. Call it from `main()`
3. Save the data with `save_json()`

---

## Troubleshooting

### "No players found"

- Check that the EuroLeague API is accessible
- Verify the SEASON constant matches the current season (e.g., 'E2024')

### "Wikipedia returning empty"

- Check that the HEADERS dict includes User-Agent
- Some players don't have Wikipedia articles

### "Box scores have None values"

- Stats are nested under `player_stat.get('stats', {})`
- Use `.get()` with defaults to handle missing data

### "GitHub Actions failing"

1. Check the Actions tab for error logs
2. Common issues:
   - Rate limits (add delays between requests)
   - API changes (update field names)
   - Missing permissions (check workflow permissions)

### Tests Failing

```bash
# Run with more detail
python -m pytest tests/ -v --tb=long
```

---

## Getting Help

- Check the code comments - they explain what each function does
- Review the GitHub Issues for known problems
- Open a new Issue if you find a bug

Good luck! The code is well-commented, so read through the files to understand how everything works.
