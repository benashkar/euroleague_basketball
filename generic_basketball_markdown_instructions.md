# Basketball League Dashboard - Replication Guide

## Purpose
This document provides complete instructions for Claude Code to replicate this basketball dashboard project for any league. The architecture, data structures, and patterns are designed to be league-agnostic.

---

## Project Overview

### What This Project Does
1. **Scrapes** player rosters, game schedules, and box scores from a basketball league API
2. **Enriches** player data with hometown/college info from Wikipedia
3. **Stores** all data in JSON files (serves as the database)
4. **Displays** data via a Flask web dashboard
5. **Deploys** to Render.com with automated data refresh on each deploy

### Key Features
- Full team rosters with player details
- Player headshot images
- Game-by-game statistics and box scores
- Season averages (PPG, RPG, APG)
- Upcoming game schedules
- Player biographical info (hometown, college, high school)
- Filterable/searchable web interface

---

## Project Structure

```
project_root/
├── daily_scraper.py          # Main scraper - fetches all data from league API
├── hometown_lookup_fixed.py  # Wikipedia lookup for player backgrounds
├── join_data.py              # Combines all data into unified records
├── dashboard.py              # Flask web application
├── start.sh                  # Startup script for deployment
├── Dockerfile                # Container configuration
├── requirements.txt          # Python dependencies
├── output/
│   └── json/                 # All JSON data files (the "database")
└── .github/
    └── workflows/            # GitHub Actions for scheduled scrapes (optional)
```

---

## Configuration Variables to Change

When adapting for a new league, modify these variables:

### In `daily_scraper.py`:
```python
# League/Competition identifier
COMPETITION = 'E'           # Change to target league code
SEASON = 'E2025'            # Change to current season format

# API Base URL
API_BASE = 'https://api-live.euroleague.net'  # Change to league's API

# Player filter criteria (e.g., American players)
NATIONALITY_FILTER = ['USA', 'US']  # Adjust based on what players you want to track
```

### In `join_data.py`:
```python
# Season display name
'season': '2025-26'  # Update to match the season
```

### In `dashboard.py`:
```python
# Page titles and headers
<title>EuroLeague American Players</title>  # Change league name
<h1>EuroLeague American Players Dashboard</h1>  # Change league name
```

---

## Data Flow Pipeline

```
┌─────────────────┐
│  League API     │
│  (External)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ daily_scraper.py│  Fetches: clubs, players, schedule, box scores
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ hometown_lookup │  Enriches with Wikipedia data (hometown, college)
│ _fixed.py       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ join_data.py    │  Combines all sources into unified player records
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ JSON Files      │  unified_american_players_*.json (the "database")
│ (output/json/)  │  american_players_summary_*.json
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ dashboard.py    │  Flask web app reads JSON, renders HTML
└─────────────────┘
```

---

## API Patterns

Most basketball league APIs follow similar patterns. Here's how to adapt:

### Common Endpoints to Find:

| Data Needed | EuroLeague Pattern | Typical Pattern |
|-------------|-------------------|-----------------|
| Teams/Clubs | `/v2/competitions/{id}/seasons/{season}/clubs` | `/api/teams` or `/clubs` |
| Players | `/v2/competitions/{id}/seasons/{season}/people?personType=J` | `/api/players` or `/rosters` |
| Schedule | `/v2/competitions/{id}/seasons/{season}/games` | `/api/schedule` or `/games` |
| Box Scores | `/v2/competitions/{id}/seasons/{season}/games/{gameCode}/stats` | `/api/games/{id}/boxscore` |

### Player Data Fields to Map:

```python
# Standard fields to extract from any league API:
player = {
    'code': '',              # Unique player ID
    'name': '',              # Player name
    'team_code': '',         # Team ID
    'team_name': '',         # Team name
    'position': '',          # Guard, Forward, Center
    'jersey': '',            # Jersey number
    'height': 0,             # Height (cm or inches)
    'weight': 0,             # Weight
    'birth_date': '',        # Birth date
    'nationality': '',       # Country
    'headshot_url': '',      # Player photo URL
}
```

### Box Score Stats to Map:

```python
# Standard stats fields:
stats = {
    'points': 0,
    'rebounds': 0,           # or 'totalRebounds'
    'assists': 0,            # might be 'assistances'
    'steals': 0,
    'blocks': 0,
    'turnovers': 0,
    'minutes': 0,            # or 'timePlayed' in seconds
    'fg_made': 0,
    'fg_attempted': 0,
    'three_made': 0,
    'three_attempted': 0,
    'ft_made': 0,
    'ft_attempted': 0,
}
```

---

## JSON Data Structures

### Unified Player Record Schema:

```json
{
  "code": "012774",
  "name": "Kendrick Nunn",
  "team": "Panathinaikos AKTOR Athens",
  "team_code": "PAN",
  "position": "Guard",
  "jersey": "12",
  "height_cm": 188,
  "height_feet": 6,
  "height_inches": 2,
  "birth_date": "1995-08-03",
  "nationality": "United States of America",
  "headshot_url": "https://media-cdn.example.com/player.png",
  "action_url": "https://media-cdn.example.com/action.png",
  "hometown_city": "Chicago",
  "hometown_state": "Illinois",
  "hometown": "Chicago, Illinois",
  "college": "Oakland University",
  "high_school": "Simeon Career Academy",
  "games_played": 21,
  "ppg": 19.4,
  "rpg": 3.0,
  "apg": 3.6,
  "total_points": 408,
  "total_rebounds": 63,
  "total_assists": 76,
  "recent_games": [...],
  "all_games": [...],
  "upcoming_games": [...]
}
```

### Game Record Schema:

```json
{
  "date": "2026-01-15T20:00:00",
  "opponent": "Real Madrid",
  "home_away": "home",
  "team_score": 85,
  "opp_score": 78,
  "result": "W",
  "points": 24,
  "rebounds": 4,
  "assists": 5,
  "steals": 2,
  "blocks": 0,
  "minutes": 32.5,
  "fg": "9/15",
  "three": "3/6",
  "ft": "3/4"
}
```

### Upcoming Game Schema:

```json
{
  "date": "2026-02-01",
  "opponent": "FC Barcelona",
  "home_away": "Away",
  "round": 25,
  "venue": "Palau Blaugrana"
}
```

---

## File-by-File Implementation Guide

### 1. `daily_scraper.py` (~900 lines)

**Purpose:** Fetches all data from the league API

**Key Functions to Implement:**

```python
def api_get(endpoint):
    """Make GET request to league API with proper headers"""

def fetch_clubs():
    """Get all teams in the league"""

def fetch_people():
    """Get all players, filter by nationality if needed"""

def fetch_games(mode='all'):
    """Get schedule - all games, played only, or upcoming only"""

def fetch_game_stats(game_code):
    """Get box score for a specific game"""

def extract_performances(game, stats):
    """Extract player stats from a box score"""

def main():
    """Orchestrate the full scrape"""
```

**Rate Limiting:** Always add delays between API calls (0.2-0.3 seconds)

### 2. `hometown_lookup_fixed.py` (~750 lines)

**Purpose:** Looks up player backgrounds on Wikipedia

**Key Features:**
- Wikipedia API search for player articles
- Parses infobox for birth_place, college, high_school
- Manual overrides for players with common names
- Handles disambiguation (e.g., "Devin Booker" could be multiple players)

**Manual Override Example:**
```python
MANUAL_OVERRIDES = {
    'BOOKER, DEVIN': {
        'hometown_city': 'Union',
        'hometown_state': 'South Carolina',
        'college': 'Clemson',
        'high_school': 'Union County High School',
    },
}
```

### 3. `join_data.py` (~500 lines)

**Purpose:** Combines all data sources into unified player records

**Data Sources Combined:**
- `american_players_*.json` - Basic player info
- `american_hometowns_found_*.json` - Wikipedia data
- `american_player_stats_*.json` - Season averages
- `american_performances_*.json` - Game-by-game stats
- `schedule_*.json` - Upcoming games

**Key Function:**
```python
def main():
    # Load all data sources
    players_data = load_latest_json('american_players_*.json')
    hometowns_data = load_latest_json('american_hometowns_found_*.json')
    stats_data = load_latest_json('american_player_stats_*.json')
    performances_data = load_latest_json('american_performances_*.json')
    schedule_data = load_latest_json('schedule_*.json')

    # Build lookup dictionaries
    # Combine into unified records
    # Save output
```

### 4. `dashboard.py` (~500 lines)

**Purpose:** Flask web application

**Routes:**
- `/` - Homepage with player list, filters, sorting
- `/player/<code>` - Player detail page with stats and game log

**Key Components:**
- Inline HTML templates (Jinja2)
- CSS styling (inline in base template)
- Filter dropdowns (team, state)
- Search box
- Sortable columns

### 5. `start.sh`

```bash
#!/bin/bash
echo "=== Starting web server ==="
exec gunicorn dashboard:app --bind 0.0.0.0:5000
```

### 6. `Dockerfile`

**Key Sections:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code
COPY . .

# Run scraper during build (bakes data into image)
RUN python daily_scraper.py && \
    python hometown_lookup_fixed.py || true && \
    python join_data.py

# Start web server
CMD ["./start.sh"]
```

### 7. `requirements.txt`

```
flask>=2.0.0
gunicorn>=20.0.0
requests>=2.25.0
```

---

## Deployment on Render.com

### Setup Steps:

1. **Create Web Service:**
   - Connect GitHub repo
   - Environment: Docker
   - Instance Type: Free

2. **Environment Variables:**
   - `RENDER_API_KEY` - For triggering deploys via API

3. **Deploy Settings:**
   - Auto-deploy on push: Yes
   - Health check path: `/`

### Triggering Manual Deploys (to refresh data):

```bash
curl -X POST "https://api.render.com/v1/services/{SERVICE_ID}/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"clearCache": "do_not_clear"}'
```

---

## Step-by-Step: Creating a New League Project

### Phase 1: Research the API

1. **Find the league's API:**
   - Check browser dev tools while browsing their website
   - Look for XHR requests to `/api/` endpoints
   - Common patterns: `/api/teams`, `/api/players`, `/api/games`

2. **Document the endpoints:**
   - Teams/clubs list
   - Player rosters
   - Game schedule
   - Box scores/game stats

3. **Map the data fields:**
   - Player ID field name
   - Stats field names (rebounds vs totalRebounds, etc.)
   - Date formats
   - Image URL patterns

### Phase 2: Create the Scraper

1. Copy `daily_scraper.py` as template
2. Update API_BASE and endpoints
3. Adjust field mappings in extract functions
4. Test each endpoint individually
5. Run full scrape and verify JSON output

### Phase 3: Adapt Supporting Scripts

1. Copy `hometown_lookup_fixed.py` (usually works as-is)
2. Copy `join_data.py` and adjust field names if needed
3. Copy `dashboard.py` and update titles/labels

### Phase 4: Deploy

1. Create new GitHub repo
2. Copy all files
3. Create Render web service
4. Connect repo and deploy

---

## Adapting for Specific Leagues

### Spanish Liga ACB
- API: Research at `acb.com`
- Player nationality: Filter for Americans or any nationality
- Language: Spanish team names

### Turkish BSL
- API: Research at `tbl.org.tr`
- Consider character encoding for Turkish names

### Italian Lega Basket
- API: Research at `legabasket.it`
- European date formats

### French Pro A
- API: Research at `lnb.fr`

### German BBL
- API: Research at `easycredit-bbl.de`

---

## Common Issues and Solutions

### Issue: API returns 403 Forbidden
**Solution:** Add proper User-Agent header, check for required auth tokens

### Issue: Player names in "LAST, FIRST" format
**Solution:** Add name cleaning function:
```python
def clean_name(name):
    if ', ' in name:
        parts = name.split(', ', 1)
        return f"{parts[1]} {parts[0]}".title()
    return name
```

### Issue: Height in centimeters, need feet/inches
**Solution:** Add conversion function:
```python
def cm_to_feet_inches(cm):
    total_inches = cm / 2.54
    feet = int(total_inches // 12)
    inches = int(round(total_inches % 12))
    return feet, inches
```

### Issue: Wikipedia finds wrong player
**Solution:** Add to MANUAL_OVERRIDES dictionary

### Issue: Render free tier spins down
**Solution:** Run scraper during Docker build (data baked into image)

---

## Testing Checklist

- [ ] Scraper fetches all teams
- [ ] Scraper fetches all players
- [ ] Scraper fetches schedule (played + upcoming games)
- [ ] Scraper fetches box scores for played games
- [ ] Wikipedia lookup finds ~40-60% of players
- [ ] Join script creates unified records
- [ ] Dashboard homepage loads with player list
- [ ] Filters work (team, state)
- [ ] Search works
- [ ] Player detail page loads
- [ ] Player headshot displays
- [ ] Game log shows all games
- [ ] Upcoming games section shows schedule
- [ ] Deployment succeeds on Render
- [ ] Site loads quickly after spin-up

---

## Summary

To create a new league dashboard:

1. **Find the API** - Research the league's data endpoints
2. **Map the fields** - Document how their data maps to our schema
3. **Copy the codebase** - Use this project as a template
4. **Update configuration** - Change API URLs, field names, titles
5. **Test locally** - Run scraper and dashboard
6. **Deploy** - Push to GitHub, connect to Render

The core architecture (scraper → enrichment → join → dashboard) works for any basketball league with a public API.
