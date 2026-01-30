"""
=============================================================================
EUROLEAGUE DAILY SCRAPER
=============================================================================

PURPOSE:
    This script collects basketball data from the EuroLeague API.
    It's designed to track American players in the EuroLeague for
    local news sites that want to cover hometown players.

WHAT IT DOES:
    1. Fetches all clubs (teams) in the EuroLeague
    2. Fetches all players with their nationality information
    3. Identifies American players (nationality code 'USA' or 'US')
    4. Fetches game schedules and scores
    5. For completed games, fetches detailed box scores (stats)
    6. Extracts performance data for American players
    7. Calculates season averages (PPG, RPG, APG)
    8. Saves everything to JSON files for further processing

HOW TO USE:
    python daily_scraper.py              # Full scrape - all 330 games
    python daily_scraper.py --recent     # Only games from last 7 days
    python daily_scraper.py --today      # Only today's games
    python daily_scraper.py --no-boxscores  # Skip fetching detailed stats

OUTPUT FILES (saved to output/json/):
    - clubs_TIMESTAMP.json: All 18 EuroLeague teams
    - players_TIMESTAMP.json: All players in the league
    - american_players_TIMESTAMP.json: Just American players
    - schedule_TIMESTAMP.json: Game schedule with scores
    - game_recaps_TIMESTAMP.json: Game summaries
    - american_performances_TIMESTAMP.json: Box score stats for Americans
    - american_player_stats_TIMESTAMP.json: Season averages for Americans

SCHEDULE:
    - Runs daily at 6 AM UTC via GitHub Actions (daily-scrape.yml)
    - Runs weekly full refresh at 2 AM UTC Sundays (weekly_full_scrape.yml)

API DOCUMENTATION:
    The EuroLeague API is at https://api-live.euroleague.net
    Key endpoints used:
    - /v2/competitions/E/seasons/E2024/clubs - Get all teams
    - /v2/competitions/E/seasons/E2024/people - Get all players (includes nationality!)
    - /v2/competitions/E/seasons/E2024/games - Get schedule
    - /v2/competitions/E/seasons/E2024/games/{code}/stats - Get box score

IMPORTANT NOTES FOR MAINTAINERS:
    - The API has rate limits, so we add 0.2 second delays between requests
    - Stats are NESTED under a 'stats' key in the API response
    - Some field names are different: 'assistances' not 'assists', 'valuation' not 'pir'
    - Time played is in SECONDS, must convert to minutes
    - Always handle None values - some players have missing data
"""

# =============================================================================
# IMPORTS
# =============================================================================
# argparse: Lets us handle command-line arguments like --recent and --today
import argparse

# json: For reading and writing JSON files (our data format)
import json

# os: For file and directory operations (creating output folders, etc.)
import os

# requests: For making HTTP requests to the EuroLeague API
# If you get "ModuleNotFoundError", run: pip install requests
import requests

# datetime, timedelta: For working with dates (filtering recent games)
from datetime import datetime, timedelta

# logging: For printing status messages with timestamps
import logging

# time: For adding delays between API requests (rate limiting)
import time

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
# This sets up logging so we can see what's happening when the script runs.
# The format shows: timestamp - log level - message
# Example output: 2024-01-15 10:30:45,123 - INFO - Fetching clubs...

logging.basicConfig(
    level=logging.INFO,  # Show INFO and above (INFO, WARNING, ERROR)
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================
# BASE_URL: The root URL for all EuroLeague API requests
BASE_URL = 'https://api-live.euroleague.net'

# SEASON: The season identifier (E2025 = 2025-26 season)
# Format is "E" for EuroLeague + the starting year
SEASON = 'E2025'

# COMPETITION: Competition code ("E" for EuroLeague, "U" for EuroCup)
COMPETITION = 'E'

# AMERICAN_CODES: Country codes that indicate American nationality
# Some records use 'USA', others use 'US'
AMERICAN_CODES = ['USA', 'US']


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_american(country_data):
    """
    Check if a player is American based on their country data.

    WHAT IT DOES:
        Takes the country data from the API and checks if the country code
        matches 'USA' or 'US'.

    PARAMETERS:
        country_data (dict or None): A dictionary containing country info like:
            {'code': 'USA', 'name': 'United States'}
            Can be None if the player has no country data.

    RETURNS:
        bool: True if American, False otherwise

    EXAMPLE:
        >>> is_american({'code': 'USA', 'name': 'United States'})
        True
        >>> is_american({'code': 'ESP', 'name': 'Spain'})
        False
        >>> is_american(None)
        False
    """
    # Safety check: If country_data is None, return False
    if not country_data:
        return False

    # Get the country code, convert to uppercase for consistent comparison
    code = country_data.get('code', '').upper()

    # Check if the code is in our list of American codes
    return code in AMERICAN_CODES


def save_json(data, filename):
    """
    Save a Python dictionary to a JSON file.

    WHAT IT DOES:
        Takes your data and saves it as a nicely formatted JSON file
        in the output/json/ directory.

    PARAMETERS:
        data (dict): The data to save (usually a dictionary)
        filename (str): The name of the file (e.g., 'clubs_20240115.json')

    RETURNS:
        str: The full file path where the data was saved

    EXAMPLE:
        >>> save_json({'name': 'Test'}, 'test.json')
        Saved: /path/to/output/json/test.json

    NOTES:
        - Creates the output/json directory if it doesn't exist
        - Uses indent=2 for readable formatting
        - Uses ensure_ascii=False to properly save non-English characters
          (important for European player names like "Ndi??ye")
    """
    # Build the path to the output directory
    # __file__ is the path to this script
    # os.path.dirname gets the directory containing this script
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')

    # Create the directory if it doesn't exist
    # exist_ok=True means don't error if it already exists
    os.makedirs(output_dir, exist_ok=True)

    # Build the full file path
    filepath = os.path.join(output_dir, filename)

    # Open the file and write the JSON
    # encoding='utf-8' ensures special characters are handled correctly
    with open(filepath, 'w', encoding='utf-8') as f:
        # json.dump writes the data to the file
        # indent=2 makes it human-readable (2 spaces per level)
        # default=str converts non-JSON types (like datetime) to strings
        # ensure_ascii=False keeps special characters as-is
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")
    return filepath


def api_get(endpoint, params=None):
    """
    Make a GET request to the EuroLeague API.

    WHAT IT DOES:
        Sends an HTTP GET request to the API and returns the JSON response.
        Handles errors gracefully so one bad request doesn't crash everything.

    PARAMETERS:
        endpoint (str): The API endpoint (e.g., '/v2/competitions/E/seasons/E2024/clubs')
        params (dict, optional): Query parameters to add to the URL

    RETURNS:
        dict or None: The JSON response as a Python dictionary, or None if error

    EXAMPLE:
        >>> data = api_get('/v2/competitions/E/seasons/E2024/clubs')
        >>> print(data['data'][0]['name'])
        'Real Madrid'

    ERROR HANDLING:
        If the request fails (network error, invalid response, etc.),
        this function logs the error and returns None instead of crashing.
    """
    # Build the full URL by combining base URL and endpoint
    url = f"{BASE_URL}{endpoint}"

    try:
        # Make the HTTP GET request
        # timeout=30 means give up after 30 seconds
        resp = requests.get(url, params=params, timeout=30)

        # raise_for_status() throws an exception if we get a 4xx or 5xx error
        resp.raise_for_status()

        # Parse the JSON response and return it
        return resp.json()

    except Exception as e:
        # Log the error but don't crash - return None instead
        logger.error(f"API error {endpoint}: {e}")
        return None


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_clubs():
    """
    Fetch all clubs (teams) in the EuroLeague.

    WHAT IT DOES:
        Calls the clubs endpoint to get all 18 EuroLeague teams.

    RETURNS:
        list: A list of club dictionaries, or empty list if error

    EXAMPLE RESPONSE (one club):
        {
            'code': 'MAD',
            'name': 'Real Madrid',
            'images': {...},
            'address': {...}
        }
    """
    logger.info("Fetching clubs...")

    # Make the API request
    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/clubs')

    if data:
        # The clubs are nested under a 'data' key
        clubs = data.get('data', [])
        logger.info(f"  Found {len(clubs)} clubs")
        return clubs

    return []


def fetch_players():
    """
    Fetch all players with their nationality information.

    WHAT IT DOES:
        Calls the "people" endpoint which gives us full player bios
        including nationality, birth country, height, weight, team, etc.

    WHY "PEOPLE" NOT "PLAYERS":
        The /people endpoint includes coaches too, but more importantly,
        it includes NATIONALITY data which the /stats endpoint doesn't have.
        This is crucial for identifying American players.

    RETURNS:
        list: A list of player record dictionaries

    EXAMPLE RESPONSE (one record):
        {
            'person': {
                'code': 'PJTU',
                'name': 'James, Jalen',
                'country': {'code': 'USA', 'name': 'United States'},
                'birthCountry': {'code': 'USA', 'name': 'United States'},
                'birthDate': '1998-05-10',
                'height': 196,
                'weight': 91
            },
            'club': {
                'code': 'BAR',
                'name': 'FC Barcelona'
            },
            'position': 'Guard',
            'dorsal': '13'
        }
    """
    logger.info("Fetching players...")

    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/people')

    if data:
        people = data.get('data', [])
        logger.info(f"  Found {len(people)} people records")
        return people

    return []


def fetch_games():
    """
    Fetch all games (schedule) for the season.

    WHAT IT DOES:
        Gets the complete game schedule including past results and future games.

    RETURNS:
        list: A list of game dictionaries

    KEY FIELDS IN EACH GAME:
        - gameCode: Unique ID for the game (e.g., 1)
        - date: When the game is/was played (ISO format)
        - played: True if game is finished, False if upcoming
        - local: Home team info including score
        - road: Away team info including score
        - round: What round of the season (1-34 for regular season)
        - winner: Which team won (only if played=True)

    EXAMPLE RESPONSE (one game):
        {
            'gameCode': 1,
            'date': '2024-10-03T19:00:00',
            'played': True,
            'round': 1,
            'local': {
                'club': {'code': 'MAD', 'name': 'Real Madrid'},
                'score': 87
            },
            'road': {
                'club': {'code': 'BAR', 'name': 'FC Barcelona'},
                'score': 79
            },
            'winner': {'code': 'MAD', 'name': 'Real Madrid'}
        }
    """
    logger.info("Fetching games/schedule...")

    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/games')

    if data:
        games = data.get('data', [])
        logger.info(f"  Found {len(games)} games")
        return games

    return []


def fetch_game_stats(game_code):
    """
    Fetch detailed box score statistics for a specific game.

    WHAT IT DOES:
        Gets the full box score for a game including every player's
        stats (points, rebounds, assists, minutes, etc.)

    PARAMETERS:
        game_code (int or str): The unique identifier for the game

    RETURNS:
        dict or None: The full game stats, or None if error/not available

    IMPORTANT NOTES ABOUT THE RESPONSE STRUCTURE:
        The stats are NESTED! Don't make this mistake:

        WRONG: player_stat.get('points')  # Returns None!
        RIGHT: player_stat.get('stats', {}).get('points')

        Also, some field names are different than you might expect:
        - 'assistances' not 'assists'
        - 'valuation' not 'pir' (Performance Index Rating)
        - 'timePlayed' is in SECONDS, not minutes

    RESPONSE STRUCTURE:
        {
            'local': {
                'players': [
                    {
                        'player': {
                            'dorsal': '7',
                            'positionName': 'Guard',
                            'person': {
                                'code': 'PJTU',
                                'name': 'James, Jalen',
                                'country': {'code': 'USA', ...}
                            }
                        },
                        'stats': {  # <-- STATS ARE NESTED HERE!
                            'points': 15,
                            'totalRebounds': 4,
                            'assistances': 6,  # <-- Note: not 'assists'
                            'timePlayed': 1800,  # <-- In SECONDS!
                            'valuation': 18,  # <-- This is PIR
                            ...
                        }
                    },
                    ...
                ]
            },
            'road': { ... same structure ... }
        }
    """
    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/games/{game_code}/stats')
    return data


# =============================================================================
# DATA PROCESSING FUNCTIONS
# =============================================================================

def process_games(games, mode='all'):
    """
    Filter games based on the selected mode.

    WHAT IT DOES:
        Takes the full list of games and filters it based on what you want:
        - 'all': Return all games (no filtering)
        - 'today': Return only today's games
        - 'recent': Return games from the last 7 days

    PARAMETERS:
        games (list): The full list of game dictionaries
        mode (str): One of 'all', 'today', or 'recent'

    RETURNS:
        list: The filtered list of games

    WHY WE NEED THIS:
        Running the full scrape (330 games) takes time because we need
        to fetch box scores for each game individually. For daily updates,
        we only need to check recent games for new scores.
    """
    now = datetime.now()

    if mode == 'today':
        # Filter to only today's games
        today = now.date()
        # Compare just the date part (first 10 characters of ISO string)
        filtered = [g for g in games if g.get('date', '')[:10] == str(today)]
        logger.info(f"  Today's games: {len(filtered)}")
        return filtered

    elif mode == 'recent':
        # Filter to games from the last 7 days
        week_ago = now - timedelta(days=7)
        # Only include games that are played AND within the time window
        filtered = [g for g in games
                   if g.get('played') and g.get('date', '') >= week_ago.isoformat()]
        logger.info(f"  Recent games (7 days): {len(filtered)}")
        return filtered

    else:  # mode == 'all'
        # Return everything
        return games


def extract_american_performances(game, stats):
    """
    Extract performance data for American players from a game's box score.

    WHAT IT DOES:
        Goes through all players in a game's box score, finds the Americans,
        and extracts their stats into a clean, consistent format.

    PARAMETERS:
        game (dict): The game info (date, teams, scores)
        stats (dict): The box score data from fetch_game_stats()

    RETURNS:
        list: A list of performance dictionaries for American players

    HOW IT WORKS:
        1. Loop through both teams (local/road)
        2. For each player, check if they're American
        3. If yes, extract all their stats into a clean dictionary
        4. Return the list of all American performances

    THE RETURNED DATA INCLUDES:
        - Game info: date, teams, scores, round
        - Player info: name, code, position, jersey number
        - Stats: points, rebounds, assists, steals, blocks, etc.
        - Advanced: field goal attempts/makes, three-pointers, free throws
        - Plus/minus and PIR (Performance Index Rating)
    """
    performances = []

    # If no stats data, return empty list
    if not stats:
        return performances

    # Extract game information that we'll include with each player
    game_info = {
        'game_code': game.get('gameCode'),
        'date': game.get('date'),
        'round': game.get('round'),
        # Navigate nested dictionaries safely with .get()
        # game -> local -> club -> name
        'local_team': game.get('local', {}).get('club', {}).get('name'),
        'local_score': game.get('local', {}).get('score'),
        'road_team': game.get('road', {}).get('club', {}).get('name'),
        'road_score': game.get('road', {}).get('score'),
    }

    # Loop through both teams: 'local' (home) and 'road' (away)
    for side in ['local', 'road']:
        # Get the team's stats data
        team_data = stats.get(side, {})
        team_name = game.get(side, {}).get('club', {}).get('name', 'Unknown')

        # Loop through each player in the team's box score
        for player_stat in team_data.get('players', []):
            # The data is nested: player_stat -> player -> person
            player = player_stat.get('player', {})
            person = player.get('person', {})

            # IMPORTANT: Stats are nested under 'stats' key!
            stat = player_stat.get('stats', {})

            # Check both nationality and birth country
            # Some players have US citizenship but play for another country
            country = person.get('country', {})
            birth_country = person.get('birthCountry', {})

            # If they're American (by either nationality or birth)
            if is_american(country) or is_american(birth_country):
                # Convert time played from seconds to minutes
                # The API gives us seconds (e.g., 1800 for 30 minutes)
                time_played = stat.get('timePlayed', 0)
                minutes = round(time_played / 60, 1) if time_played else 0

                # Build the performance dictionary
                # We use ** to merge game_info into this dict
                perf = {
                    # Include all game info
                    **game_info,
                    # Add player info
                    'team': team_name,
                    'player_code': person.get('code'),
                    'player_name': person.get('name'),
                    'nationality': country.get('name') if country else None,
                    'birth_country': birth_country.get('name') if birth_country else None,
                    'jersey': player.get('dorsal'),
                    'position': player.get('positionName'),
                    'starter': stat.get('startFive', False),
                    'minutes': minutes,
                    # Basic stats - use int() and handle None values
                    'points': int(stat.get('points', 0) or 0),
                    'rebounds': int(stat.get('totalRebounds', 0) or 0),
                    'assists': int(stat.get('assistances', 0) or 0),  # Note: 'assistances'!
                    'steals': int(stat.get('steals', 0) or 0),
                    'blocks': int(stat.get('blocksFavour', 0) or 0),
                    'turnovers': int(stat.get('turnovers', 0) or 0),
                    # Shooting stats
                    'fg_made': int(stat.get('fieldGoalsMadeTotal', 0) or 0),
                    'fg_attempted': int(stat.get('fieldGoalsAttemptedTotal', 0) or 0),
                    'three_made': int(stat.get('fieldGoalsMade3', 0) or 0),
                    'three_attempted': int(stat.get('fieldGoalsAttempted3', 0) or 0),
                    'ft_made': int(stat.get('freeThrowsMade', 0) or 0),
                    'ft_attempted': int(stat.get('freeThrowsAttempted', 0) or 0),
                    # Advanced stats
                    'plus_minus': int(stat.get('plusMinus', 0) or 0),
                    'pir': int(stat.get('valuation', 0) or 0),  # PIR = 'valuation' in API
                }
                performances.append(perf)

    return performances


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main entry point for the scraper.

    WHAT IT DOES:
        1. Parses command line arguments to determine mode
        2. Fetches all clubs and saves to JSON
        3. Fetches all players, identifies Americans, saves to JSON
        4. Fetches game schedule, filters by mode, saves to JSON
        5. For each played game, fetches box scores
        6. Extracts American player performances
        7. Calculates season averages
        8. Saves all data to JSON files
        9. Prints a summary of what was found

    COMMAND LINE ARGUMENTS:
        --recent: Only process games from the last 7 days
        --today: Only process today's games
        --no-boxscores: Skip fetching individual game stats
    """
    # =========================================================================
    # Parse Command Line Arguments
    # =========================================================================
    # argparse makes it easy to handle command-line options
    parser = argparse.ArgumentParser(description='EuroLeague Daily Scraper')
    parser.add_argument('--recent', action='store_true',
                       help='Only recent games (7 days)')
    parser.add_argument('--today', action='store_true',
                       help='Only today\'s games')
    parser.add_argument('--no-boxscores', action='store_true',
                       help='Skip box score fetching')
    args = parser.parse_args()

    # Determine which mode to use
    # Priority: --today > --recent > all
    mode = 'today' if args.today else ('recent' if args.recent else 'all')

    # Print header
    logger.info("=" * 60)
    logger.info(f"EUROLEAGUE DAILY SCRAPER - Mode: {mode.upper()}")
    logger.info("=" * 60)

    # Generate timestamp for file names
    # Format: YYYYMMDD_HHMMSS (e.g., 20240115_143022)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # Step 1: Fetch Clubs
    # =========================================================================
    clubs = fetch_clubs()
    if clubs:
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'count': len(clubs),
            'clubs': clubs
        }, f'clubs_{timestamp}.json')

    # =========================================================================
    # Step 2: Fetch Players
    # =========================================================================
    people = fetch_players()

    # Process players and identify Americans
    all_players = []
    american_players = []

    for record in people:
        # Extract data from nested structure
        person = record.get('person', {})
        club = record.get('club', {})
        country = person.get('country', {})
        birth_country = person.get('birthCountry', {})

        # Extract image URLs (headshot and action photos)
        images = record.get('images', {})

        # Build a clean player dictionary
        player = {
            'code': person.get('code'),
            'name': person.get('name'),
            'nationality': country.get('name') if country else None,
            'nationality_code': country.get('code') if country else None,
            'birth_country': birth_country.get('name') if birth_country else None,
            'birth_country_code': birth_country.get('code') if birth_country else None,
            'birth_date': person.get('birthDate'),
            'height': person.get('height'),
            'weight': person.get('weight'),
            'team_code': club.get('code') if club else None,
            'team_name': club.get('name') if club else None,
            'position': record.get('position'),
            'jersey': record.get('dorsal'),
            'headshot_url': images.get('headshot'),
            'action_url': images.get('action'),
        }
        all_players.append(player)

        # Check if American (by nationality or birth country)
        if is_american(country) or is_american(birth_country):
            american_players.append(player)

    # Deduplicate American players
    # Some players appear multiple times if they changed teams
    seen_codes = set()
    unique_americans = []
    for p in american_players:
        if p['code'] not in seen_codes:
            seen_codes.add(p['code'])
            unique_americans.append(p)

    logger.info(f"  American players: {len(unique_americans)}")

    # Save all players
    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'count': len(all_players),
        'players': all_players
    }, f'players_{timestamp}.json')

    # Save American players
    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'count': len(unique_americans),
        'players': unique_americans
    }, f'american_players_{timestamp}.json')

    # =========================================================================
    # Step 3: Fetch Games/Schedule
    # =========================================================================
    all_games = fetch_games()
    games = process_games(all_games, mode)

    # Separate played and upcoming games
    played_games = [g for g in games if g.get('played')]
    upcoming_games = [g for g in games if not g.get('played')]

    logger.info(f"  Played: {len(played_games)}, Upcoming: {len(upcoming_games)}")

    # Save schedule
    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'mode': mode,
        'total_games': len(games),
        'played': len(played_games),
        'upcoming': len(upcoming_games),
        'games': games
    }, f'schedule_{timestamp}.json')

    # =========================================================================
    # Step 4: Fetch Box Scores for Played Games
    # =========================================================================
    all_american_performances = []
    game_recaps = []

    # Only fetch box scores if we have played games and --no-boxscores wasn't used
    if not args.no_boxscores and played_games:
        logger.info(f"\nFetching box scores for {len(played_games)} played games...")

        # Loop through each played game
        for i, game in enumerate(played_games):
            game_code = game.get('gameCode')

            # Show progress every 20 games
            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i+1}/{len(played_games)}")

            # Fetch the box score for this game
            stats = fetch_game_stats(game_code)

            if stats:
                # Extract American player performances
                perfs = extract_american_performances(game, stats)
                all_american_performances.extend(perfs)

                # Create a game recap summary
                recap = {
                    'game_code': game_code,
                    'date': game.get('date'),
                    'round': game.get('round'),
                    'phase': game.get('phaseType', {}).get('name'),
                    'local': {
                        'team': game.get('local', {}).get('club', {}).get('name'),
                        'score': game.get('local', {}).get('score'),
                        'quarters': game.get('local', {}).get('partials', {}),
                    },
                    'road': {
                        'team': game.get('road', {}).get('club', {}).get('name'),
                        'score': game.get('road', {}).get('score'),
                        'quarters': game.get('road', {}).get('partials', {}),
                    },
                    'winner': (game.get('winner') or {}).get('name'),
                    'venue': (game.get('venue') or {}).get('name'),
                    'american_players_count': len(perfs),
                }
                game_recaps.append(recap)

            # IMPORTANT: Rate limiting!
            # Add a small delay between requests to avoid overwhelming the API
            time.sleep(0.2)

    # Save game recaps
    if game_recaps:
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'mode': mode,
            'game_count': len(game_recaps),
            'games': game_recaps
        }, f'game_recaps_{timestamp}.json')

    # =========================================================================
    # Step 5: Process American Player Statistics
    # =========================================================================
    if all_american_performances:
        # Save raw performance data
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'mode': mode,
            'performance_count': len(all_american_performances),
            'performances': all_american_performances
        }, f'american_performances_{timestamp}.json')

        # Calculate season averages for each player
        # We'll aggregate all their games into totals, then calculate averages
        player_stats = {}

        for perf in all_american_performances:
            code = perf['player_code']

            # Initialize player if first time seeing them
            if code not in player_stats:
                player_stats[code] = {
                    'player_code': code,
                    'player_name': perf['player_name'],
                    'team': perf['team'],
                    'nationality': perf['nationality'],
                    'games_played': 0,
                    'total_points': 0,
                    'total_rebounds': 0,
                    'total_assists': 0,
                    'performances': []  # Keep list of individual games
                }

            # Add this game's stats to their totals
            ps = player_stats[code]
            ps['games_played'] += 1
            ps['total_points'] += perf.get('points') or 0
            ps['total_rebounds'] += perf.get('rebounds') or 0
            ps['total_assists'] += perf.get('assists') or 0

            # Store the individual game performance
            ps['performances'].append({
                'date': perf['date'],
                'opponent': perf['road_team'] if perf['team'] == perf['local_team'] else perf['local_team'],
                'points': perf.get('points'),
                'rebounds': perf.get('rebounds'),
                'assists': perf.get('assists'),
                'minutes': perf.get('minutes'),
            })

        # Calculate per-game averages (PPG, RPG, APG)
        for ps in player_stats.values():
            gp = ps['games_played']
            if gp > 0:
                ps['ppg'] = round(ps['total_points'] / gp, 1)
                ps['rpg'] = round(ps['total_rebounds'] / gp, 1)
                ps['apg'] = round(ps['total_assists'] / gp, 1)

        # Sort by PPG (highest first)
        player_summary = sorted(player_stats.values(),
                               key=lambda x: x.get('ppg', 0),
                               reverse=True)

        # Save player season stats
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'player_count': len(player_summary),
            'players': player_summary
        }, f'american_player_stats_{timestamp}.json')

    # =========================================================================
    # Step 6: Print Summary
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Clubs: {len(clubs)}")
    logger.info(f"Total players: {len(all_players)}")
    logger.info(f"American players: {len(unique_americans)}")
    logger.info(f"Games (mode={mode}): {len(games)} (played: {len(played_games)}, upcoming: {len(upcoming_games)})")
    logger.info(f"American game performances: {len(all_american_performances)}")

    # Show top performances if we have any
    if all_american_performances:
        # Sort by points to find top scoring games
        top_games = sorted(all_american_performances,
                          key=lambda x: x.get('points') or 0,
                          reverse=True)[:5]
        logger.info("\nTop American performances:")
        for p in top_games:
            # Determine opponent (the other team)
            opponent = p['road_team'] if p['team'] == p['local_team'] else p['local_team']
            logger.info(f"  {p['player_name']}: {p['points']} pts vs {opponent} ({p['date'][:10]})")


# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================
# This is the standard Python idiom for making a script runnable
# When you run "python daily_scraper.py", Python sets __name__ to '__main__'
# This allows the file to also be imported as a module without running main()

if __name__ == '__main__':
    main()
