"""
=============================================================================
JOIN ALL DATA INTO UNIFIED DATASET
=============================================================================

PURPOSE:
    This script combines data from multiple sources into a single, comprehensive
    dataset that's easy to use for analysis, display, or export.

WHY WE NEED THIS:
    Our scraping process creates several separate JSON files:
    - american_players_*.json: Basic player info (name, team, nationality)
    - american_hometowns_*.json: Hometown and college info from Wikipedia
    - american_player_stats_*.json: Season averages (PPG, RPG, APG)
    - american_performances_*.json: Game-by-game box scores

    This script joins all that data together by player code, creating one
    unified record per player with all their information in one place.

WHAT THE OUTPUT LOOKS LIKE:
    For each player, the unified data includes:
    - Basic info: name, team, position, jersey, height, birthdate
    - Background: hometown city/state, college, high school
    - Season stats: games played, PPG, RPG, APG, totals
    - Recent games: last 5 game performances with stats
    - All games: complete game-by-game log for the season

OUTPUT FILES:
    - unified_american_players_TIMESTAMP.json: Full data with all games
    - american_players_summary_TIMESTAMP.json: Summary without game logs

USE CASES:
    - Website display: Show player profiles with stats and hometown
    - Local news: Find players from specific states/cities
    - Analysis: Compare player performances over time
    - Export: Provide data to other systems or visualizations

SCHEDULE:
    - Runs after daily_scraper.py and hometown_lookup_fixed.py
    - Part of the GitHub Actions daily workflow
"""

# =============================================================================
# IMPORTS
# =============================================================================
# json: For reading input files and writing output
import json

# os: For file path operations
import os

# datetime: For timestamps in output files
from datetime import datetime

# logging: For status messages
import logging

# glob: For finding files matching a pattern (e.g., "clubs_*.json")
from glob import glob

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# FILE LOADING FUNCTIONS
# =============================================================================

def load_latest_json(pattern):
    """
    Load the most recent JSON file matching a pattern.

    WHAT IT DOES:
        Finds all files in output/json/ matching the pattern, sorts them
        (which puts them in chronological order since filenames have timestamps),
        and loads the most recent one.

    PARAMETERS:
        pattern (str): A glob pattern like 'clubs_*.json' or 'american_players_2*.json'

    RETURNS:
        dict or None: The parsed JSON data, or None if no files found

    EXAMPLE:
        >>> data = load_latest_json('clubs_*.json')
        >>> print(data['count'])
        18

    WHY WE NEED THIS:
        Each scrape creates new files with timestamps. We always want to use
        the most recent data, so we sort files and take the last one.
    """
    # Build the path to the output directory
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')

    # Find all files matching the pattern
    # glob() returns a list of full file paths
    files = sorted(glob(os.path.join(output_dir, pattern)))

    if not files:
        return None

    # Load and return the most recent file (last in sorted list)
    with open(files[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, filename):
    """
    Save data to a JSON file in the output directory.

    PARAMETERS:
        data (dict): The data to save
        filename (str): The filename (e.g., 'unified_american_players_20240115.json')

    This is the same save function used across all scripts for consistency.
    """
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        # indent=2: Pretty-print with 2-space indentation
        # default=str: Convert non-JSON types (like datetime) to strings
        # ensure_ascii=False: Keep non-ASCII characters (European names)
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")


# =============================================================================
# HEIGHT CONVERSION
# =============================================================================

def cm_to_feet_inches(cm):
    """
    Convert centimeters to feet and inches.

    PARAMETERS:
        cm (int/float): Height in centimeters

    RETURNS:
        tuple: (feet, inches) as integers, or (None, None) if input is invalid

    EXAMPLE:
        >>> cm_to_feet_inches(195)
        (6, 5)  # 195 cm = 6'5"
    """
    if not cm:
        return None, None
    total_inches = cm / 2.54
    feet = int(total_inches // 12)
    inches = int(round(total_inches % 12))
    # Handle rounding to 12 inches
    if inches == 12:
        feet += 1
        inches = 0
    return feet, inches


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main entry point for the data joining script.

    WHAT IT DOES:
        1. Load all data sources (players, hometowns, stats, performances)
        2. Build lookup dictionaries for fast access by player code
        3. For each player, combine data from all sources
        4. Sort players by PPG (points per game)
        5. Save unified data (full version and summary version)
        6. Print statistics about players by state

    DATA FLOW:
        players_data ─────┐
        hometowns_data ───┼──► unified_player ──► JSON output
        stats_data ───────┤
        performances_data ┘
    """
    logger.info("=" * 60)
    logger.info("JOINING ALL DATA")
    logger.info("=" * 60)

    # Generate timestamp for output files
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # Step 1: Load All Data Sources
    # =========================================================================
    logger.info("Loading data sources...")

    # Load player data - the core list of American players
    # Pattern explanation: '2*' matches files starting with '2' (year 2024, 2025, etc.)
    players_data = load_latest_json('american_players_2*.json')

    # Load hometown data from Wikipedia lookups
    # The '_found_' version only has successful lookups
    hometowns_data = load_latest_json('american_hometowns_found_*.json')

    # Load season statistics (aggregated from all games)
    stats_data = load_latest_json('american_player_stats_*.json')

    # Load individual game performances
    performances_data = load_latest_json('american_performances_*.json')

    # Load schedule for total games count
    schedule_data = load_latest_json('schedule_*.json')

    # Load clubs for team information
    clubs_data = load_latest_json('clubs_*.json')

    # Check that we have the essential player data
    if not players_data:
        logger.error("No player data found")
        return

    # =========================================================================
    # Step 2: Build Lookup Dictionaries
    # =========================================================================
    # Lookup dictionaries let us quickly find data by player code
    # Instead of searching through a list each time, we can do: lookup[code]
    # This is much faster, especially with hundreds of players

    # ---------------------------------------------------------------------
    # Hometown Lookup
    # ---------------------------------------------------------------------
    # Structure: { 'PJTU': {'hometown_city': 'Chicago', 'hometown_state': 'Illinois', ...} }
    hometown_lookup = {}
    if hometowns_data:
        for p in hometowns_data.get('players', []):
            code = p.get('code')
            if code:
                hometown_lookup[code] = {
                    'hometown_city': p.get('hometown_city'),
                    'hometown_state': p.get('hometown_state'),
                    'college': p.get('college'),
                    'high_school': p.get('high_school'),
                }
        logger.info(f"  Loaded {len(hometown_lookup)} hometown records")

    # ---------------------------------------------------------------------
    # Stats Lookup
    # ---------------------------------------------------------------------
    # Structure: { 'PJTU': {'games_played': 20, 'ppg': 15.5, ...} }
    stats_lookup = {}
    if stats_data:
        for p in stats_data.get('players', []):
            # Note: stats use 'player_code', not just 'code'
            code = p.get('player_code')
            if code:
                stats_lookup[code] = {
                    'games_played': p.get('games_played', 0),
                    'total_points': p.get('total_points', 0),
                    'total_rebounds': p.get('total_rebounds', 0),
                    'total_assists': p.get('total_assists', 0),
                    'ppg': p.get('ppg', 0),  # Points Per Game
                    'rpg': p.get('rpg', 0),  # Rebounds Per Game
                    'apg': p.get('apg', 0),  # Assists Per Game
                }
        logger.info(f"  Loaded {len(stats_lookup)} player stats")

    # ---------------------------------------------------------------------
    # Performances Lookup
    # ---------------------------------------------------------------------
    # Structure: { 'PJTU': [game1, game2, game3, ...] }
    # Each player has a list of their game performances
    perf_lookup = {}
    if performances_data:
        for p in performances_data.get('performances', []):
            code = p.get('player_code')
            if code:
                # Initialize the list if this is the first game for this player
                if code not in perf_lookup:
                    perf_lookup[code] = []

                # Determine opponent and home/away status
                # If player's team is the local team, opponent is the road team
                is_home = p.get('team') == p.get('local_team')
                opponent = p.get('road_team') if is_home else p.get('local_team')
                team_score = p.get('local_score') if is_home else p.get('road_score')
                opp_score = p.get('road_score') if is_home else p.get('local_score')

                # Determine if their team won
                # Win if: home and local_score > road_score, or away and road_score > local_score
                won = ((is_home and p.get('local_score', 0) > p.get('road_score', 0)) or
                       (not is_home and p.get('road_score', 0) > p.get('local_score', 0)))

                # Build the game record
                perf_lookup[code].append({
                    'date': p.get('date'),
                    'opponent': opponent,
                    'home_away': 'home' if is_home else 'away',
                    'team_score': team_score,
                    'opp_score': opp_score,
                    'result': 'W' if won else 'L',
                    'points': p.get('points'),
                    'rebounds': p.get('rebounds'),
                    'assists': p.get('assists'),
                    'steals': p.get('steals'),
                    'blocks': p.get('blocks'),
                    'minutes': p.get('minutes'),
                    # Format shooting stats as "made/attempted"
                    'fg': f"{p.get('fg_made', 0)}/{p.get('fg_attempted', 0)}",
                    'three': f"{p.get('three_made', 0)}/{p.get('three_attempted', 0)}",
                    'ft': f"{p.get('ft_made', 0)}/{p.get('ft_attempted', 0)}",
                    'plus_minus': p.get('plus_minus'),
                    'pir': p.get('pir'),  # Performance Index Rating
                })
        logger.info(f"  Loaded performances for {len(perf_lookup)} players")

    # =========================================================================
    # Step 3: Build Unified Player Records
    # =========================================================================
    unified_players = []
    players = players_data.get('players', [])

    for player in players:
        code = player.get('code')

        # Get data from lookup tables (empty dict if not found)
        hometown = hometown_lookup.get(code, {})
        stats = stats_lookup.get(code, {})
        games = perf_lookup.get(code, [])

        # Sort games by date (most recent first)
        games = sorted(games, key=lambda x: x.get('date', ''), reverse=True)

        # Clean up the player's name
        # API format: "James, LeBron" -> "LeBron James"
        name = player.get('name', '')
        if ', ' in name:
            parts = name.split(', ', 1)
            name = f"{parts[1]} {parts[0]}".title()

        # Convert height from cm to feet/inches
        height_cm = player.get('height')
        height_feet, height_inches = cm_to_feet_inches(height_cm)

        # Convert birth_date from "YYYY-MM-DDTHH:MM:SS" to "YYYY-MM-DD"
        raw_birth_date = player.get('birth_date', '')
        birth_date = raw_birth_date[:10] if raw_birth_date else None

        # Build the unified player record
        # This combines data from all our sources into one comprehensive record
        unified = {
            # -----------------------------------------------------------------
            # Basic Player Information
            # -----------------------------------------------------------------
            'code': code,                              # Unique identifier
            'name': name,                              # Cleaned name
            'team': player.get('team_name'),           # Current team
            'team_code': player.get('team_code'),      # Team code (e.g., 'BAR')
            'position': player.get('position'),        # Guard, Forward, Center
            'jersey': player.get('jersey'),            # Jersey number
            'height_cm': height_cm,                    # Height in centimeters
            'height_feet': height_feet,                # Height feet component
            'height_inches': height_inches,            # Height inches component
            'birth_date': birth_date,                  # YYYY-MM-DD format
            'nationality': player.get('nationality'),  # Country
            'birth_country': player.get('birth_country'),
            'headshot_url': player.get('headshot_url'),  # Player headshot image
            'action_url': player.get('action_url'),      # Player action photo

            # -----------------------------------------------------------------
            # Hometown/College Information (from Wikipedia)
            # -----------------------------------------------------------------
            'hometown_city': hometown.get('hometown_city'),
            'hometown_state': hometown.get('hometown_state'),
            # Combined hometown string for display
            'hometown': f"{hometown.get('hometown_city')}, {hometown.get('hometown_state')}"
                       if hometown.get('hometown_city') and hometown.get('hometown_state')
                       else None,
            'college': hometown.get('college'),
            'high_school': hometown.get('high_school'),

            # -----------------------------------------------------------------
            # Season Statistics
            # -----------------------------------------------------------------
            # Use stats if available, otherwise count from games list
            'games_played': stats.get('games_played', len(games)),
            'ppg': stats.get('ppg', 0),                # Points per game
            'rpg': stats.get('rpg', 0),                # Rebounds per game
            'apg': stats.get('apg', 0),                # Assists per game
            'total_points': stats.get('total_points', 0),
            'total_rebounds': stats.get('total_rebounds', 0),
            'total_assists': stats.get('total_assists', 0),

            # -----------------------------------------------------------------
            # Game Performances
            # -----------------------------------------------------------------
            'recent_games': games[:5],  # Last 5 games for quick display
            'all_games': games,         # Full game log

            # -----------------------------------------------------------------
            # Upcoming Games (from schedule)
            # -----------------------------------------------------------------
            'upcoming_games': [],  # Will be populated below
        }

        # Build upcoming games for this player's team
        team_code = player.get('team_code')
        if schedule_data and team_code:
            for game in schedule_data.get('games', []):
                if not game.get('played'):
                    local_code = game.get('local', {}).get('club', {}).get('code')
                    road_code = game.get('road', {}).get('club', {}).get('code')
                    if team_code in (local_code, road_code):
                        is_home = (team_code == local_code)
                        unified['upcoming_games'].append({
                            'date': game.get('date', '')[:10],
                            'opponent': game.get('road', {}).get('club', {}).get('name') if is_home else game.get('local', {}).get('club', {}).get('name'),
                            'home_away': 'Home' if is_home else 'Away',
                            'round': game.get('round'),
                            'venue': game.get('venue', {}).get('name'),
                        })
            # Sort upcoming games by date
            unified['upcoming_games'].sort(key=lambda x: x.get('date', ''))

        unified_players.append(unified)

    # Sort by PPG (highest scorers first)
    unified_players.sort(key=lambda x: x.get('ppg', 0), reverse=True)

    logger.info(f"\nUnified {len(unified_players)} players")

    # =========================================================================
    # Step 4: Save Full Unified Data
    # =========================================================================
    full_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': '2025-26',
        'total_players': len(unified_players),
        'total_games_in_season': schedule_data.get('total_games', 0) if schedule_data else 0,
        'clubs': clubs_data.get('clubs', []) if clubs_data else [],
        'players': unified_players,
    }
    save_json(full_export, f'unified_american_players_{timestamp}.json')

    # =========================================================================
    # Step 5: Save Summary Version (without full game logs)
    # =========================================================================
    # The summary version is smaller and faster to load
    # It includes recent_games but not all_games
    summary_players = []
    for p in unified_players:
        # Copy all fields except 'all_games'
        summary = {k: v for k, v in p.items() if k != 'all_games'}
        summary_players.append(summary)

    summary_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': '2025-26',
        'total_players': len(summary_players),
        'players': summary_players,
    }
    save_json(summary_export, f'american_players_summary_{timestamp}.json')

    # =========================================================================
    # Step 6: Print Statistics
    # =========================================================================
    # Show top performers
    logger.info("\n" + "=" * 60)
    logger.info("TOP AMERICAN PLAYERS BY PPG")
    logger.info("=" * 60)
    for p in unified_players[:15]:
        hometown = p.get('hometown') or 'Unknown'
        # Format: Name (25 chars) | Team (30 chars) | PPG | Hometown
        logger.info(f"  {p['name']:25} {p['team']:30} {p['ppg']:5.1f} PPG | {hometown}")

    # Count players by state
    logger.info("\n" + "=" * 60)
    logger.info("PLAYERS BY STATE")
    logger.info("=" * 60)

    # Build a dictionary: { 'California': ['Player 1', 'Player 2'], ... }
    by_state = {}
    for p in unified_players:
        state = p.get('hometown_state')
        if state:
            if state not in by_state:
                by_state[state] = []
            by_state[state].append(p['name'])

    # Sort states by number of players (most first) and show top 10
    for state in sorted(by_state.keys(), key=lambda s: len(by_state[s]), reverse=True)[:10]:
        logger.info(f"  {state}: {len(by_state[state])} players")


# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    main()
