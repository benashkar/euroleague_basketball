"""
Validates scraped data before database insertion.

Checks for:
- Required fields
- Data format validation
- Duplicate detection
- Data consistency
"""

from typing import Dict, List, Optional, Tuple
import re
from datetime import date, datetime
import logging
from config.settings import US_STATES, AMERICAN_NATIONALITIES

logger = logging.getLogger(__name__)


class DataValidator:
    """Validator for scraped basketball data."""

    def __init__(self):
        """Initialize data validator."""
        self.logger = logging.getLogger(__name__)

    # ========================================
    # TEAM VALIDATION
    # ========================================

    def validate_team(self, team: Dict) -> Tuple[bool, List[str]]:
        """
        Validate team data.

        Args:
            team: Team data dict

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        # Required fields
        if not team.get('team_id'):
            errors.append("Missing team_id")
        if not team.get('team_name'):
            errors.append("Missing team_name")
        if not team.get('league_id'):
            errors.append("Missing league_id")

        # Format validation
        if team.get('team_id') and not self._is_valid_id(team['team_id']):
            errors.append(f"Invalid team_id format: {team['team_id']}")

        return (len(errors) == 0, errors)

    # ========================================
    # PLAYER VALIDATION
    # ========================================

    def validate_player(self, player: Dict) -> Tuple[bool, List[str]]:
        """
        Validate player data.

        Args:
            player: Player data dict

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        # Required fields
        if not player.get('player_id'):
            errors.append("Missing player_id")
        if not player.get('full_name'):
            errors.append("Missing full_name")

        # Format validation
        if player.get('player_id') and not self._is_valid_id(player['player_id']):
            errors.append(f"Invalid player_id format: {player['player_id']}")

        # Birth date validation
        if player.get('birth_date'):
            if not self._is_valid_date(player['birth_date']):
                errors.append(f"Invalid birth_date: {player['birth_date']}")

        # Height validation
        if player.get('height_cm'):
            if not 150 <= player['height_cm'] <= 250:
                errors.append(f"Suspicious height_cm: {player['height_cm']}")

        # Weight validation
        if player.get('weight_kg'):
            if not 50 <= player['weight_kg'] <= 200:
                errors.append(f"Suspicious weight_kg: {player['weight_kg']}")

        # Jersey number validation
        if player.get('jersey_number'):
            jersey = player['jersey_number']
            if not (jersey.isdigit() and 0 <= int(jersey) <= 99):
                if jersey not in ['00']:
                    errors.append(f"Invalid jersey_number: {jersey}")

        # American player validation
        if player.get('is_american'):
            if player.get('hometown_state'):
                if player['hometown_state'] not in US_STATES:
                    errors.append(f"Invalid hometown_state for American: {player['hometown_state']}")

        return (len(errors) == 0, errors)

    # ========================================
    # GAME VALIDATION
    # ========================================

    def validate_game(self, game: Dict) -> Tuple[bool, List[str]]:
        """
        Validate game/schedule data.

        Args:
            game: Game data dict

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        # Required fields
        if not game.get('game_id'):
            errors.append("Missing game_id")
        if not game.get('game_date'):
            errors.append("Missing game_date")

        # Date validation
        if game.get('game_date'):
            if not self._is_valid_date(game['game_date']):
                errors.append(f"Invalid game_date: {game['game_date']}")

        # Score validation (if completed)
        if game.get('status') == 'completed':
            if game.get('home_score') is None:
                errors.append("Completed game missing home_score")
            if game.get('away_score') is None:
                errors.append("Completed game missing away_score")

            # Valid basketball scores
            if game.get('home_score') is not None:
                if not 0 <= game['home_score'] <= 200:
                    errors.append(f"Suspicious home_score: {game['home_score']}")
            if game.get('away_score') is not None:
                if not 0 <= game['away_score'] <= 200:
                    errors.append(f"Suspicious away_score: {game['away_score']}")

        return (len(errors) == 0, errors)

    # ========================================
    # GAME STATS VALIDATION
    # ========================================

    def validate_game_stat(self, stat: Dict) -> Tuple[bool, List[str]]:
        """
        Validate player game statistics.

        Args:
            stat: Game stat dict

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        # Required fields
        if not stat.get('player_id'):
            errors.append("Missing player_id")
        if not stat.get('game_id'):
            errors.append("Missing game_id")

        # Skip validation if DNP
        if stat.get('did_not_play'):
            return (len(errors) == 0, errors)

        # Stats range validation
        if stat.get('points') is not None:
            if not 0 <= stat['points'] <= 80:
                errors.append(f"Suspicious points: {stat['points']}")

        if stat.get('rebounds_total') is not None:
            if not 0 <= stat['rebounds_total'] <= 35:
                errors.append(f"Suspicious rebounds: {stat['rebounds_total']}")

        if stat.get('assists') is not None:
            if not 0 <= stat['assists'] <= 25:
                errors.append(f"Suspicious assists: {stat['assists']}")

        # FG attempted must be >= made
        if stat.get('fg_made') is not None and stat.get('fg_attempted') is not None:
            if stat['fg_made'] > stat['fg_attempted']:
                errors.append(f"FG made ({stat['fg_made']}) > attempted ({stat['fg_attempted']})")

        # 3PT attempted must be >= made
        if stat.get('three_pt_made') is not None and stat.get('three_pt_attempted') is not None:
            if stat['three_pt_made'] > stat['three_pt_attempted']:
                errors.append(f"3PT made > attempted")

        # FT attempted must be >= made
        if stat.get('ft_made') is not None and stat.get('ft_attempted') is not None:
            if stat['ft_made'] > stat['ft_attempted']:
                errors.append(f"FT made > attempted")

        return (len(errors) == 0, errors)

    # ========================================
    # HOMETOWN VALIDATION
    # ========================================

    def validate_hometown(self, data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate hometown lookup data.

        Args:
            data: Hometown data dict

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        # State validation
        if data.get('hometown_state'):
            if data['hometown_state'] not in US_STATES:
                errors.append(f"Invalid hometown_state: {data['hometown_state']}")

        if data.get('high_school_state'):
            if data['high_school_state'] not in US_STATES:
                errors.append(f"Invalid high_school_state: {data['high_school_state']}")

        return (len(errors) == 0, errors)

    # ========================================
    # HELPER METHODS
    # ========================================

    def _is_valid_id(self, id_value: str) -> bool:
        """Check if ID has valid format."""
        if not id_value:
            return False
        # IDs should be alphanumeric with underscores
        return bool(re.match(r'^[A-Za-z0-9_]+$', id_value))

    def _is_valid_date(self, date_value) -> bool:
        """Check if date is valid."""
        if isinstance(date_value, (date, datetime)):
            return True
        if isinstance(date_value, str):
            try:
                # Try common formats
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y']:
                    try:
                        datetime.strptime(date_value[:10], fmt)
                        return True
                    except:
                        continue
            except:
                pass
        return False

    def is_american_nationality(self, nationality: str) -> bool:
        """
        Check if nationality indicates American.

        Args:
            nationality: Nationality string

        Returns:
            True if American
        """
        if not nationality:
            return False

        nationality_lower = nationality.lower().strip()
        return any(
            ind.lower() in nationality_lower
            for ind in AMERICAN_NATIONALITIES
        )

    def clean_player_data(self, player: Dict) -> Dict:
        """
        Clean and normalize player data.

        Args:
            player: Raw player data

        Returns:
            Cleaned player data
        """
        cleaned = player.copy()

        # Trim string fields
        string_fields = [
            'full_name', 'first_name', 'last_name',
            'position', 'hometown_city', 'hometown_state',
            'high_school', 'college'
        ]
        for field in string_fields:
            if cleaned.get(field):
                cleaned[field] = cleaned[field].strip()

        # Normalize position
        if cleaned.get('position'):
            pos = cleaned['position'].upper()
            position_map = {
                'PG': 'PG', 'POINT GUARD': 'PG', 'POINT': 'PG',
                'SG': 'SG', 'SHOOTING GUARD': 'SG', 'SHOOTING': 'SG',
                'SF': 'SF', 'SMALL FORWARD': 'SF',
                'PF': 'PF', 'POWER FORWARD': 'PF',
                'C': 'C', 'CENTER': 'C',
                'G': 'G', 'GUARD': 'G',
                'F': 'F', 'FORWARD': 'F'
            }
            cleaned['position'] = position_map.get(pos, pos)

        # Set is_american based on nationality
        if cleaned.get('birth_country'):
            cleaned['is_american'] = self.is_american_nationality(cleaned['birth_country'])

        return cleaned

    def validate_and_clean_batch(self, items: List[Dict], item_type: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate and clean a batch of items.

        Args:
            items: List of data dicts
            item_type: Type of data ('team', 'player', 'game', 'game_stat')

        Returns:
            Tuple of (valid_items, invalid_items_with_errors)
        """
        validators = {
            'team': self.validate_team,
            'player': self.validate_player,
            'game': self.validate_game,
            'game_stat': self.validate_game_stat
        }

        if item_type not in validators:
            raise ValueError(f"Unknown item type: {item_type}")

        validator = validators[item_type]
        valid_items = []
        invalid_items = []

        for item in items:
            is_valid, errors = validator(item)
            if is_valid:
                valid_items.append(item)
            else:
                invalid_items.append({
                    'item': item,
                    'errors': errors
                })
                self.logger.warning(f"Invalid {item_type}: {errors}")

        return (valid_items, invalid_items)
