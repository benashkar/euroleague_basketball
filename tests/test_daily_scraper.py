"""
=============================================================================
UNIT TESTS FOR DAILY SCRAPER
=============================================================================

HOW TO RUN THESE TESTS:
    From the project root directory:
        python -m pytest tests/                    # Run all tests
        python -m pytest tests/ -v                 # Verbose output
        python -m pytest tests/ -v --tb=short     # Short traceback on errors

    If pytest isn't installed:
        pip install pytest

WHAT THESE TESTS DO:
    Test individual functions to make sure they work correctly.
    This helps catch bugs early when you make changes to the code.

WHY WRITE TESTS:
    1. Catch bugs before they reach production
    2. Make it safe to refactor code
    3. Document how functions should behave
    4. Save time on manual testing

TEST NAMING CONVENTION:
    test_<function_name>_<scenario>
    Example: test_is_american_with_usa_code
"""

import pytest
import sys
import os

# Add parent directory to path so we can import our modules
# This lets us run tests from the tests/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daily_scraper import is_american, process_games, extract_american_performances


# =============================================================================
# TESTS FOR is_american()
# =============================================================================

class TestIsAmerican:
    """Tests for the is_american() function."""

    def test_is_american_with_usa_code(self):
        """
        Test that 'USA' country code is recognized as American.

        This is the standard case - most American players have
        country code 'USA'.
        """
        country_data = {'code': 'USA', 'name': 'United States'}
        assert is_american(country_data) == True

    def test_is_american_with_us_code(self):
        """
        Test that 'US' country code is also recognized.

        Some records in the API use 'US' instead of 'USA'.
        """
        country_data = {'code': 'US', 'name': 'United States'}
        assert is_american(country_data) == True

    def test_is_american_with_lowercase(self):
        """
        Test that lowercase country codes work.

        The function should handle case-insensitively.
        """
        country_data = {'code': 'usa', 'name': 'United States'}
        assert is_american(country_data) == True

    def test_is_american_with_non_american(self):
        """
        Test that non-American countries return False.
        """
        country_data = {'code': 'ESP', 'name': 'Spain'}
        assert is_american(country_data) == False

    def test_is_american_with_none(self):
        """
        Test that None input returns False without crashing.

        Some players in the API don't have country data.
        """
        assert is_american(None) == False

    def test_is_american_with_empty_dict(self):
        """
        Test that empty dict returns False.
        """
        assert is_american({}) == False

    def test_is_american_with_missing_code(self):
        """
        Test that dict without 'code' key returns False.
        """
        country_data = {'name': 'United States'}
        assert is_american(country_data) == False


# =============================================================================
# TESTS FOR process_games()
# =============================================================================

class TestProcessGames:
    """Tests for the process_games() function."""

    @pytest.fixture
    def sample_games(self):
        """
        Create sample game data for testing.

        A pytest fixture is a function that provides test data.
        It runs before each test that uses it.
        """
        return [
            {'gameCode': 1, 'date': '2025-01-01T19:00:00', 'played': True},
            {'gameCode': 2, 'date': '2025-01-28T20:00:00', 'played': True},
            {'gameCode': 3, 'date': '2025-01-29T19:00:00', 'played': True},
            {'gameCode': 4, 'date': '2025-02-15T20:00:00', 'played': False},  # Upcoming
        ]

    def test_process_games_all_mode(self, sample_games):
        """
        Test that 'all' mode returns all games.
        """
        result = process_games(sample_games, mode='all')
        assert len(result) == 4  # Should return all games

    def test_process_games_recent_mode(self, sample_games):
        """
        Test that 'recent' mode filters to recent played games.

        Note: This test might need adjustment based on current date.
        """
        result = process_games(sample_games, mode='recent')
        # Should return played games from last 7 days
        # All returned games should be played
        for game in result:
            assert game.get('played') == True

    def test_process_games_empty_list(self):
        """
        Test that empty input returns empty output.
        """
        result = process_games([], mode='all')
        assert result == []


# =============================================================================
# TESTS FOR extract_american_performances()
# =============================================================================

class TestExtractAmericanPerformances:
    """Tests for the extract_american_performances() function."""

    @pytest.fixture
    def sample_game(self):
        """Sample game data."""
        return {
            'gameCode': 1,
            'date': '2025-01-15T19:00:00',
            'round': 20,
            'local': {
                'club': {'code': 'MAD', 'name': 'Real Madrid'},
                'score': 85
            },
            'road': {
                'club': {'code': 'BAR', 'name': 'FC Barcelona'},
                'score': 80
            }
        }

    @pytest.fixture
    def sample_stats_with_american(self):
        """Sample box score with one American player."""
        return {
            'local': {
                'players': [
                    {
                        'player': {
                            'dorsal': '7',
                            'positionName': 'Guard',
                            'person': {
                                'code': 'PJTU',
                                'name': 'Test, American',
                                'country': {'code': 'USA', 'name': 'United States'},
                                'birthCountry': {'code': 'USA', 'name': 'United States'}
                            }
                        },
                        'stats': {
                            'points': 20,
                            'totalRebounds': 5,
                            'assistances': 8,  # Note: API uses 'assistances'
                            'timePlayed': 1800,  # 30 minutes in seconds
                            'valuation': 25  # PIR
                        }
                    }
                ]
            },
            'road': {
                'players': []
            }
        }

    def test_extract_american_performances_finds_american(
        self, sample_game, sample_stats_with_american
    ):
        """
        Test that American players are correctly identified and extracted.
        """
        result = extract_american_performances(sample_game, sample_stats_with_american)

        # Should find 1 American player
        assert len(result) == 1

        # Check the extracted data
        perf = result[0]
        assert perf['player_name'] == 'Test, American'
        assert perf['points'] == 20
        assert perf['rebounds'] == 5
        assert perf['assists'] == 8
        assert perf['minutes'] == 30.0  # Should be converted from seconds

    def test_extract_american_performances_no_americans(self, sample_game):
        """
        Test that no results are returned when no Americans play.
        """
        stats = {
            'local': {
                'players': [
                    {
                        'player': {
                            'person': {
                                'code': 'TEST',
                                'name': 'European, Player',
                                'country': {'code': 'ESP', 'name': 'Spain'}
                            }
                        },
                        'stats': {'points': 15}
                    }
                ]
            },
            'road': {'players': []}
        }

        result = extract_american_performances(sample_game, stats)
        assert len(result) == 0

    def test_extract_american_performances_with_none_stats(self, sample_game):
        """
        Test that None stats input returns empty list.
        """
        result = extract_american_performances(sample_game, None)
        assert result == []


# =============================================================================
# RUN TESTS
# =============================================================================
if __name__ == '__main__':
    # Run pytest with verbose output
    pytest.main([__file__, '-v'])
