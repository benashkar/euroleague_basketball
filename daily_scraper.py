"""
=============================================================================
EUROLEAGUE DAILY SCRAPER
=============================================================================

Comprehensive scraper that collects:
- All games/schedule with scores
- Box scores for completed games
- American player game performances
- Player rosters with nationality

Run daily to get fresh scores and game recaps.

Usage:
    python daily_scraper.py              # Full scrape
    python daily_scraper.py --recent     # Only recent games (last 7 days)
    python daily_scraper.py --today      # Only today's games
"""

import argparse
import json
import os
import requests
from datetime import datetime, timedelta
import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = 'https://api-live.euroleague.net'
SEASON = 'E2024'
COMPETITION = 'E'

# American nationality codes
AMERICAN_CODES = ['USA', 'US']


def is_american(country_data):
    """Check if country indicates American."""
    if not country_data:
        return False
    code = country_data.get('code', '').upper()
    return code in AMERICAN_CODES


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    logger.info(f"Saved: {filepath}")
    return filepath


def api_get(endpoint, params=None):
    """Make API request with error handling."""
    url = f"{BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"API error {endpoint}: {e}")
        return None


def fetch_clubs():
    """Fetch all clubs."""
    logger.info("Fetching clubs...")
    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/clubs')
    if data:
        clubs = data.get('data', [])
        logger.info(f"  Found {len(clubs)} clubs")
        return clubs
    return []


def fetch_players():
    """Fetch all players with nationality."""
    logger.info("Fetching players...")
    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/people')
    if data:
        people = data.get('data', [])
        logger.info(f"  Found {len(people)} people records")
        return people
    return []


def fetch_games():
    """Fetch all games/schedule."""
    logger.info("Fetching games/schedule...")
    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/games')
    if data:
        games = data.get('data', [])
        logger.info(f"  Found {len(games)} games")
        return games
    return []


def fetch_game_stats(game_code):
    """Fetch box score stats for a game."""
    data = api_get(f'/v2/competitions/{COMPETITION}/seasons/{SEASON}/games/{game_code}/stats')
    return data


def process_games(games, mode='all'):
    """Process games based on mode."""
    now = datetime.now()

    if mode == 'today':
        today = now.date()
        filtered = [g for g in games if g.get('date', '')[:10] == str(today)]
        logger.info(f"  Today's games: {len(filtered)}")
        return filtered

    elif mode == 'recent':
        week_ago = now - timedelta(days=7)
        filtered = [g for g in games
                   if g.get('played') and g.get('date', '') >= week_ago.isoformat()]
        logger.info(f"  Recent games (7 days): {len(filtered)}")
        return filtered

    else:  # all
        return games


def extract_american_performances(game, stats):
    """Extract American player performances from game stats."""
    performances = []

    if not stats:
        return performances

    game_info = {
        'game_code': game.get('gameCode'),
        'date': game.get('date'),
        'round': game.get('round'),
        'local_team': game.get('local', {}).get('club', {}).get('name'),
        'local_score': game.get('local', {}).get('score'),
        'road_team': game.get('road', {}).get('club', {}).get('name'),
        'road_score': game.get('road', {}).get('score'),
    }

    for side in ['local', 'road']:
        team_data = stats.get(side, {})
        team_name = game.get(side, {}).get('club', {}).get('name', 'Unknown')

        for player_stat in team_data.get('players', []):
            player = player_stat.get('player', {})
            person = player.get('person', {})
            stat = player_stat.get('stats', {})  # Stats are nested

            # Check if American
            country = person.get('country', {})
            birth_country = person.get('birthCountry', {})

            if is_american(country) or is_american(birth_country):
                # Convert time played (seconds) to minutes
                time_played = stat.get('timePlayed', 0)
                minutes = round(time_played / 60, 1) if time_played else 0

                perf = {
                    **game_info,
                    'team': team_name,
                    'player_code': person.get('code'),
                    'player_name': person.get('name'),
                    'nationality': country.get('name') if country else None,
                    'birth_country': birth_country.get('name') if birth_country else None,
                    'jersey': player.get('dorsal'),
                    'position': player.get('positionName'),
                    'starter': stat.get('startFive', False),
                    'minutes': minutes,
                    'points': int(stat.get('points', 0) or 0),
                    'rebounds': int(stat.get('totalRebounds', 0) or 0),
                    'assists': int(stat.get('assistances', 0) or 0),
                    'steals': int(stat.get('steals', 0) or 0),
                    'blocks': int(stat.get('blocksFavour', 0) or 0),
                    'turnovers': int(stat.get('turnovers', 0) or 0),
                    'fg_made': int(stat.get('fieldGoalsMadeTotal', 0) or 0),
                    'fg_attempted': int(stat.get('fieldGoalsAttemptedTotal', 0) or 0),
                    'three_made': int(stat.get('fieldGoalsMade3', 0) or 0),
                    'three_attempted': int(stat.get('fieldGoalsAttempted3', 0) or 0),
                    'ft_made': int(stat.get('freeThrowsMade', 0) or 0),
                    'ft_attempted': int(stat.get('freeThrowsAttempted', 0) or 0),
                    'plus_minus': int(stat.get('plusMinus', 0) or 0),
                    'pir': int(stat.get('valuation', 0) or 0),  # Performance Index Rating
                }
                performances.append(perf)

    return performances


def main():
    parser = argparse.ArgumentParser(description='EuroLeague Daily Scraper')
    parser.add_argument('--recent', action='store_true', help='Only recent games (7 days)')
    parser.add_argument('--today', action='store_true', help='Only today\'s games')
    parser.add_argument('--no-boxscores', action='store_true', help='Skip box score fetching')
    args = parser.parse_args()

    mode = 'today' if args.today else ('recent' if args.recent else 'all')

    logger.info("=" * 60)
    logger.info(f"EUROLEAGUE DAILY SCRAPER - Mode: {mode.upper()}")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # Fetch Clubs
    # =========================================================================
    clubs = fetch_clubs()
    if clubs:
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'count': len(clubs),
            'clubs': clubs
        }, f'clubs_{timestamp}.json')

    # =========================================================================
    # Fetch Players
    # =========================================================================
    people = fetch_players()

    # Process players and identify Americans
    all_players = []
    american_players = []

    for record in people:
        person = record.get('person', {})
        club = record.get('club', {})
        country = person.get('country', {})
        birth_country = person.get('birthCountry', {})

        player = {
            'code': person.get('code'),
            'name': person.get('name'),
            'nationality': country.get('name') if country else None,
            'nationality_code': country.get('code') if country else None,
            'birth_country': birth_country.get('name') if birth_country else None,
            'birth_country_code': birth_country.get('code') if birth_country else None,
            'birth_date': person.get('birthDate'),
            'height': person.get('height'),
            'weight': person.get('weight'),
            'team_code': club.get('code') if club else None,
            'team_name': club.get('name') if club else None,
            'position': record.get('position'),
            'jersey': record.get('dorsal'),
        }
        all_players.append(player)

        if is_american(country) or is_american(birth_country):
            american_players.append(player)

    # Deduplicate American players
    seen_codes = set()
    unique_americans = []
    for p in american_players:
        if p['code'] not in seen_codes:
            seen_codes.add(p['code'])
            unique_americans.append(p)

    logger.info(f"  American players: {len(unique_americans)}")

    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'count': len(all_players),
        'players': all_players
    }, f'players_{timestamp}.json')

    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'count': len(unique_americans),
        'players': unique_americans
    }, f'american_players_{timestamp}.json')

    # =========================================================================
    # Fetch Games/Schedule
    # =========================================================================
    all_games = fetch_games()
    games = process_games(all_games, mode)

    # Separate played and upcoming
    played_games = [g for g in games if g.get('played')]
    upcoming_games = [g for g in games if not g.get('played')]

    logger.info(f"  Played: {len(played_games)}, Upcoming: {len(upcoming_games)}")

    # Save schedule
    save_json({
        'export_date': datetime.now().isoformat(),
        'season': SEASON,
        'mode': mode,
        'total_games': len(games),
        'played': len(played_games),
        'upcoming': len(upcoming_games),
        'games': games
    }, f'schedule_{timestamp}.json')

    # =========================================================================
    # Fetch Box Scores for Played Games
    # =========================================================================
    all_american_performances = []
    game_recaps = []

    if not args.no_boxscores and played_games:
        logger.info(f"\nFetching box scores for {len(played_games)} played games...")

        for i, game in enumerate(played_games):
            game_code = game.get('gameCode')

            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i+1}/{len(played_games)}")

            stats = fetch_game_stats(game_code)
            if stats:
                # Extract American performances
                perfs = extract_american_performances(game, stats)
                all_american_performances.extend(perfs)

                # Create game recap
                recap = {
                    'game_code': game_code,
                    'date': game.get('date'),
                    'round': game.get('round'),
                    'phase': game.get('phaseType', {}).get('name'),
                    'local': {
                        'team': game.get('local', {}).get('club', {}).get('name'),
                        'score': game.get('local', {}).get('score'),
                        'quarters': game.get('local', {}).get('partials', {}),
                    },
                    'road': {
                        'team': game.get('road', {}).get('club', {}).get('name'),
                        'score': game.get('road', {}).get('score'),
                        'quarters': game.get('road', {}).get('partials', {}),
                    },
                    'winner': game.get('winner', {}).get('name'),
                    'venue': game.get('venue', {}).get('name'),
                    'american_players_count': len(perfs),
                }
                game_recaps.append(recap)

            time.sleep(0.2)  # Rate limiting

    # Save game recaps
    if game_recaps:
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'mode': mode,
            'game_count': len(game_recaps),
            'games': game_recaps
        }, f'game_recaps_{timestamp}.json')

    # Save American performances
    if all_american_performances:
        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'mode': mode,
            'performance_count': len(all_american_performances),
            'performances': all_american_performances
        }, f'american_performances_{timestamp}.json')

        # Also create a summary by player
        player_stats = {}
        for perf in all_american_performances:
            code = perf['player_code']
            if code not in player_stats:
                player_stats[code] = {
                    'player_code': code,
                    'player_name': perf['player_name'],
                    'team': perf['team'],
                    'nationality': perf['nationality'],
                    'games_played': 0,
                    'total_points': 0,
                    'total_rebounds': 0,
                    'total_assists': 0,
                    'performances': []
                }

            ps = player_stats[code]
            ps['games_played'] += 1
            ps['total_points'] += perf.get('points') or 0
            ps['total_rebounds'] += perf.get('rebounds') or 0
            ps['total_assists'] += perf.get('assists') or 0
            ps['performances'].append({
                'date': perf['date'],
                'opponent': perf['road_team'] if perf['team'] == perf['local_team'] else perf['local_team'],
                'points': perf.get('points'),
                'rebounds': perf.get('rebounds'),
                'assists': perf.get('assists'),
                'minutes': perf.get('minutes'),
            })

        # Calculate averages
        for ps in player_stats.values():
            gp = ps['games_played']
            if gp > 0:
                ps['ppg'] = round(ps['total_points'] / gp, 1)
                ps['rpg'] = round(ps['total_rebounds'] / gp, 1)
                ps['apg'] = round(ps['total_assists'] / gp, 1)

        # Sort by PPG
        player_summary = sorted(player_stats.values(), key=lambda x: x.get('ppg', 0), reverse=True)

        save_json({
            'export_date': datetime.now().isoformat(),
            'season': SEASON,
            'player_count': len(player_summary),
            'players': player_summary
        }, f'american_player_stats_{timestamp}.json')

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Clubs: {len(clubs)}")
    logger.info(f"Total players: {len(all_players)}")
    logger.info(f"American players: {len(unique_americans)}")
    logger.info(f"Games (mode={mode}): {len(games)} (played: {len(played_games)}, upcoming: {len(upcoming_games)})")
    logger.info(f"American game performances: {len(all_american_performances)}")

    if all_american_performances:
        # Top scorers
        top_games = sorted(all_american_performances, key=lambda x: x.get('points') or 0, reverse=True)[:5]
        logger.info("\nTop American performances:")
        for p in top_games:
            logger.info(f"  {p['player_name']}: {p['points']} pts vs {p['road_team'] if p['team'] == p['local_team'] else p['local_team']} ({p['date'][:10]})")


if __name__ == '__main__':
    main()
