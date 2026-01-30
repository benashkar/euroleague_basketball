"""
=============================================================================
JOIN ALL DATA INTO UNIFIED DATASET
=============================================================================

Combines:
- American players (with nationality)
- Hometown/college data
- Season statistics (aggregated from all games)
- Game-by-game performances

Output: A single comprehensive dataset ready for analysis or display.
"""

import json
import os
from datetime import datetime
import logging
from glob import glob

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_latest_json(pattern):
    """Load the most recent JSON file matching pattern."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = sorted(glob(os.path.join(output_dir, pattern)))
    if not files:
        return None
    with open(files[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    logger.info(f"Saved: {filepath}")


def main():
    logger.info("=" * 60)
    logger.info("JOINING ALL DATA")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Load all data sources
    logger.info("Loading data sources...")

    players_data = load_latest_json('american_players_2*.json')
    hometowns_data = load_latest_json('american_hometowns_found_*.json')
    stats_data = load_latest_json('american_player_stats_*.json')
    performances_data = load_latest_json('american_performances_*.json')
    schedule_data = load_latest_json('schedule_*.json')
    clubs_data = load_latest_json('clubs_*.json')

    if not players_data:
        logger.error("No player data found")
        return

    # Build hometown lookup by player code
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

    # Build stats lookup by player code
    stats_lookup = {}
    if stats_data:
        for p in stats_data.get('players', []):
            code = p.get('player_code')
            if code:
                stats_lookup[code] = {
                    'games_played': p.get('games_played', 0),
                    'total_points': p.get('total_points', 0),
                    'total_rebounds': p.get('total_rebounds', 0),
                    'total_assists': p.get('total_assists', 0),
                    'ppg': p.get('ppg', 0),
                    'rpg': p.get('rpg', 0),
                    'apg': p.get('apg', 0),
                }
        logger.info(f"  Loaded {len(stats_lookup)} player stats")

    # Build performances lookup by player code
    perf_lookup = {}
    if performances_data:
        for p in performances_data.get('performances', []):
            code = p.get('player_code')
            if code:
                if code not in perf_lookup:
                    perf_lookup[code] = []
                perf_lookup[code].append({
                    'date': p.get('date'),
                    'opponent': p.get('road_team') if p.get('team') == p.get('local_team') else p.get('local_team'),
                    'home_away': 'home' if p.get('team') == p.get('local_team') else 'away',
                    'team_score': p.get('local_score') if p.get('team') == p.get('local_team') else p.get('road_score'),
                    'opp_score': p.get('road_score') if p.get('team') == p.get('local_team') else p.get('local_score'),
                    'result': 'W' if (p.get('team') == p.get('local_team') and p.get('local_score', 0) > p.get('road_score', 0)) or
                                    (p.get('team') != p.get('local_team') and p.get('road_score', 0) > p.get('local_score', 0)) else 'L',
                    'points': p.get('points'),
                    'rebounds': p.get('rebounds'),
                    'assists': p.get('assists'),
                    'steals': p.get('steals'),
                    'blocks': p.get('blocks'),
                    'minutes': p.get('minutes'),
                    'fg': f"{p.get('fg_made', 0)}/{p.get('fg_attempted', 0)}",
                    'three': f"{p.get('three_made', 0)}/{p.get('three_attempted', 0)}",
                    'ft': f"{p.get('ft_made', 0)}/{p.get('ft_attempted', 0)}",
                    'plus_minus': p.get('plus_minus'),
                    'pir': p.get('pir'),
                })
        logger.info(f"  Loaded performances for {len(perf_lookup)} players")

    # Build unified player records
    unified_players = []
    players = players_data.get('players', [])

    for player in players:
        code = player.get('code')

        # Get hometown data
        hometown = hometown_lookup.get(code, {})

        # Get season stats
        stats = stats_lookup.get(code, {})

        # Get game performances
        games = perf_lookup.get(code, [])
        # Sort games by date (most recent first)
        games = sorted(games, key=lambda x: x.get('date', ''), reverse=True)

        # Clean up name
        name = player.get('name', '')
        if ', ' in name:
            parts = name.split(', ', 1)
            name = f"{parts[1]} {parts[0]}".title()

        unified = {
            # Player info
            'code': code,
            'name': name,
            'team': player.get('team_name'),
            'team_code': player.get('team_code'),
            'position': player.get('position'),
            'jersey': player.get('jersey'),
            'height_cm': player.get('height'),
            'birth_date': player.get('birth_date'),
            'nationality': player.get('nationality'),
            'birth_country': player.get('birth_country'),

            # Hometown/college
            'hometown_city': hometown.get('hometown_city'),
            'hometown_state': hometown.get('hometown_state'),
            'hometown': f"{hometown.get('hometown_city')}, {hometown.get('hometown_state')}" if hometown.get('hometown_city') and hometown.get('hometown_state') else None,
            'college': hometown.get('college'),
            'high_school': hometown.get('high_school'),

            # Season stats
            'games_played': stats.get('games_played', len(games)),
            'ppg': stats.get('ppg', 0),
            'rpg': stats.get('rpg', 0),
            'apg': stats.get('apg', 0),
            'total_points': stats.get('total_points', 0),
            'total_rebounds': stats.get('total_rebounds', 0),
            'total_assists': stats.get('total_assists', 0),

            # Recent performances (last 5 games)
            'recent_games': games[:5],

            # All performances
            'all_games': games,
        }

        unified_players.append(unified)

    # Sort by PPG
    unified_players.sort(key=lambda x: x.get('ppg', 0), reverse=True)

    logger.info(f"\nUnified {len(unified_players)} players")

    # Save full unified data
    full_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': '2024-25',
        'total_players': len(unified_players),
        'total_games_in_season': schedule_data.get('total_games', 0) if schedule_data else 0,
        'clubs': clubs_data.get('clubs', []) if clubs_data else [],
        'players': unified_players,
    }
    save_json(full_export, f'unified_american_players_{timestamp}.json')

    # Save summary version (without all_games)
    summary_players = []
    for p in unified_players:
        summary = {k: v for k, v in p.items() if k != 'all_games'}
        summary_players.append(summary)

    summary_export = {
        'export_date': datetime.now().isoformat(),
        'league': 'EuroLeague',
        'season': '2024-25',
        'total_players': len(summary_players),
        'players': summary_players,
    }
    save_json(summary_export, f'american_players_summary_{timestamp}.json')

    # Print top performers
    logger.info("\n" + "=" * 60)
    logger.info("TOP AMERICAN PLAYERS BY PPG")
    logger.info("=" * 60)
    for p in unified_players[:15]:
        hometown = p.get('hometown') or 'Unknown'
        logger.info(f"  {p['name']:25} {p['team']:30} {p['ppg']:5.1f} PPG | {hometown}")

    # Print by state
    logger.info("\n" + "=" * 60)
    logger.info("PLAYERS BY STATE")
    logger.info("=" * 60)
    by_state = {}
    for p in unified_players:
        state = p.get('hometown_state')
        if state:
            if state not in by_state:
                by_state[state] = []
            by_state[state].append(p['name'])

    for state in sorted(by_state.keys(), key=lambda s: len(by_state[s]), reverse=True)[:10]:
        logger.info(f"  {state}: {len(by_state[state])} players")


if __name__ == '__main__':
    main()
