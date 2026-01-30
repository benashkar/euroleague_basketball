"""
=============================================================================
HOMETOWN LOOKUP USING WIKIPEDIA API
=============================================================================

Uses the Wikipedia API to look up hometown data for American players.
Faster and more reliable than web scraping.
"""

import json
import os
import re
import requests
from datetime import datetime
import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Wikipedia API
WIKI_API = "https://en.wikipedia.org/w/api.php"

# US States for validation
US_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming', 'District of Columbia'
}


def load_american_players():
    """Load the most recent American players JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = [f for f in os.listdir(output_dir) if f.startswith('american_players_full_')]
    if not files:
        return []
    latest_file = sorted(files)[-1]
    filepath = os.path.join(output_dir, latest_file)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('players', [])


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    logger.info(f"Saved: {filepath}")
    return filepath


def clean_player_name(name):
    """Clean up player name for searching."""
    if ', ' in name:
        parts = name.split(', ', 1)
        name = f"{parts[1]} {parts[0]}"
    # Title case and clean suffixes
    name = name.title()
    # Remove Roman numerals at end
    name = re.sub(r'\s+(Ii|Iii|Iv|Jr\.?|Sr\.?)$', '', name, flags=re.IGNORECASE)
    return name.strip()


def search_wikipedia(name):
    """Search Wikipedia for a player."""
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': f'{name} basketball player',
        'format': 'json',
        'srlimit': 5
    }

    try:
        resp = requests.get(WIKI_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = data.get('query', {}).get('search', [])
        if results:
            # Return the title of best match
            return results[0].get('title')
    except Exception as e:
        logger.debug(f"Search error for {name}: {e}")

    return None


def get_wikipedia_page(title):
    """Get Wikipedia page content."""
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'extracts|revisions',
        'exintro': True,
        'explaintext': True,
        'format': 'json'
    }

    try:
        resp = requests.get(WIKI_API, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        pages = data.get('query', {}).get('pages', {})
        for page_id, page in pages.items():
            if page_id != '-1':
                return page.get('extract', '')
    except Exception as e:
        logger.debug(f"Page fetch error: {e}")

    return None


def parse_hometown_from_text(text):
    """Extract hometown info from Wikipedia text."""
    result = {
        'hometown_city': None,
        'hometown_state': None,
        'high_school': None,
        'college': None
    }

    if not text:
        return result

    # Patterns for birthplace
    birth_patterns = [
        r'born\s+(?:\w+\s+\d+,?\s+\d{4}(?:,?\s+)?)?(?:in\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'grew up in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
    ]

    for pattern in birth_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            state = match.group(2).strip()
            if state in US_STATES:
                result['hometown_city'] = city
                result['hometown_state'] = state
                break

    # Look for college
    college_patterns = [
        r'played\s+(?:college\s+)?basketball\s+(?:at|for)\s+(?:the\s+)?([A-Z][a-zA-Z\s]+(?:University|College|State))',
        r'attended\s+(?:the\s+)?([A-Z][a-zA-Z\s]+(?:University|College|State))',
        r'went to\s+(?:the\s+)?([A-Z][a-zA-Z\s]+(?:University|College|State))',
    ]

    for pattern in college_patterns:
        match = re.search(pattern, text)
        if match:
            result['college'] = match.group(1).strip()
            break

    # Look for high school
    hs_patterns = [
        r'attended\s+([A-Z][a-zA-Z\s]+High School)',
        r'played\s+(?:at|for)\s+([A-Z][a-zA-Z\s]+High School)',
    ]

    for pattern in hs_patterns:
        match = re.search(pattern, text)
        if match:
            result['high_school'] = match.group(1).strip()
            break

    return result


def lookup_player_hometown(name):
    """Look up a single player's hometown."""
    clean_name = clean_player_name(name)

    # Search Wikipedia
    title = search_wikipedia(clean_name)
    if not title:
        return None

    # Get page content
    content = get_wikipedia_page(title)
    if not content:
        return None

    # Parse hometown info
    info = parse_hometown_from_text(content)

    # Check if we found useful data
    if info.get('hometown_state') or info.get('college'):
        info['wiki_title'] = title
        info['lookup_successful'] = True
        return info

    return None


def main():
    logger.info("=" * 60)
    logger.info("HOMETOWN LOOKUP USING WIKIPEDIA API")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Load players
    players = load_american_players()
    if not players:
        logger.error("No players found")
        return

    # Deduplicate
    seen_codes = set()
    unique_players = []
    for player in players:
        code = player.get('code')
        if code and code not in seen_codes:
            seen_codes.add(code)
            unique_players.append(player)

    logger.info(f"Processing {len(unique_players)} unique players")

    results = []
    success_count = 0
    failed_count = 0

    for i, player in enumerate(unique_players):
        player_name = player.get('name', '')
        team = player.get('team_name', 'Unknown')
        clean_name = clean_player_name(player_name)

        logger.info(f"[{i+1}/{len(unique_players)}] {clean_name} ({team})")

        info = lookup_player_hometown(player_name)

        player_result = {
            'code': player.get('code'),
            'name': player_name,
            'clean_name': clean_name,
            'team_code': player.get('team_code'),
            'team_name': team,
            'nationality': player.get('nationality'),
            'birth_date': player.get('birth_date'),
            'height': player.get('height'),
            'position': player.get('position'),
        }

        if info and info.get('lookup_successful'):
            player_result.update(info)
            success_count += 1
            logger.info(f"  FOUND: {info.get('hometown_city')}, {info.get('hometown_state')} | College: {info.get('college')}")
        else:
            player_result['lookup_successful'] = False
            failed_count += 1
            logger.info(f"  Not found on Wikipedia")

        results.append(player_result)
        time.sleep(0.3)  # Rate limiting

    # Save all results
    export_data = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': 'E2024',
        'total_players': len(unique_players),
        'successful_lookups': success_count,
        'failed_lookups': failed_count,
        'players': results
    }
    save_json(export_data, f'american_players_wiki_{timestamp}.json')

    # Save successful lookups
    successful = [p for p in results if p.get('lookup_successful')]
    success_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': 'E2024',
        'player_count': len(successful),
        'players': successful
    }
    save_json(success_export, f'american_players_hometowns_{timestamp}.json')

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total players: {len(unique_players)}")
    logger.info(f"Found on Wikipedia: {success_count}")
    logger.info(f"Not found: {failed_count}")
    logger.info(f"Success rate: {(success_count/len(unique_players)*100):.1f}%")

    if successful:
        logger.info("\nPlayers with hometown found:")
        for p in successful[:15]:
            logger.info(f"  {p['clean_name']}: {p.get('hometown_city')}, {p.get('hometown_state')} | {p.get('college')}")


if __name__ == '__main__':
    main()
