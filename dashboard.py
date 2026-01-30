"""
=============================================================================
SIMPLE WEB DASHBOARD
=============================================================================

PURPOSE:
    A simple web interface to view American player data without needing
    a database or SQL knowledge. Just run this script and open your browser.

HOW TO USE:
    1. Run this script:
           python dashboard.py
    2. Open your browser to:
           http://localhost:5000
    3. Browse players, filter by team, state, or search

DEPENDENCIES:
    pip install flask

FEATURES:
    - View all American players with stats
    - Filter by team, hometown state
    - Search by player name
    - View player detail pages with game logs
    - Sort by PPG, RPG, APG, name, or team

WHY A SIMPLE DASHBOARD:
    - No database setup required
    - Reads directly from JSON files
    - Easy to customize and extend
    - Runs locally for development/testing
"""

import json
import os
from glob import glob
from flask import Flask, render_template_string, request

# =============================================================================
# FLASK APP SETUP
# =============================================================================
app = Flask(__name__)


# =============================================================================
# DATA LOADING
# =============================================================================

def load_latest_data():
    """
    Load the most recent unified player data.

    Returns the data from american_players_summary_*.json
    (uses summary version because it's smaller and faster to load)
    """
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = sorted(glob(os.path.join(output_dir, 'american_players_summary_*.json')))

    if not files:
        return {'players': [], 'export_date': 'No data'}

    with open(files[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def load_player_detail(player_code):
    """
    Load full player data including all games.

    Uses unified_american_players_*.json for the full game log.
    """
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    files = sorted(glob(os.path.join(output_dir, 'unified_american_players_*.json')))

    if not files:
        return None

    with open(files[-1], 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Find the specific player
    for player in data.get('players', []):
        if player.get('code') == player_code:
            return player

    return None


# =============================================================================
# HTML TEMPLATES
# =============================================================================
# Using inline templates for simplicity (no separate template files needed)

BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>EuroLeague American Players</title>
    <style>
        /* Basic styling - feel free to customize! */
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #1a1a2e; }
        .filters {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .filters select, .filters input {
            padding: 8px;
            margin-right: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        table {
            width: 100%;
            background: white;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th {
            background: #1a1a2e;
            color: white;
            padding: 12px 8px;
            text-align: left;
        }
        th a { color: white; text-decoration: none; }
        td {
            padding: 10px 8px;
            border-bottom: 1px solid #eee;
        }
        tr:hover { background: #f9f9f9; }
        a { color: #4361ee; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .stats { font-weight: bold; }
        .hometown { color: #666; font-size: 0.9em; }
        .last-updated {
            color: #666;
            font-size: 0.85em;
            margin-bottom: 10px;
        }
        .player-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .game-log { font-size: 0.9em; }
        .win { color: #2ecc71; }
        .loss { color: #e74c3c; }
    </style>
</head>
<body>
    <h1>EuroLeague American Players Dashboard</h1>
    {% block content %}{% endblock %}
</body>
</html>
"""

HOME_TEMPLATE = """
{% extends "base" %}
{% block content %}
<p class="last-updated">Last updated: {{ export_date }}</p>

<div class="filters">
    <form method="GET">
        <input type="text" name="search" placeholder="Search by name..."
               value="{{ search }}">

        <select name="team">
            <option value="">All Teams</option>
            {% for team in teams %}
            <option value="{{ team }}" {% if team == selected_team %}selected{% endif %}>
                {{ team }}
            </option>
            {% endfor %}
        </select>

        <select name="state">
            <option value="">All States</option>
            {% for state in states %}
            <option value="{{ state }}" {% if state == selected_state %}selected{% endif %}>
                {{ state }}
            </option>
            {% endfor %}
        </select>

        <button type="submit">Filter</button>
        <a href="/">Reset</a>
    </form>
</div>

<table>
    <thead>
        <tr>
            <th><a href="?sort=name&{{ query_string }}">Player</a></th>
            <th><a href="?sort=team&{{ query_string }}">Team</a></th>
            <th>Position</th>
            <th><a href="?sort=ppg&{{ query_string }}">PPG</a></th>
            <th><a href="?sort=rpg&{{ query_string }}">RPG</a></th>
            <th><a href="?sort=apg&{{ query_string }}">APG</a></th>
            <th>GP</th>
            <th>Hometown</th>
            <th>College</th>
        </tr>
    </thead>
    <tbody>
        {% for player in players %}
        <tr>
            <td><a href="/player/{{ player.code }}">{{ player.name }}</a></td>
            <td>{{ player.team or 'N/A' }}</td>
            <td>{{ player.position or 'N/A' }}</td>
            <td class="stats">{{ "%.1f"|format(player.ppg or 0) }}</td>
            <td class="stats">{{ "%.1f"|format(player.rpg or 0) }}</td>
            <td class="stats">{{ "%.1f"|format(player.apg or 0) }}</td>
            <td>{{ player.games_played or 0 }}</td>
            <td class="hometown">{{ player.hometown or 'Unknown' }}</td>
            <td>{{ player.college or 'N/A' }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<p>Showing {{ players|length }} players</p>
{% endblock %}
"""

PLAYER_TEMPLATE = """
{% extends "base" %}
{% block content %}
<a href="/">&larr; Back to all players</a>

<div class="player-card">
    <h2>{{ player.name }}</h2>
    <p>
        <strong>Team:</strong> {{ player.team or 'N/A' }}<br>
        <strong>Position:</strong> {{ player.position or 'N/A' }}<br>
        <strong>Jersey:</strong> #{{ player.jersey or 'N/A' }}<br>
        <strong>Height:</strong> {{ player.height_cm or 'N/A' }} cm<br>
        <strong>Birth Date:</strong> {{ player.birth_date or 'N/A' }}
    </p>
    <p>
        <strong>Hometown:</strong> {{ player.hometown or 'Unknown' }}<br>
        <strong>College:</strong> {{ player.college or 'N/A' }}<br>
        <strong>High School:</strong> {{ player.high_school or 'N/A' }}
    </p>
</div>

<div class="player-card">
    <h3>Season Statistics</h3>
    <p>
        <strong>Games Played:</strong> {{ player.games_played or 0 }}<br>
        <strong>Points Per Game:</strong> {{ "%.1f"|format(player.ppg or 0) }}<br>
        <strong>Rebounds Per Game:</strong> {{ "%.1f"|format(player.rpg or 0) }}<br>
        <strong>Assists Per Game:</strong> {{ "%.1f"|format(player.apg or 0) }}
    </p>
    <p>
        <strong>Total Points:</strong> {{ player.total_points or 0 }}<br>
        <strong>Total Rebounds:</strong> {{ player.total_rebounds or 0 }}<br>
        <strong>Total Assists:</strong> {{ player.total_assists or 0 }}
    </p>
</div>

{% if player.all_games %}
<div class="player-card">
    <h3>Game Log</h3>
    <table class="game-log">
        <thead>
            <tr>
                <th>Date</th>
                <th>Opponent</th>
                <th>H/A</th>
                <th>Result</th>
                <th>Score</th>
                <th>PTS</th>
                <th>REB</th>
                <th>AST</th>
                <th>MIN</th>
                <th>FG</th>
                <th>3PT</th>
                <th>FT</th>
            </tr>
        </thead>
        <tbody>
            {% for game in player.all_games %}
            <tr>
                <td>{{ game.date[:10] if game.date else 'N/A' }}</td>
                <td>{{ game.opponent or 'N/A' }}</td>
                <td>{{ game.home_away or 'N/A' }}</td>
                <td class="{{ 'win' if game.result == 'W' else 'loss' }}">
                    {{ game.result or 'N/A' }}
                </td>
                <td>{{ game.team_score or 0 }}-{{ game.opp_score or 0 }}</td>
                <td><strong>{{ game.points or 0 }}</strong></td>
                <td>{{ game.rebounds or 0 }}</td>
                <td>{{ game.assists or 0 }}</td>
                <td>{{ game.minutes or 0 }}</td>
                <td>{{ game.fg or 'N/A' }}</td>
                <td>{{ game.three or 'N/A' }}</td>
                <td>{{ game.ft or 'N/A' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}
{% endblock %}
"""


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def home():
    """
    Main page showing all players with filtering options.
    """
    # Load data
    data = load_latest_data()
    players = data.get('players', [])
    export_date = data.get('export_date', 'Unknown')

    # Get filter parameters from URL
    search = request.args.get('search', '').lower()
    selected_team = request.args.get('team', '')
    selected_state = request.args.get('state', '')
    sort_by = request.args.get('sort', 'ppg')

    # Apply filters
    if search:
        players = [p for p in players if search in p.get('name', '').lower()]

    if selected_team:
        players = [p for p in players if p.get('team') == selected_team]

    if selected_state:
        players = [p for p in players if p.get('hometown_state') == selected_state]

    # Sort
    sort_key = sort_by if sort_by in ['name', 'team', 'ppg', 'rpg', 'apg'] else 'ppg'
    reverse = sort_by in ['ppg', 'rpg', 'apg']  # Numeric sorts are descending
    players = sorted(players, key=lambda p: p.get(sort_key) or 0, reverse=reverse)

    # Get unique teams and states for filter dropdowns
    all_data = load_latest_data()
    all_players = all_data.get('players', [])
    teams = sorted(set(p.get('team') for p in all_players if p.get('team')))
    states = sorted(set(p.get('hometown_state') for p in all_players if p.get('hometown_state')))

    # Build query string for sort links (preserving other filters)
    query_parts = []
    if search:
        query_parts.append(f"search={search}")
    if selected_team:
        query_parts.append(f"team={selected_team}")
    if selected_state:
        query_parts.append(f"state={selected_state}")
    query_string = '&'.join(query_parts)

    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}',
                              HOME_TEMPLATE.replace('{% extends "base" %}', '')),
        players=players,
        export_date=export_date,
        teams=teams,
        states=states,
        search=search,
        selected_team=selected_team,
        selected_state=selected_state,
        query_string=query_string
    )


@app.route('/player/<code>')
def player_detail(code):
    """
    Player detail page with full game log.
    """
    player = load_player_detail(code)

    if not player:
        return "Player not found", 404

    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}',
                              PLAYER_TEMPLATE.replace('{% extends "base" %}', '')),
        player=player
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("EUROLEAGUE AMERICAN PLAYERS DASHBOARD")
    print("=" * 60)
    print("\nStarting web server...")
    print("Open your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server\n")

    # Run the Flask development server
    # debug=True enables auto-reload when you change code
    # host='0.0.0.0' makes it accessible from other machines on your network
    app.run(debug=True, host='0.0.0.0', port=5000)
