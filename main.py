"""
=============================================================================
MAIN PIPELINE ORCHESTRATOR
=============================================================================

This is the main entry point for the EuroLeague data collection system.
Think of it as the "conductor" of an orchestra - it coordinates all the
different components (scrapers, services, database) to work together.

WHAT DOES THIS FILE DO?
-----------------------
1. Loads configuration from files
2. Connects all components together (scrapers, database, services)
3. Provides command-line interface for running different operations
4. Orchestrates the data flow from websites -> processing -> database -> export

HOW TO RUN THIS:
----------------
From the command line:

    # Full sync - scrape everything
    python main.py --full

    # Scrape teams only
    python main.py --teams

    # Scrape rosters only
    python main.py --rosters

    # Scrape schedule only
    python main.py --schedule

    # Scrape game statistics for recent games
    python main.py --stats

    # Process hometown lookups for American players
    python main.py --hometowns

    # Export data to JSON files
    python main.py --export

    # Combine multiple operations
    python main.py --teams --rosters --export

THE DATA PIPELINE:
------------------
Here's how data flows through the system:

    1. TEAMS
       EuroLeague Website → EuroLeagueScraper → teams table

    2. ROSTERS (for each team)
       EuroLeague Website → EuroLeagueScraper → players table
       (American players are flagged for hometown lookup)

    3. SCHEDULE
       EuroLeague Website → EuroLeagueScraper → schedule table

    4. HOMETOWN LOOKUP (for American players)
       Basketball Reference → Wikipedia → Grokepedia → players table
       (Updates hometown_city, hometown_state, high_school)

    5. GAME STATS (for completed games)
       EuroLeague Website → EuroLeagueScraper → game_stats table

    6. EXPORT
       Database tables → JSON files in output/json/

DEPENDENCIES:
-------------
- All the scrapers (euroleague, basketball_ref, wikipedia, grokepedia)
- Database connector
- Services (hometown_lookup, photo_processor)
- Configuration files (config/settings.py, config/league_config.json)
"""

# =============================================================================
# IMPORTS
# =============================================================================

# argparse is Python's built-in library for parsing command-line arguments
# It lets users run: python main.py --teams --export
import argparse

# logging for tracking what the program is doing
import logging

# datetime for timestamps on exports and date calculations
from datetime import datetime, date, timedelta

# json for reading config files and writing export files
import json

# os for file path operations (creating directories, etc.)
import os

# sys for system-level operations (like exiting with error codes)
import sys

# -----------------------------------------------------------------------------
# Import our configuration
# -----------------------------------------------------------------------------
# These are loaded from the config/ directory
# DB_CONFIG contains database connection settings
# OUTPUT_CONFIG contains paths for JSON exports
from config.settings import DB_CONFIG, OUTPUT_CONFIG

# -----------------------------------------------------------------------------
# Import our database connector
# -----------------------------------------------------------------------------
# MySQLConnector handles all database operations
from database.mysql_connector import MySQLConnector

# -----------------------------------------------------------------------------
# Import our scrapers
# -----------------------------------------------------------------------------
# EuroLeagueScraper gets data from the EuroLeague website
from scrapers.euroleague_scraper import EuroLeagueScraper

# -----------------------------------------------------------------------------
# Import our services
# -----------------------------------------------------------------------------
# HometownLookupService coordinates lookups from multiple sources
from services.hometown_lookup import HometownLookupService

# PhotoProcessor handles player photo URL processing
from services.photo_processor import PhotoProcessor

# DataValidator validates data before database insertion
from services.data_validator import DataValidator


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
#
# Set up logging so we can track what the program is doing.
# This creates log messages like:
#   2024-01-15 10:30:45 - main - INFO - Starting full sync...
#
# Log levels (in order of severity):
# - DEBUG: Detailed information for debugging
# - INFO: General information about what's happening
# - WARNING: Something unexpected happened, but not an error
# - ERROR: Something failed
# - CRITICAL: Program cannot continue

logging.basicConfig(
    level=logging.INFO,  # Show INFO and above (INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    # Format: timestamp - logger name - level - message
)

# Get a logger for this module
logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PIPELINE CLASS
# =============================================================================

class EuroLeaguePipeline:
    """
    Main pipeline class that orchestrates all data collection operations.

    WHAT IS A PIPELINE?
    -------------------
    A pipeline is a series of processing steps where the output of one step
    feeds into the next. Our pipeline:

        Scrape Teams → Scrape Rosters → Process Hometowns → Flag Games → Export

    WHY USE A CLASS?
    ----------------
    Using a class lets us:
    1. Initialize all components once in __init__
    2. Share resources (like database connection) between methods
    3. Keep related functionality organized together

    ATTRIBUTES:
    -----------
    config : dict
        Loaded from config/league_config.json
    db : MySQLConnector
        Database connection for storing/retrieving data
    scraper : EuroLeagueScraper
        Scraper for EuroLeague website
    hometown_service : HometownLookupService
        Service for looking up American player hometowns
    photo_processor : PhotoProcessor
        Service for processing player photos
    validator : DataValidator
        Service for validating scraped data

    EXAMPLE USAGE:
    --------------
    pipeline = EuroLeaguePipeline()

    # Run a full sync
    pipeline.run_full_sync()

    # Or run individual operations
    pipeline.sync_teams()
    pipeline.sync_rosters()
    pipeline.export_json()
    """

    def __init__(self):
        """
        Initialize the pipeline by setting up all components.

        WHAT HAPPENS HERE:
        ------------------
        1. Load configuration from JSON file
        2. Create database connection
        3. Initialize all scrapers and services
        4. Everything is ready to use!

        This is called automatically when you create an instance:
            pipeline = EuroLeaguePipeline()
        """
        # =====================================================================
        # STEP 1: LOAD CONFIGURATION
        # =====================================================================
        #
        # Configuration is stored in config/league_config.json
        # It contains URLs, API endpoints, rate limits, etc.

        logger.info("Loading configuration...")

        # Get the directory where this script is located
        # This ensures we find the config file regardless of where
        # the script is run from
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config', 'league_config.json')

        try:
            # Open and read the JSON configuration file
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info("Configuration loaded successfully")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            logger.error("Please ensure config/league_config.json exists")
            # Raise exception to stop - we can't continue without config
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise

        # =====================================================================
        # STEP 2: INITIALIZE DATABASE CONNECTION
        # =====================================================================
        #
        # The database stores all our collected data.
        # DB_CONFIG comes from config/settings.py and contains:
        # - host, port, user, password, database name

        logger.info("Initializing database connection...")

        self.db = MySQLConnector(DB_CONFIG)

        # Test the connection
        if self.db.connect():
            logger.info("Database connection successful")
        else:
            logger.warning("Could not connect to database - some features may not work")
            logger.warning("Make sure MySQL is running and credentials are correct in .env")

        # =====================================================================
        # STEP 3: INITIALIZE SCRAPERS
        # =====================================================================
        #
        # Scrapers fetch data from websites.
        # We pass the 'league' section of our config which contains
        # URLs, API endpoints, and rate limits.

        logger.info("Initializing scrapers...")

        # The EuroLeague scraper fetches teams, rosters, schedules, and stats
        self.scraper = EuroLeagueScraper(self.config.get('league', {}))

        # =====================================================================
        # STEP 4: INITIALIZE SERVICES
        # =====================================================================
        #
        # Services provide higher-level functionality built on top of scrapers.

        logger.info("Initializing services...")

        # HometownLookupService coordinates lookups from Basketball Reference,
        # Wikipedia, and Grokepedia to find American player hometowns
        self.hometown_service = HometownLookupService(self.db)

        # PhotoProcessor handles fetching and categorizing player photos
        self.photo_processor = PhotoProcessor()

        # DataValidator checks data quality before database insertion
        self.validator = DataValidator()

        logger.info("Pipeline initialization complete!")

    # =========================================================================
    # MAIN SYNC METHODS
    # =========================================================================

    def run_full_sync(self):
        """
        Run a complete data refresh - teams, rosters, schedule, and hometowns.

        This is the most common operation. It:
        1. Gets all teams from EuroLeague
        2. Gets rosters for each team
        3. Gets the season schedule
        4. Looks up hometowns for American players
        5. Flags which games have American players

        USE WHEN:
        ---------
        - Setting up the system for the first time
        - Weekly refresh to catch roster changes
        - Starting a new season

        DURATION:
        ---------
        Can take 30+ minutes depending on:
        - Number of teams (18 in EuroLeague)
        - Rate limiting (2-3 seconds between requests)
        - Hometown lookups (3+ seconds per player for Basketball Reference)
        """
        logger.info("=" * 60)
        logger.info("STARTING FULL SYNC")
        logger.info("=" * 60)

        try:
            # Step 1: Sync all teams
            self.sync_teams()

            # Step 2: Sync rosters for all teams
            self.sync_rosters()

            # Step 3: Sync the season schedule
            self.sync_schedule()

            # Step 4: Look up hometowns for American players
            self.process_hometowns()

            # Step 5: Update schedule with American player flags
            self.flag_american_games()

            logger.info("=" * 60)
            logger.info("FULL SYNC COMPLETE!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            raise

    def sync_teams(self):
        """
        Sync all EuroLeague teams to the database.

        WHAT IT DOES:
        -------------
        1. Scrapes team list from EuroLeague (tries API first, then web)
        2. For each team, extracts: name, code, city, country, arena, logo
        3. Upserts each team into the database
           (upsert = insert if new, update if exists)

        DATA COLLECTED:
        ---------------
        - team_id: Normalized ID (e.g., EUROLEAGUE_real_madrid)
        - team_name: Display name (e.g., Real Madrid)
        - team_code: Short code (e.g., RMA)
        - team_slug: URL-friendly name for building URLs
        - city, country, arena: Location info
        - logo_url: Team logo image URL
        """
        logger.info("-" * 40)
        logger.info("SYNCING TEAMS")
        logger.info("-" * 40)

        # Call the scraper to get all teams
        # This returns a list of dictionaries, one per team
        teams = self.scraper.scrape_teams()

        logger.info(f"Found {len(teams)} teams")

        # Track success/failure counts
        success_count = 0
        error_count = 0

        # Process each team
        for team in teams:
            try:
                # Validate the team data before saving
                is_valid, errors = self.validator.validate_team(team)

                if not is_valid:
                    logger.warning(f"Invalid team data for {team.get('team_name', 'Unknown')}: {errors}")
                    error_count += 1
                    continue

                # Save to database
                # upsert_team will INSERT if team doesn't exist, UPDATE if it does
                if self.db.upsert_team(team):
                    logger.debug(f"Saved team: {team['team_name']}")
                    success_count += 1
                else:
                    logger.warning(f"Failed to save team: {team['team_name']}")
                    error_count += 1

            except Exception as e:
                logger.error(f"Error processing team {team.get('team_name', 'Unknown')}: {e}")
                error_count += 1

        logger.info(f"Teams sync complete: {success_count} saved, {error_count} errors")

    def sync_rosters(self):
        """
        Sync rosters for all teams.

        WHAT IT DOES:
        -------------
        1. Gets all teams from the database
        2. For each team, scrapes the roster from EuroLeague
        3. For each player:
           - Extracts: name, position, jersey number, height, nationality, etc.
           - Checks if player is American
           - Flags American players for hometown lookup
           - Saves to database

        AMERICAN PLAYER DETECTION:
        --------------------------
        We check the nationality field for variations like:
        - USA, United States, U.S.A., American, etc.

        If a player is American and we don't have their hometown info,
        they get flagged with needs_hometown_lookup = True
        """
        logger.info("-" * 40)
        logger.info("SYNCING ROSTERS")
        logger.info("-" * 40)

        # Get all teams from the database
        teams = self.db.get_all_teams()

        if not teams:
            logger.warning("No teams found in database. Run team sync first!")
            return

        logger.info(f"Processing rosters for {len(teams)} teams")

        # Track totals
        total_players = 0
        american_players = 0

        # Process each team
        for team in teams:
            team_name = team['team_name']
            team_id = team['team_id']
            team_slug = team.get('team_slug', '')

            logger.info(f"Processing roster for: {team_name}")

            try:
                # Scrape the roster
                # We pass team_slug for URL building and team_id for player assignment
                players = self.scraper.scrape_roster(team_slug, team_id)

                logger.info(f"  Found {len(players)} players")

                # Process each player
                for player in players:
                    # Ensure team assignment
                    player['team_id'] = team_id
                    player['league_id'] = 'EUROLEAGUE'

                    # Check if American and needs hometown lookup
                    if player.get('is_american'):
                        american_players += 1

                        # If we don't have hometown data, flag for lookup
                        if not player.get('hometown_state') or not player.get('high_school'):
                            player['needs_hometown_lookup'] = True
                            logger.debug(f"    Flagged for hometown lookup: {player['full_name']}")

                    # Validate player data
                    is_valid, errors = self.validator.validate_player(player)
                    if not is_valid:
                        logger.warning(f"    Invalid player data: {player.get('full_name', 'Unknown')}: {errors}")
                        continue

                    # Save to database
                    if self.db.upsert_player(player):
                        total_players += 1
                    else:
                        logger.warning(f"    Failed to save player: {player['full_name']}")

            except Exception as e:
                logger.error(f"Error processing roster for {team_name}: {e}")

        logger.info(f"Rosters sync complete: {total_players} players saved")
        logger.info(f"American players found: {american_players}")

    def sync_schedule(self):
        """
        Sync the season schedule.

        WHAT IT DOES:
        -------------
        1. Scrapes the full season schedule from EuroLeague
        2. For each game, extracts:
           - Date, time, timezone
           - Home and away teams
           - Venue information
           - Score (if game is completed)
        3. Saves all games to the database

        WHY WE NEED THE SCHEDULE:
        -------------------------
        The schedule lets us:
        - Know when games with American players are happening
        - Alert local news sites about upcoming games
        - Know which games need stats scraped after completion
        """
        logger.info("-" * 40)
        logger.info("SYNCING SCHEDULE")
        logger.info("-" * 40)

        try:
            # Scrape the full schedule
            # This can return 200+ games for a full season
            schedule = self.scraper.scrape_schedule()

            logger.info(f"Found {len(schedule)} games")

            # Track counts
            saved_count = 0

            for game in schedule:
                try:
                    # Validate game data
                    is_valid, errors = self.validator.validate_game(game)
                    if not is_valid:
                        logger.warning(f"Invalid game data: {game.get('game_id', 'Unknown')}: {errors}")
                        continue

                    # Save to database
                    if self.db.upsert_game(game):
                        saved_count += 1
                    else:
                        logger.warning(f"Failed to save game: {game.get('game_id', 'Unknown')}")

                except Exception as e:
                    logger.error(f"Error processing game: {e}")

            logger.info(f"Schedule sync complete: {saved_count} games saved")

        except Exception as e:
            logger.error(f"Schedule sync failed: {e}")
            raise

    def process_hometowns(self):
        """
        Look up hometowns for American players missing data.

        THE HOMETOWN LOOKUP PROCESS:
        ----------------------------
        For each American player without hometown data:

        1. Try Basketball Reference (PRIMARY source)
           - Most comprehensive for US players
           - 3+ second rate limit
           - Best for NBA/NCAA players

        2. If not found, try Wikipedia (SECONDARY source)
           - Good biographical data
           - API is fast and reliable

        3. If still not found, try Grokepedia (TERTIARY source)
           - Alternative source
           - May have obscure players

        4. If all fail, mark for manual review

        WHY MULTIPLE SOURCES?
        ---------------------
        - Not all players are on Basketball Reference
        - Wikipedia might have more recent info
        - Different sources have different coverage
        """
        logger.info("-" * 40)
        logger.info("PROCESSING HOMETOWN LOOKUPS")
        logger.info("-" * 40)

        # Get all American players who need hometown lookup
        players = self.db.get_players_needing_hometown_lookup()

        if not players:
            logger.info("No players need hometown lookup")
            return

        logger.info(f"Found {len(players)} players needing hometown lookup")

        # Track counts
        success_count = 0
        failed_count = 0

        for player in players:
            player_id = player['player_id']
            player_name = player['full_name']

            logger.info(f"Looking up: {player_name}")

            try:
                # Use the hometown service to look up the player
                # This tries all sources in priority order
                result = self.hometown_service.lookup_player_hometown(player_name)

                if result.get('lookup_successful'):
                    # Update the player record with found data
                    self.db.update_player_hometown(
                        player_id,
                        hometown_city=result.get('hometown_city'),
                        hometown_state=result.get('hometown_state'),
                        high_school=result.get('high_school'),
                        high_school_city=result.get('high_school_city'),
                        high_school_state=result.get('high_school_state'),
                        college=result.get('college'),
                        hometown_source=result.get('source')
                    )

                    # Process photo if found
                    if result.get('photo_url'):
                        self.photo_processor.process_player_photos(
                            player_id,
                            [result['photo_url']],
                            self.db
                        )

                    success_count += 1
                    logger.info(f"  Found: {result.get('hometown_city')}, {result.get('hometown_state')}")
                    logger.info(f"  High School: {result.get('high_school')}")

                else:
                    # Mark for manual review
                    self.db.mark_player_for_review(player_id)
                    failed_count += 1
                    logger.warning(f"  Could not find hometown for {player_name}")
                    logger.warning(f"  Player marked for manual review")

            except Exception as e:
                logger.error(f"Error looking up {player_name}: {e}")
                failed_count += 1

        logger.info(f"Hometown processing complete: {success_count} found, {failed_count} need review")

    def flag_american_games(self):
        """
        Update the schedule to flag which games have American players.

        WHY THIS MATTERS:
        -----------------
        Local news sites want to know when players from their area are playing.
        By flagging games, we can quickly answer questions like:
        - "Which games this week have Illinois players?"
        - "When is the next game with a player from Chicago?"

        WHAT IT DOES:
        -------------
        For each game in the schedule:
        1. Check if either team has American players
        2. Count how many American players are in the game
        3. Update the has_american_player and american_player_count fields

        This runs a single UPDATE query that sets flags based on player data.
        """
        logger.info("-" * 40)
        logger.info("FLAGGING GAMES WITH AMERICAN PLAYERS")
        logger.info("-" * 40)

        try:
            # This SQL updates ALL games in one query
            # It's much faster than updating games one by one
            query = """
                UPDATE schedule s
                SET
                    has_american_player = EXISTS (
                        SELECT 1 FROM players p
                        WHERE p.is_american = TRUE
                        AND p.is_active = TRUE
                        AND (p.team_id = s.home_team_id OR p.team_id = s.away_team_id)
                    ),
                    american_player_count = (
                        SELECT COUNT(*) FROM players p
                        WHERE p.is_american = TRUE
                        AND p.is_active = TRUE
                        AND (p.team_id = s.home_team_id OR p.team_id = s.away_team_id)
                    )
            """

            result = self.db.execute(query)

            if result is not None:
                logger.info(f"Game flagging complete - {result} games updated")
            else:
                logger.error("Game flagging failed")

        except Exception as e:
            logger.error(f"Error flagging games: {e}")

    def scrape_game_stats(self, days_back: int = 7):
        """
        Scrape statistics for recently completed games.

        WHAT IT DOES:
        -------------
        1. Find games that are completed but don't have stats yet
        2. For each game, scrape the box score
        3. Save individual player statistics
        4. Update game scores if needed

        WHY DAYS_BACK?
        --------------
        We don't want to re-scrape old games every time.
        days_back limits how far back we look for unscraped games.
        Default is 7 days, but you can change it:
            python main.py --stats --days-back 30

        PLAYER STATS COLLECTED:
        -----------------------
        - Minutes, Points, Rebounds, Assists, Steals, Blocks
        - Field Goals (made/attempted), 3-pointers, Free Throws
        - Plus/Minus, Efficiency Rating (PIR)
        """
        logger.info("-" * 40)
        logger.info(f"SCRAPING GAME STATS (last {days_back} days)")
        logger.info("-" * 40)

        # Get completed games that need stats
        games = self.db.get_games_needing_stats(days_back)

        if not games:
            logger.info("No games need stats scraped")
            return

        logger.info(f"Found {len(games)} games needing stats")

        success_count = 0
        error_count = 0

        for game in games:
            game_id = game['game_id']

            logger.info(f"Scraping stats for game: {game_id}")

            try:
                # Scrape the game stats
                stats = self.scraper.scrape_game_stats(game_id)

                if stats and stats.get('player_stats'):
                    # Update game scores
                    if stats.get('final_score'):
                        self.db.update_game_scores(
                            game_id,
                            stats['final_score'],
                            stats.get('quarter_scores', {})
                        )

                    # Insert player stats
                    for player_stat in stats.get('player_stats', []):
                        # Validate stat data
                        is_valid, errors = self.validator.validate_game_stat(player_stat)
                        if not is_valid:
                            logger.warning(f"Invalid stat data: {errors}")
                            continue

                        self.db.insert_game_stat(game_id, player_stat)

                    # Mark game as scraped
                    self.db.mark_game_stats_scraped(game_id)

                    success_count += 1
                    logger.info(f"  Saved {len(stats.get('player_stats', []))} player stats")

                else:
                    logger.warning(f"  No stats found for game {game_id}")
                    error_count += 1

            except Exception as e:
                logger.error(f"Error scraping game {game_id}: {e}")
                error_count += 1

        logger.info(f"Stats scraping complete: {success_count} games, {error_count} errors")

    def export_json(self):
        """
        Export all data to JSON files.

        WHY EXPORT TO JSON?
        -------------------
        - Easy to share with other systems
        - Human-readable format
        - Can be used by web applications
        - Serves as a backup of current data

        FILES CREATED:
        --------------
        output/json/
        ├── american_players_{date}.json    - All American players with hometown data
        ├── teams_{date}.json               - All teams
        ├── schedule_{date}.json            - Full schedule with American player info
        └── upcoming_games_{date}.json      - Games in the next 14 days

        JSON STRUCTURE:
        ---------------
        Each file has:
        - export_date: When the export was created
        - league: Which league (EuroLeague)
        - count: Number of items
        - data: Array of items
        """
        logger.info("-" * 40)
        logger.info("EXPORTING TO JSON")
        logger.info("-" * 40)

        # Get the output directory from config
        output_dir = OUTPUT_CONFIG.get('json_dir', 'output/json')

        # Create the directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Use today's date in filenames
        timestamp = datetime.now().strftime('%Y%m%d')

        # =====================================================================
        # EXPORT 1: AMERICAN PLAYERS
        # =====================================================================
        logger.info("Exporting American players...")

        try:
            american_players = self.db.get_american_players_with_hometown()

            # Build the export structure
            export_data = {
                'export_date': datetime.now().isoformat(),
                'league': 'EuroLeague',
                'player_count': len(american_players),
                'players': american_players
            }

            # Write to file
            filepath = os.path.join(output_dir, f'american_players_{timestamp}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                # indent=2 makes it human-readable
                # default=str handles datetime objects
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"  Saved {len(american_players)} American players to {filepath}")

        except Exception as e:
            logger.error(f"Error exporting American players: {e}")

        # =====================================================================
        # EXPORT 2: TEAMS
        # =====================================================================
        logger.info("Exporting teams...")

        try:
            teams = self.db.get_all_teams()

            export_data = {
                'export_date': datetime.now().isoformat(),
                'league': 'EuroLeague',
                'team_count': len(teams),
                'teams': teams
            }

            filepath = os.path.join(output_dir, f'teams_{timestamp}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"  Saved {len(teams)} teams to {filepath}")

        except Exception as e:
            logger.error(f"Error exporting teams: {e}")

        # =====================================================================
        # EXPORT 3: SCHEDULE WITH AMERICAN PLAYER INFO
        # =====================================================================
        logger.info("Exporting schedule...")

        try:
            schedule = self.db.get_schedule_with_americans()

            export_data = {
                'export_date': datetime.now().isoformat(),
                'league': 'EuroLeague',
                'game_count': len(schedule),
                'games': schedule
            }

            filepath = os.path.join(output_dir, f'schedule_{timestamp}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"  Saved {len(schedule)} games to {filepath}")

        except Exception as e:
            logger.error(f"Error exporting schedule: {e}")

        # =====================================================================
        # EXPORT 4: UPCOMING GAMES (Next 14 days)
        # =====================================================================
        logger.info("Exporting upcoming games...")

        try:
            upcoming = self.db.get_upcoming_american_games(days_ahead=14)

            export_data = {
                'export_date': datetime.now().isoformat(),
                'league': 'EuroLeague',
                'days_ahead': 14,
                'game_count': len(upcoming),
                'games': upcoming
            }

            filepath = os.path.join(output_dir, f'upcoming_games_{timestamp}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"  Saved {len(upcoming)} upcoming games to {filepath}")

        except Exception as e:
            logger.error(f"Error exporting upcoming games: {e}")

        logger.info(f"JSON export complete! Files saved to {output_dir}/")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_upcoming_games_by_state(self, state: str, days_ahead: int = 14) -> list:
        """
        Get upcoming games featuring players from a specific state.

        This is the KEY QUERY for local news sites!

        Example query:
        "Show me all games in the next 2 weeks with players from Illinois"

        Parameters:
        -----------
        state : str
            Full state name (e.g., 'Illinois', 'California')
        days_ahead : int
            How many days to look ahead (default 14)

        Returns:
        --------
        list
            List of games with player details

        Example output:
        ---------------
        [
            {
                'game_id': 'EUROLEAGUE_E2024_123',
                'game_date': '2024-01-20',
                'home_team': 'Real Madrid',
                'away_team': 'Barcelona',
                'player_name': 'John Smith',
                'hometown_city': 'Chicago',
                'hometown_state': 'Illinois',
                'high_school': 'Simeon Career Academy'
            },
            ...
        ]
        """
        return self.db.get_upcoming_games_by_state(state, days_ahead)


# =============================================================================
# COMMAND-LINE INTERFACE
# =============================================================================

def main():
    """
    Main entry point - parses command line arguments and runs operations.

    COMMAND LINE ARGUMENTS:
    -----------------------
    --full       : Run complete sync (teams, rosters, schedule, hometowns)
    --teams      : Sync teams only
    --rosters    : Sync rosters only
    --schedule   : Sync schedule only
    --stats      : Scrape game statistics
    --hometowns  : Process hometown lookups
    --export     : Export data to JSON
    --days-back  : Number of days back for stats (default: 7)

    EXAMPLES:
    ---------
    # Full sync
    python main.py --full

    # Teams and rosters only
    python main.py --teams --rosters

    # Stats for last 14 days
    python main.py --stats --days-back 14

    # Export to JSON
    python main.py --export
    """
    # =========================================================================
    # SET UP ARGUMENT PARSER
    # =========================================================================
    #
    # argparse creates a nice command-line interface with help text

    parser = argparse.ArgumentParser(
        description='EuroLeague Basketball Data Pipeline',
        # Show default values in help text
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Add arguments
    # action='store_true' means: if flag is present, set to True

    parser.add_argument(
        '--full',
        action='store_true',
        help='Run full sync (teams, rosters, schedule, hometowns)'
    )

    parser.add_argument(
        '--teams',
        action='store_true',
        help='Sync teams only'
    )

    parser.add_argument(
        '--rosters',
        action='store_true',
        help='Sync rosters only'
    )

    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Sync schedule only'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Scrape game statistics for recently completed games'
    )

    parser.add_argument(
        '--hometowns',
        action='store_true',
        help='Process hometown lookups for American players'
    )

    parser.add_argument(
        '--export',
        action='store_true',
        help='Export data to JSON files'
    )

    parser.add_argument(
        '--days-back',
        type=int,
        default=7,
        help='Number of days back for stats scraping'
    )

    # Parse the command line arguments
    args = parser.parse_args()

    # =========================================================================
    # CHECK IF ANY ARGUMENTS PROVIDED
    # =========================================================================

    # If no arguments provided, show help
    if not any([args.full, args.teams, args.rosters, args.schedule,
                args.stats, args.hometowns, args.export]):
        parser.print_help()
        print("\nNo operation specified. Use one of the options above.")
        sys.exit(1)

    # =========================================================================
    # INITIALIZE AND RUN PIPELINE
    # =========================================================================

    try:
        # Create the pipeline (this loads config and initializes everything)
        pipeline = EuroLeaguePipeline()

        # Run the requested operations
        if args.full:
            # Full sync runs everything in order
            pipeline.run_full_sync()
        else:
            # Run individual operations as requested
            if args.teams:
                pipeline.sync_teams()

            if args.rosters:
                pipeline.sync_rosters()

            if args.schedule:
                pipeline.sync_schedule()

            if args.hometowns:
                pipeline.process_hometowns()

            if args.stats:
                pipeline.scrape_game_stats(args.days_back)

            if args.export:
                pipeline.export_json()

        logger.info("Pipeline execution completed successfully!")

    except KeyboardInterrupt:
        # User pressed Ctrl+C
        logger.info("Operation cancelled by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        sys.exit(1)


# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================
#
# This is Python's standard way of making a script runnable.
# __name__ is '__main__' only when you run the script directly:
#     python main.py
#
# It's NOT '__main__' when you import it as a module:
#     from main import EuroLeaguePipeline

if __name__ == '__main__':
    main()
