"""
=============================================================================
HOMETOWN LOOKUP FOR AMERICAN PLAYERS
=============================================================================

Looks up hometown and high school information for American EuroLeague players
using Basketball Reference, Wikipedia, and Grokepedia.
Saves results to JSON without requiring a database.
"""

import json
import os
from datetime import datetime
import logging
import time

from services.hometown_lookup import HometownLookupService
from scrapers.basketball_ref_scraper import BasketballRefScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_american_players():
    """Load the most recent American players JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')

    # Find the most recent american_players_full file
    files = [f for f in os.listdir(output_dir) if f.startswith('american_players_full_')]
    if not files:
        logger.error("No american_players_full file found")
        return []

    # Sort by name (which includes timestamp) and get most recent
    latest_file = sorted(files)[-1]
    filepath = os.path.join(output_dir, latest_file)

    logger.info(f"Loading players from: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    players = data.get('players', [])
    logger.info(f"Loaded {len(players)} American players")

    return players


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
    logger.info("HOMETOWN LOOKUP FOR AMERICAN PLAYERS")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Load American players
    players = load_american_players()
    if not players:
        return

    # Deduplicate players (some appear multiple times for different teams)
    seen_codes = set()
    unique_players = []
    for player in players:
        code = player.get('code')
        if code and code not in seen_codes:
            seen_codes.add(code)
            unique_players.append(player)

    logger.info(f"Unique American players: {len(unique_players)}")

    # Initialize hometown lookup service (no database)
    lookup_service = HometownLookupService(db=None)

    # Process each player
    results = []
    success_count = 0
    failed_count = 0

    for i, player in enumerate(unique_players):
        player_name = player.get('name', '')
        team = player.get('team_name', 'Unknown')

        logger.info(f"\n[{i+1}/{len(unique_players)}] Looking up: {player_name} ({team})")

        try:
            # Clean up name format (API returns "LASTNAME, FIRSTNAME")
            if ', ' in player_name:
                parts = player_name.split(', ', 1)
                cleaned_name = f"{parts[1]} {parts[0]}"  # "FIRSTNAME LASTNAME"
            else:
                cleaned_name = player_name

            # Remove suffixes like "II", "III", "JR" for better matching
            cleaned_name = cleaned_name.title()  # Proper case

            # Lookup hometown
            result = lookup_service.lookup_player_hometown(cleaned_name)

            # Combine with player info
            player_result = {
                'code': player.get('code'),
                'name': player.get('name'),
                'clean_name': cleaned_name,
                'team_code': player.get('team_code'),
                'team_name': player.get('team_name'),
                'nationality': player.get('nationality'),
                'birth_date': player.get('birth_date'),
                'height': player.get('height'),
                'position': player.get('position'),
                # Hometown lookup results
                'hometown_city': result.get('hometown_city'),
                'hometown_state': result.get('hometown_state'),
                'high_school': result.get('high_school'),
                'high_school_city': result.get('high_school_city'),
                'high_school_state': result.get('high_school_state'),
                'college': result.get('college'),
                'photo_url': result.get('photo_url'),
                'profile_url': result.get('profile_url'),
                'lookup_source': result.get('source'),
                'lookup_successful': result.get('lookup_successful', False),
                'needs_manual_review': result.get('needs_manual_review', False)
            }

            results.append(player_result)

            if result.get('lookup_successful'):
                success_count += 1
                logger.info(f"  SUCCESS: {result.get('hometown_city')}, {result.get('hometown_state')}")
                if result.get('high_school'):
                    logger.info(f"  High School: {result.get('high_school')}")
                if result.get('college'):
                    logger.info(f"  College: {result.get('college')}")
            else:
                failed_count += 1
                logger.warning(f"  FAILED: Could not find hometown data")

            # Rate limiting
            time.sleep(1.5)

        except Exception as e:
            logger.error(f"Error processing {player_name}: {e}")
            failed_count += 1
            results.append({
                'code': player.get('code'),
                'name': player.get('name'),
                'team_name': player.get('team_name'),
                'lookup_successful': False,
                'error': str(e)
            })

    # Save results
    export_data = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': 'E2024',
        'total_players': len(unique_players),
        'successful_lookups': success_count,
        'failed_lookups': failed_count,
        'players': results
    }
    save_json(export_data, f'american_players_with_hometowns_{timestamp}.json')

    # Also save just the successful lookups
    successful_players = [p for p in results if p.get('lookup_successful')]
    success_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': 'E2024',
        'player_count': len(successful_players),
        'players': successful_players
    }
    save_json(success_export, f'american_players_hometowns_found_{timestamp}.json')

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("HOMETOWN LOOKUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total unique players: {len(unique_players)}")
    logger.info(f"Successful lookups: {success_count}")
    logger.info(f"Failed lookups: {failed_count}")
    logger.info(f"Success rate: {(success_count/len(unique_players)*100):.1f}%")

    # Print players with hometown found
    if successful_players:
        logger.info("\nPlayers with hometown found:")
        for p in successful_players[:20]:  # First 20
            logger.info(f"  - {p.get('clean_name')} ({p.get('team_name')}): "
                       f"{p.get('hometown_city')}, {p.get('hometown_state')}")


if __name__ == '__main__':
    main()
