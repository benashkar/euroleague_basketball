"""
=============================================================================
SCRAPE EUROLEAGUE DATA - FULL API APPROACH
=============================================================================

Uses the EuroLeague v2 API to get player data WITH nationality information.
The /v2/competitions/E/seasons/E2024/people endpoint has full player bios.
"""

import json
import os
import requests
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API base URL
BASE_URL = 'https://api-live.euroleague.net'

# American nationality indicators
AMERICAN_CODES = ['USA', 'US']
AMERICAN_NAMES = ['United States', 'United States of America', 'America']


def is_american(country_data):
    """Check if country data indicates American player."""
    if not country_data:
        return False

    code = country_data.get('code', '').upper()
    name = country_data.get('name', '').lower()

    if code in AMERICAN_CODES:
        return True

    for american_name in AMERICAN_NAMES:
        if american_name.lower() in name:
            return True

    return False


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")
    return filepath


def fetch_clubs(season='E2024'):
    """Fetch all clubs for the season."""
    url = f'{BASE_URL}/v2/competitions/E/seasons/{season}/clubs'
    logger.info(f"Fetching clubs from {url}")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    clubs = data.get('data', [])
    logger.info(f"Found {len(clubs)} clubs")

    return clubs


def fetch_people(season='E2024'):
    """Fetch all people (players, coaches, etc.) for the season with nationality."""
    url = f'{BASE_URL}/v2/competitions/E/seasons/{season}/people'
    logger.info(f"Fetching people from {url}")

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    people = data.get('data', [])
    logger.info(f"Found {len(people)} people records")

    return people


def fetch_player_stats(season=2024):
    """Fetch player statistics using euroleague-api package."""
    try:
        from euroleague_api.player_stats import PlayerStats

        player_stats = PlayerStats(competition="E")
        df = player_stats.get_player_stats_single_season(
            endpoint="traditional",
            season=season,
            phase_type_code="RS",
            statistic_mode="PerGame"
        )

        logger.info(f"Fetched stats for {len(df)} players")
        return df.to_dict('records')
    except Exception as e:
        logger.error(f"Error fetching player stats: {e}")
        return []


def main():
    logger.info("=" * 60)
    logger.info("SCRAPING EUROLEAGUE DATA WITH FULL API")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # Fetch Clubs
    # =========================================================================
    logger.info("\n--- Fetching Clubs ---")
    clubs = fetch_clubs()

    clubs_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': 'E2024',
        'club_count': len(clubs),
        'clubs': clubs
    }
    save_json(clubs_export, f'euroleague_clubs_{timestamp}.json')

    # Print club names
    logger.info("Clubs:")
    for club in clubs:
        logger.info(f"  - {club.get('name')} ({club.get('code')})")

    # =========================================================================
    # Fetch People (Players with Nationality)
    # =========================================================================
    logger.info("\n--- Fetching People (Players) ---")
    people = fetch_people()

    # Process people data
    all_players = []
    american_players = []

    for record in people:
        person = record.get('person', {})
        club = record.get('club', {})

        # Get nationality
        country = person.get('country', {})
        birth_country = person.get('birthCountry', {})

        player_data = {
            'code': person.get('code'),
            'name': person.get('name'),
            'alias': person.get('alias'),
            'jersey_name': person.get('jerseyName'),
            'nationality': country.get('name') if country else None,
            'nationality_code': country.get('code') if country else None,
            'birth_country': birth_country.get('name') if birth_country else None,
            'birth_country_code': birth_country.get('code') if birth_country else None,
            'birth_date': person.get('birthDate'),
            'height': person.get('height'),
            'weight': person.get('weight'),
            'team_code': club.get('code'),
            'team_name': club.get('name'),
            'position': record.get('position'),
            'jersey_number': record.get('dorsal'),
            'active': record.get('active'),
        }

        all_players.append(player_data)

        # Check if American (by either nationality or birth country)
        if is_american(country) or is_american(birth_country):
            american_players.append(player_data)
            logger.info(f"  USA: {player_data['name']} - {player_data['team_name']} "
                       f"(nat: {player_data['nationality']}, birth: {player_data['birth_country']})")

    # Save all players
    players_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': 'E2024',
        'player_count': len(all_players),
        'players': all_players
    }
    save_json(players_export, f'euroleague_players_full_{timestamp}.json')

    # Save American players
    american_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': 'E2024',
        'american_player_count': len(american_players),
        'players': american_players
    }
    save_json(american_export, f'american_players_full_{timestamp}.json')

    # =========================================================================
    # Fetch Player Statistics
    # =========================================================================
    logger.info("\n--- Fetching Player Statistics ---")
    stats = fetch_player_stats()

    if stats:
        stats_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'season': 'E2024',
            'stat_count': len(stats),
            'stats': stats
        }
        save_json(stats_export, f'euroleague_stats_{timestamp}.json')

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Clubs: {len(clubs)}")
    logger.info(f"Total players/people: {len(all_players)}")
    logger.info(f"American players: {len(american_players)}")
    logger.info(f"Player statistics: {len(stats)}")

    if american_players:
        logger.info("\nAmerican Players Found:")
        for player in american_players:
            logger.info(f"  - {player['name']} ({player['team_name']}) - {player['position'] or 'N/A'}")


if __name__ == '__main__':
    main()
