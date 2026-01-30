# EuroLeague Basketball Data Aggregation System

A data pipeline to track American players in the EuroLeague, collecting roster information, schedules, and game statistics to support "athletes in action" stories for local US news sites.

## Purpose

Enable local news sites to write stories every time a former local high school player competes in a EuroLeague game. For example:
- "Chicago native John Smith scored 22 points for Real Madrid last night"
- "Former Oak Hill Academy star leads Barcelona to victory"

## Features

- **Team Scraping**: Collects all 18 EuroLeague teams with logos and venue info
- **Roster Scraping**: Gets all players with nationality detection
- **American Player Detection**: Automatically flags US-born players
- **Hometown Lookup**: Finds hometown/high school from Basketball Reference, Wikipedia, Grokepedia
- **Schedule Tracking**: Full season schedule with game times
- **Game Statistics**: Box scores for completed games
- **Photo Collection**: Player photos with aspect ratio categorization (16:9 preferred)
- **JSON Export**: Ready-to-use data exports for news applications

## Project Structure

```
euroleague_basketball/
├── config/                          # Configuration files
│   ├── __init__.py
│   ├── database.py                  # Database connection helpers
│   ├── settings.py                  # Environment variables and constants
│   └── league_config.json           # EuroLeague URLs and endpoints
│
├── scrapers/                        # Web scrapers
│   ├── __init__.py
│   ├── base_scraper.py              # Abstract base class with rate limiting
│   ├── euroleague_scraper.py        # EuroLeague website/API scraper
│   ├── basketball_ref_scraper.py    # Basketball Reference (PRIMARY hometown)
│   ├── wikipedia_scraper.py         # Wikipedia (SECONDARY hometown)
│   └── grokepedia_scraper.py        # Grokepedia (TERTIARY hometown)
│
├── database/                        # Database layer
│   ├── __init__.py
│   ├── schema.sql                   # MySQL database schema
│   └── mysql_connector.py           # Database operations
│
├── services/                        # Business logic
│   ├── __init__.py
│   ├── hometown_lookup.py           # Multi-source hometown orchestrator
│   ├── photo_processor.py           # Photo URL processing
│   └── data_validator.py            # Data validation before storage
│
├── utils/                           # Utilities
│   ├── __init__.py
│   ├── name_normalizer.py           # Consistent name formatting
│   ├── date_utils.py                # Timezone handling
│   └── image_utils.py               # Photo URL utilities
│
├── output/                          # Export outputs
│   ├── json/                        # JSON exports
│   └── reports/                     # Generated reports
│
├── tests/                           # Unit tests
│   └── __init__.py
│
├── main.py                          # Main pipeline orchestrator
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
└── README.md                        # This file
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/benashkar/euroleague_basketball.git
cd euroleague_basketball
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up MySQL Database

```bash
# Log into MySQL
mysql -u root -p

# Run the schema
source database/schema.sql
```

### 5. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your database credentials
```

**.env file contents:**
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=basketball_user
MYSQL_PASSWORD=your_secure_password
MYSQL_DATABASE=euroleague_tracker
```

## Usage

### Full Sync (Recommended for First Run)

```bash
python main.py --full
```

This will:
1. Scrape all 18 EuroLeague teams
2. Scrape rosters for each team
3. Scrape the season schedule
4. Look up hometowns for American players
5. Flag games with American players

### Individual Operations

```bash
# Teams only
python main.py --teams

# Rosters only
python main.py --rosters

# Schedule only
python main.py --schedule

# Hometown lookups
python main.py --hometowns

# Game statistics (last 7 days)
python main.py --stats

# Game statistics (last 30 days)
python main.py --stats --days-back 30

# Export to JSON
python main.py --export
```

### Combine Operations

```bash
# Update rosters and export
python main.py --rosters --export

# Scrape stats and export
python main.py --stats --export
```

## Data Sources

### Primary Data
| Source | URL | Data |
|--------|-----|------|
| EuroLeague | https://www.euroleaguebasketball.net | Teams, rosters, schedule, stats |

### Hometown Lookup (Priority Order)
| Priority | Source | URL | Notes |
|----------|--------|-----|-------|
| 1 | Basketball Reference | https://www.basketball-reference.com | Best for NBA/NCAA players |
| 2 | Wikipedia | https://en.wikipedia.org | Good biographical data |
| 3 | Grokepedia | https://grokepedia.com | Alternative source |

## Output Formats

### american_players_{date}.json
```json
{
  "export_date": "2024-01-15T12:00:00",
  "league": "EuroLeague",
  "player_count": 45,
  "players": [
    {
      "full_name": "John Smith",
      "position": "SG",
      "team_name": "Real Madrid",
      "hometown_city": "Chicago",
      "hometown_state": "Illinois",
      "high_school": "Simeon Career Academy",
      "college": "Duke University",
      "photo_url_16x9": "https://..."
    }
  ]
}
```

### upcoming_games_{date}.json
```json
{
  "export_date": "2024-01-15T12:00:00",
  "league": "EuroLeague",
  "days_ahead": 14,
  "games": [
    {
      "game_id": "EUROLEAGUE_E2024_123",
      "game_date": "2024-01-20",
      "game_time": "20:00",
      "home_team_name": "Real Madrid",
      "away_team_name": "Barcelona",
      "american_player_count": 3
    }
  ]
}
```

## Key Queries

### Get Upcoming Games by State

```python
from main import EuroLeaguePipeline

pipeline = EuroLeaguePipeline()
games = pipeline.get_upcoming_games_by_state('Illinois', days_ahead=14)

for game in games:
    print(f"{game['player_name']} from {game['hometown_city']} plays on {game['game_date']}")
```

### SQL: American Players by State

```sql
SELECT
    p.full_name,
    p.hometown_city,
    p.hometown_state,
    p.high_school,
    t.team_name
FROM players p
JOIN teams t ON p.team_id = t.team_id
WHERE p.is_american = TRUE
  AND p.hometown_state = 'Illinois'
ORDER BY p.hometown_city;
```

## Rate Limiting

The scrapers implement respectful rate limiting:

| Source | Delay |
|--------|-------|
| EuroLeague | 2 seconds |
| Basketball Reference | 3 seconds |
| Wikipedia | 1 second |
| Grokepedia | 2 seconds |

## Architecture Notes

### Why Multiple Hometown Sources?

Not all players are on every site:
- **Basketball Reference**: Best coverage for players with NBA/NCAA history
- **Wikipedia**: Good for notable players, has structured infoboxes
- **Grokepedia**: May have lesser-known players

The system tries each source in priority order until it finds the data.

### Name Normalization

Player names are normalized for consistent matching:
- "José García" → "jose_garcia"
- Accents removed
- Lowercase
- Spaces → underscores

This allows matching across sources that may spell names differently.

### Photo Preferences

News sites prefer 16:9 aspect ratio images:
- Better for article headers
- Consistent presentation
- The system tracks multiple photos and prioritizes 16:9

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Contact

For questions or issues, please open a GitHub issue.
