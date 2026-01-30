"""
MySQL database connector with methods for CRUD operations.
"""
import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Optional, Any
from datetime import datetime, date
import logging
import json

logger = logging.getLogger(__name__)


class MySQLConnector:
    """MySQL database connector for EuroLeague tracker."""

    def __init__(self, config: dict):
        """
        Initialize MySQL connector.

        Args:
            config: Dict with host, port, user, password, database
        """
        self.config = config
        self.connection = None

    def connect(self):
        """Establish database connection."""
        try:
            self.connection = mysql.connector.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            logger.info("Connected to MySQL database")
            return True
        except Error as e:
            logger.error(f"Error connecting to MySQL: {e}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Disconnected from MySQL database")

    def ensure_connected(self):
        """Ensure connection is active, reconnect if needed."""
        if not self.connection or not self.connection.is_connected():
            self.connect()

    def execute(self, query: str, params: tuple = None) -> Optional[int]:
        """
        Execute a query (INSERT, UPDATE, DELETE).

        Returns:
            Number of affected rows or None on error
        """
        self.ensure_connected()
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            affected = cursor.rowcount
            cursor.close()
            return affected
        except Error as e:
            logger.error(f"Query execution error: {e}")
            logger.error(f"Query: {query}")
            return None

    def execute_many(self, query: str, params_list: List[tuple]) -> Optional[int]:
        """Execute a query with multiple parameter sets."""
        self.ensure_connected()
        try:
            cursor = self.connection.cursor()
            cursor.executemany(query, params_list)
            self.connection.commit()
            affected = cursor.rowcount
            cursor.close()
            return affected
        except Error as e:
            logger.error(f"Batch execution error: {e}")
            return None

    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Fetch single row as dictionary."""
        self.ensure_connected()
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params)
            result = cursor.fetchone()
            cursor.close()
            return result
        except Error as e:
            logger.error(f"Fetch one error: {e}")
            return None

    def fetch_all(self, query: str, params: tuple = None) -> List[Dict]:
        """Fetch all rows as list of dictionaries."""
        self.ensure_connected()
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            logger.error(f"Fetch all error: {e}")
            return []

    # ========================================
    # TEAM OPERATIONS
    # ========================================

    def upsert_team(self, team: Dict) -> bool:
        """Insert or update a team."""
        query = """
            INSERT INTO teams (
                team_id, league_id, team_name, team_name_normalized,
                team_code, team_slug, city, country, arena, arena_capacity,
                logo_url, website_url, source_team_id, is_active
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                team_name = VALUES(team_name),
                team_name_normalized = VALUES(team_name_normalized),
                team_code = VALUES(team_code),
                team_slug = VALUES(team_slug),
                city = VALUES(city),
                country = VALUES(country),
                arena = VALUES(arena),
                arena_capacity = VALUES(arena_capacity),
                logo_url = VALUES(logo_url),
                website_url = VALUES(website_url),
                is_active = VALUES(is_active),
                updated_at = CURRENT_TIMESTAMP
        """
        params = (
            team.get('team_id'),
            team.get('league_id', 'EUROLEAGUE'),
            team.get('team_name'),
            team.get('team_name_normalized'),
            team.get('team_code'),
            team.get('team_slug'),
            team.get('city'),
            team.get('country'),
            team.get('arena'),
            team.get('arena_capacity'),
            team.get('logo_url'),
            team.get('website_url'),
            team.get('source_team_id'),
            team.get('is_active', True)
        )
        result = self.execute(query, params)
        return result is not None

    def get_all_teams(self, league_id: str = 'EUROLEAGUE') -> List[Dict]:
        """Get all active teams for a league."""
        query = """
            SELECT * FROM teams
            WHERE league_id = %s AND is_active = TRUE
            ORDER BY team_name
        """
        return self.fetch_all(query, (league_id,))

    def get_team_by_id(self, team_id: str) -> Optional[Dict]:
        """Get team by ID."""
        query = "SELECT * FROM teams WHERE team_id = %s"
        return self.fetch_one(query, (team_id,))

    # ========================================
    # PLAYER OPERATIONS
    # ========================================

    def upsert_player(self, player: Dict) -> bool:
        """Insert or update a player."""
        query = """
            INSERT INTO players (
                player_id, team_id, league_id,
                first_name, last_name, full_name, full_name_normalized,
                jersey_number, position,
                height_cm, height_display, weight_kg, weight_display,
                birth_date, birth_year, birth_country, birth_city,
                is_american,
                hometown_city, hometown_state, hometown_source, hometown_lookup_date,
                high_school, high_school_city, high_school_state,
                college, college_years,
                photo_url, photo_url_16x9, photo_url_square, photo_source,
                euroleague_profile_url, basketball_ref_url, wikipedia_url,
                source_player_id, needs_hometown_lookup, needs_manual_review, is_active
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                team_id = VALUES(team_id),
                first_name = VALUES(first_name),
                last_name = VALUES(last_name),
                full_name = VALUES(full_name),
                full_name_normalized = VALUES(full_name_normalized),
                jersey_number = VALUES(jersey_number),
                position = VALUES(position),
                height_cm = VALUES(height_cm),
                height_display = VALUES(height_display),
                weight_kg = VALUES(weight_kg),
                weight_display = VALUES(weight_display),
                birth_date = VALUES(birth_date),
                birth_year = VALUES(birth_year),
                birth_country = VALUES(birth_country),
                birth_city = VALUES(birth_city),
                is_american = VALUES(is_american),
                photo_url = COALESCE(VALUES(photo_url), photo_url),
                photo_url_16x9 = COALESCE(VALUES(photo_url_16x9), photo_url_16x9),
                photo_url_square = COALESCE(VALUES(photo_url_square), photo_url_square),
                photo_source = COALESCE(VALUES(photo_source), photo_source),
                euroleague_profile_url = VALUES(euroleague_profile_url),
                source_player_id = VALUES(source_player_id),
                needs_hometown_lookup = VALUES(needs_hometown_lookup),
                is_active = VALUES(is_active),
                updated_at = CURRENT_TIMESTAMP
        """
        params = (
            player.get('player_id'),
            player.get('team_id'),
            player.get('league_id', 'EUROLEAGUE'),
            player.get('first_name'),
            player.get('last_name'),
            player.get('full_name'),
            player.get('full_name_normalized'),
            player.get('jersey_number'),
            player.get('position'),
            player.get('height_cm'),
            player.get('height_display'),
            player.get('weight_kg'),
            player.get('weight_display'),
            player.get('birth_date'),
            player.get('birth_year'),
            player.get('birth_country'),
            player.get('birth_city'),
            player.get('is_american', False),
            player.get('hometown_city'),
            player.get('hometown_state'),
            player.get('hometown_source'),
            player.get('hometown_lookup_date'),
            player.get('high_school'),
            player.get('high_school_city'),
            player.get('high_school_state'),
            player.get('college'),
            player.get('college_years'),
            player.get('photo_url'),
            player.get('photo_url_16x9'),
            player.get('photo_url_square'),
            player.get('photo_source'),
            player.get('euroleague_profile_url'),
            player.get('basketball_ref_url'),
            player.get('wikipedia_url'),
            player.get('source_player_id'),
            player.get('needs_hometown_lookup', False),
            player.get('needs_manual_review', False),
            player.get('is_active', True)
        )
        result = self.execute(query, params)
        return result is not None

    def get_players_needing_hometown_lookup(self) -> List[Dict]:
        """Get American players missing hometown data."""
        query = """
            SELECT player_id, full_name, full_name_normalized, team_id
            FROM players
            WHERE is_american = TRUE
              AND is_active = TRUE
              AND needs_hometown_lookup = TRUE
              AND (hometown_state IS NULL OR high_school IS NULL)
            ORDER BY full_name
        """
        return self.fetch_all(query)

    def update_player_hometown(self, player_id: str, **kwargs) -> bool:
        """Update player hometown information."""
        query = """
            UPDATE players SET
                hometown_city = %s,
                hometown_state = %s,
                high_school = %s,
                high_school_city = %s,
                high_school_state = %s,
                college = %s,
                hometown_source = %s,
                hometown_lookup_date = %s,
                needs_hometown_lookup = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE player_id = %s
        """
        params = (
            kwargs.get('hometown_city'),
            kwargs.get('hometown_state'),
            kwargs.get('high_school'),
            kwargs.get('high_school_city'),
            kwargs.get('high_school_state'),
            kwargs.get('college'),
            kwargs.get('hometown_source'),
            date.today(),
            player_id
        )
        result = self.execute(query, params)
        return result is not None

    def mark_player_for_review(self, player_id: str) -> bool:
        """Mark player for manual review."""
        query = """
            UPDATE players SET
                needs_manual_review = TRUE,
                needs_hometown_lookup = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE player_id = %s
        """
        result = self.execute(query, (player_id,))
        return result is not None

    def get_american_players_with_hometown(self) -> List[Dict]:
        """Get all American players with their hometown data."""
        query = """
            SELECT
                p.player_id, p.full_name, p.position, p.jersey_number,
                p.hometown_city, p.hometown_state, p.high_school,
                p.high_school_city, p.high_school_state, p.college,
                p.photo_url, p.photo_url_16x9, p.photo_url_square,
                p.euroleague_profile_url, p.basketball_ref_url,
                p.hometown_source, p.needs_manual_review,
                t.team_id, t.team_name
            FROM players p
            JOIN teams t ON p.team_id = t.team_id
            WHERE p.is_american = TRUE AND p.is_active = TRUE
            ORDER BY p.hometown_state, p.hometown_city, p.last_name
        """
        return self.fetch_all(query)

    # ========================================
    # SCHEDULE OPERATIONS
    # ========================================

    def upsert_game(self, game: Dict) -> bool:
        """Insert or update a game in the schedule."""
        query = """
            INSERT INTO schedule (
                game_id, league_id, season, season_code,
                round_number, round_name, phase,
                home_team_id, away_team_id,
                game_date, game_time, game_datetime, timezone, game_date_utc,
                venue, city, country,
                status,
                home_score, away_score,
                source_game_id, game_url
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                round_number = VALUES(round_number),
                round_name = VALUES(round_name),
                phase = VALUES(phase),
                game_date = VALUES(game_date),
                game_time = VALUES(game_time),
                game_datetime = VALUES(game_datetime),
                venue = VALUES(venue),
                status = VALUES(status),
                home_score = VALUES(home_score),
                away_score = VALUES(away_score),
                game_url = VALUES(game_url),
                updated_at = CURRENT_TIMESTAMP
        """
        params = (
            game.get('game_id'),
            game.get('league_id', 'EUROLEAGUE'),
            game.get('season'),
            game.get('season_code'),
            game.get('round_number'),
            game.get('round_name'),
            game.get('phase'),
            game.get('home_team_id'),
            game.get('away_team_id'),
            game.get('game_date'),
            game.get('game_time'),
            game.get('game_datetime'),
            game.get('timezone', 'Europe/Madrid'),
            game.get('game_date_utc'),
            game.get('venue'),
            game.get('city'),
            game.get('country'),
            game.get('status', 'scheduled'),
            game.get('home_score'),
            game.get('away_score'),
            game.get('source_game_id'),
            game.get('game_url')
        )
        result = self.execute(query, params)
        return result is not None

    def get_games_needing_stats(self, days_back: int = 7) -> List[Dict]:
        """Get completed games that need stats scraped."""
        query = """
            SELECT game_id, game_date, home_team_id, away_team_id, source_game_id
            FROM schedule
            WHERE status = 'completed'
              AND stats_scraped = FALSE
              AND game_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY game_date DESC
        """
        return self.fetch_all(query, (days_back,))

    def update_game_scores(self, game_id: str, final_score: Dict, quarter_scores: Dict = None) -> bool:
        """Update game scores."""
        query = """
            UPDATE schedule SET
                home_score = %s,
                away_score = %s,
                home_score_q1 = %s,
                home_score_q2 = %s,
                home_score_q3 = %s,
                home_score_q4 = %s,
                away_score_q1 = %s,
                away_score_q2 = %s,
                away_score_q3 = %s,
                away_score_q4 = %s,
                status = 'completed',
                updated_at = CURRENT_TIMESTAMP
            WHERE game_id = %s
        """
        home_q = quarter_scores.get('home', [None]*4) if quarter_scores else [None]*4
        away_q = quarter_scores.get('away', [None]*4) if quarter_scores else [None]*4

        params = (
            final_score.get('home'),
            final_score.get('away'),
            home_q[0] if len(home_q) > 0 else None,
            home_q[1] if len(home_q) > 1 else None,
            home_q[2] if len(home_q) > 2 else None,
            home_q[3] if len(home_q) > 3 else None,
            away_q[0] if len(away_q) > 0 else None,
            away_q[1] if len(away_q) > 1 else None,
            away_q[2] if len(away_q) > 2 else None,
            away_q[3] if len(away_q) > 3 else None,
            game_id
        )
        result = self.execute(query, params)
        return result is not None

    def mark_game_stats_scraped(self, game_id: str) -> bool:
        """Mark game as having stats scraped."""
        query = """
            UPDATE schedule SET
                stats_scraped = TRUE,
                stats_scraped_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE game_id = %s
        """
        result = self.execute(query, (game_id,))
        return result is not None

    def get_schedule_with_americans(self) -> List[Dict]:
        """Get full schedule with American player info."""
        query = """
            SELECT
                s.*,
                ht.team_name AS home_team_name,
                at.team_name AS away_team_name
            FROM schedule s
            JOIN teams ht ON s.home_team_id = ht.team_id
            JOIN teams at ON s.away_team_id = at.team_id
            WHERE s.has_american_player = TRUE
            ORDER BY s.game_date, s.game_time
        """
        return self.fetch_all(query)

    def get_upcoming_american_games(self, days_ahead: int = 14) -> List[Dict]:
        """Get upcoming games with American players."""
        query = """
            SELECT
                s.game_id, s.game_date, s.game_time, s.game_datetime,
                s.venue, s.status, s.american_player_count,
                ht.team_id AS home_team_id, ht.team_name AS home_team_name,
                at.team_id AS away_team_id, at.team_name AS away_team_name
            FROM schedule s
            JOIN teams ht ON s.home_team_id = ht.team_id
            JOIN teams at ON s.away_team_id = at.team_id
            WHERE s.has_american_player = TRUE
              AND s.game_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL %s DAY)
              AND s.status IN ('scheduled', 'in_progress')
            ORDER BY s.game_date, s.game_time
        """
        return self.fetch_all(query, (days_ahead,))

    def get_upcoming_games_by_state(self, state: str, days_ahead: int = 14) -> List[Dict]:
        """Get upcoming games featuring players from a specific state."""
        query = """
            SELECT DISTINCT
                s.game_id, s.game_date, s.game_time, s.venue,
                ht.team_name AS home_team, at.team_name AS away_team,
                p.full_name AS player_name, p.position,
                p.hometown_city, p.hometown_state, p.high_school,
                p.photo_url_16x9,
                t.team_name AS player_team,
                CASE WHEN p.team_id = s.home_team_id THEN 'home' ELSE 'away' END AS home_or_away
            FROM schedule s
            JOIN teams ht ON s.home_team_id = ht.team_id
            JOIN teams at ON s.away_team_id = at.team_id
            JOIN players p ON (p.team_id = s.home_team_id OR p.team_id = s.away_team_id)
            JOIN teams t ON p.team_id = t.team_id
            WHERE p.is_american = TRUE
              AND p.hometown_state = %s
              AND p.is_active = TRUE
              AND s.game_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL %s DAY)
              AND s.status = 'scheduled'
            ORDER BY s.game_date, s.game_time
        """
        return self.fetch_all(query, (state, days_ahead))

    # ========================================
    # GAME STATS OPERATIONS
    # ========================================

    def insert_game_stat(self, game_id: str, stat: Dict) -> bool:
        """Insert player game statistics."""
        query = """
            INSERT INTO game_stats (
                game_id, player_id, team_id,
                is_home_team, is_starter, did_not_play, dnp_reason,
                minutes_played, minutes_decimal,
                points, rebounds_total, rebounds_offensive, rebounds_defensive,
                assists, steals, blocks, blocks_against,
                turnovers, fouls_personal, fouls_drawn,
                fg_made, fg_attempted, fg_percentage,
                two_pt_made, two_pt_attempted, two_pt_percentage,
                three_pt_made, three_pt_attempted, three_pt_percentage,
                ft_made, ft_attempted, ft_percentage,
                plus_minus, efficiency_rating
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                minutes_played = VALUES(minutes_played),
                minutes_decimal = VALUES(minutes_decimal),
                points = VALUES(points),
                rebounds_total = VALUES(rebounds_total),
                assists = VALUES(assists),
                updated_at = CURRENT_TIMESTAMP
        """
        params = (
            game_id,
            stat.get('player_id'),
            stat.get('team_id'),
            stat.get('is_home_team'),
            stat.get('is_starter'),
            stat.get('did_not_play', False),
            stat.get('dnp_reason'),
            stat.get('minutes_played'),
            stat.get('minutes_decimal'),
            stat.get('points', 0),
            stat.get('rebounds_total', 0),
            stat.get('rebounds_offensive', 0),
            stat.get('rebounds_defensive', 0),
            stat.get('assists', 0),
            stat.get('steals', 0),
            stat.get('blocks', 0),
            stat.get('blocks_against', 0),
            stat.get('turnovers', 0),
            stat.get('fouls_personal', 0),
            stat.get('fouls_drawn', 0),
            stat.get('fg_made', 0),
            stat.get('fg_attempted', 0),
            stat.get('fg_percentage'),
            stat.get('two_pt_made', 0),
            stat.get('two_pt_attempted', 0),
            stat.get('two_pt_percentage'),
            stat.get('three_pt_made', 0),
            stat.get('three_pt_attempted', 0),
            stat.get('three_pt_percentage'),
            stat.get('ft_made', 0),
            stat.get('ft_attempted', 0),
            stat.get('ft_percentage'),
            stat.get('plus_minus'),
            stat.get('efficiency_rating')
        )
        result = self.execute(query, params)
        return result is not None

    # ========================================
    # CACHE OPERATIONS
    # ========================================

    def get_hometown_cache(self, normalized_name: str) -> Optional[Dict]:
        """Get cached hometown lookup result."""
        query = """
            SELECT *
            FROM hometown_cache
            WHERE player_name_search = %s
              AND lookup_successful = TRUE
            ORDER BY lookup_date DESC
            LIMIT 1
        """
        return self.fetch_one(query, (normalized_name,))

    def cache_hometown_lookup(self, normalized_name: str, source: str, result: Dict) -> bool:
        """Cache a hometown lookup result."""
        query = """
            INSERT INTO hometown_cache (
                player_name_search, lookup_source, lookup_successful,
                hometown_city, hometown_state,
                high_school, high_school_city, high_school_state,
                college, source_url, profile_url, photo_url
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        params = (
            normalized_name,
            source,
            result.get('lookup_successful', False),
            result.get('hometown_city'),
            result.get('hometown_state'),
            result.get('high_school'),
            result.get('high_school_city'),
            result.get('high_school_state'),
            result.get('college'),
            result.get('source_url'),
            result.get('profile_url'),
            result.get('photo_url')
        )
        return self.execute(query, params) is not None

    # ========================================
    # SCRAPE LOG OPERATIONS
    # ========================================

    def start_scrape_log(self, scrape_type: str) -> Optional[int]:
        """Start a scrape log entry."""
        query = """
            INSERT INTO scrape_log (scrape_type, status)
            VALUES (%s, 'running')
        """
        self.ensure_connected()
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (scrape_type,))
            self.connection.commit()
            log_id = cursor.lastrowid
            cursor.close()
            return log_id
        except Error as e:
            logger.error(f"Error creating scrape log: {e}")
            return None

    def complete_scrape_log(self, log_id: int, items_processed: int,
                           items_success: int, items_failed: int,
                           error_message: str = None) -> bool:
        """Complete a scrape log entry."""
        query = """
            UPDATE scrape_log SET
                completed_at = CURRENT_TIMESTAMP,
                status = %s,
                items_processed = %s,
                items_success = %s,
                items_failed = %s,
                error_message = %s
            WHERE log_id = %s
        """
        status = 'failed' if error_message else 'completed'
        params = (status, items_processed, items_success, items_failed, error_message, log_id)
        return self.execute(query, params) is not None
