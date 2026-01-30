"""
=============================================================================
SCRAPE WITH EUROLEAGUE API PACKAGE
=============================================================================

Uses the official euroleague-api package to get player data with nationalities.
"""

import json
import os
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import euroleague_api
from euroleague_api.player_stats import PlayerStats
from euroleague_api.team_stats import TeamStats

# American nationality indicators
AMERICAN_NATIONALITIES = ['USA', 'United States', 'US', 'U.S.A.', 'American']


def is_american(nationality):
    """Check if nationality indicates American player."""
    if not nationality:
        return False
    nationality_lower = str(nationality).lower()
    return any(ind.lower() in nationality_lower for ind in AMERICAN_NATIONALITIES)


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")
    return filepath


def main():
    logger.info("=" * 60)
    logger.info("SCRAPING EUROLEAGUE DATA WITH OFFICIAL API")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Initialize the API client
    # Competition: E = EuroLeague, U = EuroCup
    # Season code format: E2024 (for 2024-25 season)
    player_stats = PlayerStats(competition="E")
    team_stats = TeamStats(competition="E")

    # =========================================================================
    # Get Player Stats with Player Info
    # =========================================================================
    logger.info("\nFetching player statistics...")

    try:
        # Get traditional stats - this includes player names and teams
        # Phase type: RS = Regular Season, PO = Playoffs, FF = Final Four
        # Season is the start year (2024 for 2024-25 season)
        df = player_stats.get_player_stats_single_season(
            endpoint="traditional",
            season=2024,
            phase_type_code="RS",
            statistic_mode="PerGame"
        )

        logger.info(f"Retrieved {len(df)} player records")

        # Print columns to see what data we have
        logger.info(f"Available columns: {list(df.columns)}")

        # Convert to list of dicts
        all_players = df.to_dict('records')

        # Find American players
        american_players = []

        # Check if nationality column exists
        nationality_col = None
        for col in ['country', 'nationality', 'playerCountry', 'Country']:
            if col in df.columns:
                nationality_col = col
                break

        if nationality_col:
            logger.info(f"Found nationality column: {nationality_col}")
            for player in all_players:
                if is_american(player.get(nationality_col)):
                    american_players.append(player)
                    logger.info(f"  AMERICAN: {player.get('playerName', 'Unknown')} - {player.get('teamName', 'Unknown')}")
        else:
            logger.warning("No nationality column found in data")
            logger.info("Available columns: " + ", ".join(df.columns))

        # Save all players
        players_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'season': 'E2024',
            'player_count': len(all_players),
            'players': all_players
        }
        save_json(players_export, f'euroleague_players_{timestamp}.json')

        # Save American players
        american_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'season': 'E2024',
            'player_count': len(american_players),
            'players': american_players
        }
        save_json(american_export, f'american_players_api_{timestamp}.json')

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total players: {len(all_players)}")
        logger.info(f"American players: {len(american_players)}")

        # Print first few player records to see structure
        if all_players:
            logger.info("\nSample player data (first player):")
            for key, value in list(all_players[0].items())[:15]:
                logger.info(f"  {key}: {value}")

    except Exception as e:
        logger.error(f"Error fetching player stats: {e}")
        import traceback
        traceback.print_exc()

    # =========================================================================
    # Get Team Stats
    # =========================================================================
    logger.info("\n" + "-" * 40)
    logger.info("Fetching team statistics...")

    try:
        team_df = team_stats.get_team_stats_single_season(
            endpoint="traditional",
            season=2024,
            phase_type_code="RS",
            statistic_mode="PerGame"
        )

        logger.info(f"Retrieved {len(team_df)} teams")

        teams = team_df.to_dict('records')

        # Save teams
        teams_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'season': 'E2024',
            'team_count': len(teams),
            'teams': teams
        }
        save_json(teams_export, f'euroleague_teams_api_{timestamp}.json')

        # Print team names
        logger.info("Teams:")
        for team in teams:
            logger.info(f"  - {team.get('teamName', 'Unknown')}")

    except Exception as e:
        logger.error(f"Error fetching team stats: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
