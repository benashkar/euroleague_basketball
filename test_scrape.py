"""
=============================================================================
TEST SCRAPE SCRIPT - No Database Required
=============================================================================

This script tests the scrapers and saves data directly to JSON files.
It does NOT require MySQL to be running.

Usage:
    python test_scrape.py

Output:
    Creates JSON files in output/json/ directory
"""

import json
import os
import sys
from datetime import datetime
import logging

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our scrapers
from scrapers.euroleague_scraper import EuroLeagueScraper

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
    """Run test scraping."""
    logger.info("=" * 60)
    logger.info("STARTING TEST SCRAPE (No Database)")
    logger.info("=" * 60)

    # Initialize the scraper
    config = {
        'base_url': 'https://www.euroleaguebasketball.net/euroleague',
        'rate_limit_seconds': 2,
        'current_season_code': 'E2024'
    }
    scraper = EuroLeagueScraper(config)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # STEP 1: SCRAPE TEAMS
    # =========================================================================
    logger.info("")
    logger.info("-" * 40)
    logger.info("STEP 1: SCRAPING TEAMS")
    logger.info("-" * 40)

    teams = scraper.scrape_teams()
    logger.info(f"Found {len(teams)} teams")

    # Log team names
    for team in teams:
        logger.info(f"  - {team['team_name']} ({team.get('team_code', 'N/A')})")

    # Save teams to JSON
    teams_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'team_count': len(teams),
        'teams': teams
    }
    save_json(teams_export, f'teams_{timestamp}.json')

    if not teams:
        logger.error("No teams found! Cannot continue without teams.")
        return

    # =========================================================================
    # STEP 2: SCRAPE ROSTERS FOR EACH TEAM
    # =========================================================================
    logger.info("")
    logger.info("-" * 40)
    logger.info("STEP 2: SCRAPING ROSTERS")
    logger.info("-" * 40)

    all_players = []
    american_players = []

    for team in teams:
        team_name = team['team_name']
        team_slug = team['team_slug']
        team_id = team['team_id']

        logger.info(f"Scraping roster: {team_name}")

        try:
            players = scraper.scrape_roster(team_slug, team_id)
            logger.info(f"  Found {len(players)} players")

            # Track Americans
            for player in players:
                player['team_name'] = team_name  # Add team name for easy reference
                all_players.append(player)

                if player.get('is_american'):
                    american_players.append(player)
                    logger.info(f"    AMERICAN: {player['full_name']}")

        except Exception as e:
            logger.error(f"  Error: {e}")

    logger.info(f"\nTotal players: {len(all_players)}")
    logger.info(f"American players: {len(american_players)}")

    # Save all players
    players_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'player_count': len(all_players),
        'american_player_count': len(american_players),
        'players': all_players
    }
    save_json(players_export, f'all_players_{timestamp}.json')

    # Save American players separately
    american_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'player_count': len(american_players),
        'note': 'These players need hometown lookup from Basketball Reference/Wikipedia',
        'players': american_players
    }
    save_json(american_export, f'american_players_{timestamp}.json')

    # =========================================================================
    # STEP 3: SCRAPE SCHEDULE
    # =========================================================================
    logger.info("")
    logger.info("-" * 40)
    logger.info("STEP 3: SCRAPING SCHEDULE")
    logger.info("-" * 40)

    try:
        schedule = scraper.scrape_schedule()
        logger.info(f"Found {len(schedule)} games")

        # Save schedule
        schedule_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'game_count': len(schedule),
            'games': schedule
        }
        save_json(schedule_export, f'schedule_{timestamp}.json')

    except Exception as e:
        logger.error(f"Schedule scraping error: {e}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("SCRAPING COMPLETE!")
    logger.info("=" * 60)
    logger.info(f"Teams scraped: {len(teams)}")
    logger.info(f"Players scraped: {len(all_players)}")
    logger.info(f"American players found: {len(american_players)}")
    logger.info("")
    logger.info("JSON files saved to: output/json/")
    logger.info("")

    # List American players
    if american_players:
        logger.info("AMERICAN PLAYERS FOUND:")
        logger.info("-" * 40)
        for player in american_players:
            logger.info(f"  {player['full_name']} - {player.get('team_name', 'Unknown Team')}")
            if player.get('birth_country'):
                logger.info(f"    Country: {player['birth_country']}")


if __name__ == '__main__':
    main()
