"""
EuroLeague scraper implementation.

Target URLs:
- Teams list: https://www.euroleaguebasketball.net/euroleague/teams/
- Team roster: https://www.euroleaguebasketball.net/euroleague/teams/{team-slug}/roster/
- Player profile: https://www.euroleaguebasketball.net/euroleague/players/{player-slug}/
- Schedule: https://www.euroleaguebasketball.net/euroleague/game-center/
- Game stats: https://www.euroleaguebasketball.net/euroleague/game-center/{season}/{game-code}/

Also uses EuroLeague API:
- Base: https://api-live.euroleague.net
"""

from typing import List, Dict, Optional
from datetime import datetime
import re
import json
from .base_scraper import BaseScraper


class EuroLeagueScraper(BaseScraper):
    """Scraper for EuroLeague basketball data."""

    LEAGUE_ID = "EUROLEAGUE"
    BASE_URL = "https://www.euroleaguebasketball.net/euroleague"
    API_BASE = "https://api-live.euroleague.net"

    def __init__(self, config: dict = None):
        """
        Initialize EuroLeague scraper.

        Args:
            config: Configuration dict with API settings
        """
        config = config or {}
        config['base_url'] = config.get('base_url', self.BASE_URL)
        config['rate_limit_seconds'] = config.get('rate_limit_seconds', 2)
        super().__init__(config)

        self.api_base = config.get('api_base', self.API_BASE)
        self.current_season = config.get('current_season_code', 'E2024')

        # American nationality strings to check
        self.american_indicators = [
            'USA', 'United States', 'US', 'U.S.A.', 'U.S.',
            'American', 'United States of America'
        ]

    def scrape_teams(self) -> List[Dict]:
        """
        Scrape all EuroLeague teams.

        Tries API first, falls back to web scraping.

        Returns:
            List of team dicts with normalized IDs
        """
        teams = []

        # Try API first
        api_teams = self._scrape_teams_api()
        if api_teams:
            return api_teams

        # Fallback to web scraping
        self.logger.info("API failed, falling back to web scraping for teams")
        return self._scrape_teams_web()

    def _scrape_teams_api(self) -> List[Dict]:
        """Scrape teams from EuroLeague API."""
        # Try the clubs endpoint
        url = f"{self.api_base}/v2/competitions/E/seasons/{self.current_season}/clubs"

        data = self._get_json(url)
        if not data:
            # Try alternative endpoint
            url = f"{self.api_base}/v3/competitions/E/seasons/{self.current_season}/clubs"
            data = self._get_json(url)

        if not data:
            return []

        teams = []
        clubs = data if isinstance(data, list) else data.get('data', data.get('clubs', []))

        for club in clubs:
            team = self._parse_api_team(club)
            if team:
                teams.append(team)
                self.logger.info(f"Found team: {team['team_name']}")

        return teams

    def _parse_api_team(self, club: Dict) -> Optional[Dict]:
        """Parse team data from API response."""
        if not club:
            return None

        team_name = club.get('name', club.get('clubName', ''))
        if not team_name:
            return None

        team_code = club.get('code', club.get('clubCode', ''))
        team_slug = self._create_slug(team_name)

        return {
            'team_id': self.normalize_team_id(self.LEAGUE_ID, team_name),
            'league_id': self.LEAGUE_ID,
            'team_name': team_name,
            'team_name_normalized': self.normalize_name(team_name),
            'team_code': team_code,
            'team_slug': team_slug,
            'city': club.get('city', ''),
            'country': club.get('country', club.get('countryName', '')),
            'arena': club.get('arena', club.get('arenaName', '')),
            'arena_capacity': club.get('arenaCapacity'),
            'logo_url': club.get('images', {}).get('crest', club.get('logo', '')),
            'website_url': club.get('website', ''),
            'source_team_id': club.get('code', str(club.get('id', ''))),
            'is_active': True
        }

    def _scrape_teams_web(self) -> List[Dict]:
        """Scrape teams from web page."""
        url = f"{self.BASE_URL}/teams/"
        soup = self._get_soup(url)

        if not soup:
            return []

        teams = []
        seen_slugs = set()  # Track duplicates

        # Look for team roster links - they have format /euroleague/teams/{slug}/roster/{code}/
        team_links = soup.find_all('a', href=re.compile(r'/euroleague/teams/[^/]+/roster/'))

        for link in team_links:
            href = link.get('href', '')

            # Extract team slug from URL: /euroleague/teams/{slug}/roster/{code}/
            team_slug_match = re.search(r'/teams/([^/]+)/roster/([^/]+)/', href)
            if not team_slug_match:
                continue

            team_slug = team_slug_match.group(1)
            team_code = team_slug_match.group(2).upper()

            # Skip duplicates
            if team_slug in seen_slugs:
                continue
            seen_slugs.add(team_slug)

            # Get team name - convert slug to readable name
            # e.g., "anadolu-efes-istanbul" -> "Anadolu Efes Istanbul"
            team_name = team_slug.replace('-', ' ').title()

            # Try to find better team name from link text or nearby elements
            link_text = self.extract_text(link)
            if link_text and len(link_text) > 3 and not link_text.lower().startswith('roster'):
                team_name = link_text

            # Try to find logo
            logo = link.find('img')
            logo_url = logo.get('src', '') if logo else ''

            team = {
                'team_id': self.normalize_team_id(self.LEAGUE_ID, team_name),
                'league_id': self.LEAGUE_ID,
                'team_name': team_name,
                'team_name_normalized': self.normalize_name(team_name),
                'team_code': team_slug.upper()[:3] if team_slug else '',
                'team_slug': team_slug,
                'city': '',
                'country': '',
                'arena': '',
                'logo_url': logo_url,
                'source_team_id': team_slug,
                'is_active': True
            }
            teams.append(team)
            self.logger.info(f"Found team: {team_name}")

        return teams

    def scrape_roster(self, team_slug: str, team_id: str = None) -> List[Dict]:
        """
        Scrape roster for a specific team.

        Args:
            team_slug: Team URL slug
            team_id: Normalized team ID for player assignments

        Returns:
            List of player dicts
        """
        players = []

        # Try API first
        api_players = self._scrape_roster_api(team_slug)
        if api_players:
            players = api_players
        else:
            # Fallback to web scraping
            players = self._scrape_roster_web(team_slug)

        # Assign team_id to all players
        if team_id:
            for player in players:
                player['team_id'] = team_id

        return players

    def _scrape_roster_api(self, team_code: str) -> List[Dict]:
        """Scrape roster from API."""
        # Try club players endpoint
        url = f"{self.api_base}/v2/competitions/E/seasons/{self.current_season}/clubs/{team_code}/people"

        data = self._get_json(url)
        if not data:
            return []

        players = []
        people = data if isinstance(data, list) else data.get('data', data.get('players', []))

        for person in people:
            # Filter to players only
            if person.get('role', '').lower() not in ['player', '']:
                continue

            player = self._parse_api_player(person, team_code)
            if player:
                players.append(player)

        return players

    def _parse_api_player(self, person: Dict, team_code: str = '') -> Optional[Dict]:
        """Parse player data from API response."""
        if not person:
            return None

        # Get name
        first_name = person.get('name', person.get('firstName', ''))
        last_name = person.get('surname', person.get('lastName', ''))
        full_name = f"{first_name} {last_name}".strip()

        if not full_name:
            full_name = person.get('fullName', person.get('playerName', ''))

        if not full_name:
            return None

        # Parse nationality
        nationality = person.get('country', person.get('nationality', ''))
        is_american = self._identify_american(nationality)

        # Parse birth info
        birth_date = person.get('birthDate', person.get('dateOfBirth', ''))
        birth_year = None
        if birth_date:
            try:
                if isinstance(birth_date, str):
                    birth_year = int(birth_date[:4]) if len(birth_date) >= 4 else None
            except:
                pass

        # Parse height
        height_str = str(person.get('height', ''))
        height_cm = self.parse_height_cm(height_str)

        # Parse weight
        weight_str = str(person.get('weight', ''))
        weight_kg = self.parse_weight_kg(weight_str)

        # Get player code for profile URL
        player_code = person.get('code', person.get('personCode', ''))
        player_slug = self._create_slug(full_name)

        # Photo URL
        images = person.get('images', {})
        photo_url = images.get('portrait', images.get('action', images.get('default', '')))
        if not photo_url and person.get('imageUrl'):
            photo_url = person.get('imageUrl')

        return {
            'player_id': self.normalize_player_id(self.LEAGUE_ID, full_name),
            'league_id': self.LEAGUE_ID,
            'first_name': first_name,
            'last_name': last_name,
            'full_name': full_name,
            'full_name_normalized': self.normalize_name(full_name),
            'jersey_number': str(person.get('dorsal', person.get('jerseyNumber', ''))),
            'position': person.get('position', person.get('positionName', '')),
            'height_cm': height_cm,
            'height_display': height_str,
            'weight_kg': weight_kg,
            'weight_display': weight_str,
            'birth_date': birth_date if birth_date else None,
            'birth_year': birth_year,
            'birth_country': nationality,
            'is_american': is_american,
            'needs_hometown_lookup': is_american,
            'photo_url': photo_url,
            'euroleague_profile_url': f"{self.BASE_URL}/players/{player_slug}/" if player_slug else '',
            'source_player_id': player_code or str(person.get('personId', '')),
            'is_active': True
        }

    def _scrape_roster_web(self, team_slug: str) -> List[Dict]:
        """Scrape roster from web page."""
        url = f"{self.BASE_URL}/teams/{team_slug}/roster/"
        soup = self._get_soup(url)

        if not soup:
            return []

        players = []

        # Look for player cards
        player_elements = soup.find_all(['div', 'article'], class_=re.compile(r'player|roster'))

        for elem in player_elements:
            player = self._parse_web_player(elem)
            if player:
                players.append(player)

        # If no players found, try alternative structure
        if not players:
            # Try table format
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    player = self._parse_table_player(row)
                    if player:
                        players.append(player)

        return players

    def _parse_web_player(self, elem) -> Optional[Dict]:
        """Parse player from web element."""
        # Try to find player name
        name_elem = elem.find(['h2', 'h3', 'h4', 'a', 'span'], class_=re.compile(r'name|player'))
        if not name_elem:
            name_elem = elem.find('a', href=re.compile(r'/players/'))

        if not name_elem:
            return None

        full_name = self.extract_text(name_elem)
        if not full_name or len(full_name) < 3:
            return None

        # Parse name parts
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ''
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

        # Get player URL
        player_link = elem.find('a', href=re.compile(r'/players/'))
        player_url = player_link.get('href', '') if player_link else ''
        player_slug = ''
        if player_url:
            slug_match = re.search(r'/players/([^/]+)/', player_url)
            player_slug = slug_match.group(1) if slug_match else ''

        # Get jersey number
        jersey_elem = elem.find(class_=re.compile(r'number|jersey|dorsal'))
        jersey_number = self.extract_text(jersey_elem) if jersey_elem else ''
        jersey_number = re.sub(r'[^\d]', '', jersey_number)

        # Get position
        position_elem = elem.find(class_=re.compile(r'position|role'))
        position = self.extract_text(position_elem) if position_elem else ''

        # Get nationality
        country_elem = elem.find(class_=re.compile(r'country|nation|flag'))
        country = ''
        if country_elem:
            country = country_elem.get('title', '') or self.extract_text(country_elem)
            # Check for flag image with alt text
            flag_img = country_elem.find('img')
            if flag_img:
                country = flag_img.get('alt', country)

        is_american = self._identify_american(country)

        # Get photo
        photo_elem = elem.find('img')
        photo_url = photo_elem.get('src', '') if photo_elem else ''

        return {
            'player_id': self.normalize_player_id(self.LEAGUE_ID, full_name),
            'league_id': self.LEAGUE_ID,
            'first_name': first_name,
            'last_name': last_name,
            'full_name': full_name,
            'full_name_normalized': self.normalize_name(full_name),
            'jersey_number': jersey_number,
            'position': position,
            'birth_country': country,
            'is_american': is_american,
            'needs_hometown_lookup': is_american,
            'photo_url': photo_url,
            'euroleague_profile_url': f"https://www.euroleaguebasketball.net{player_url}" if player_url else '',
            'source_player_id': player_slug,
            'is_active': True
        }

    def _parse_table_player(self, row) -> Optional[Dict]:
        """Parse player from table row."""
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            return None

        # Usually: Number, Name, Position, ...
        full_name = self.extract_text(cells[1]) if len(cells) > 1 else ''
        if not full_name or len(full_name) < 3:
            return None

        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ''
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

        jersey_number = self.extract_text(cells[0]) if cells else ''
        jersey_number = re.sub(r'[^\d]', '', jersey_number)

        position = self.extract_text(cells[2]) if len(cells) > 2 else ''

        return {
            'player_id': self.normalize_player_id(self.LEAGUE_ID, full_name),
            'league_id': self.LEAGUE_ID,
            'first_name': first_name,
            'last_name': last_name,
            'full_name': full_name,
            'full_name_normalized': self.normalize_name(full_name),
            'jersey_number': jersey_number,
            'position': position,
            'is_american': False,
            'needs_hometown_lookup': False,
            'is_active': True
        }

    def scrape_player_profile(self, player_slug: str) -> Dict:
        """
        Scrape detailed player profile page.

        Args:
            player_slug: Player URL slug

        Returns:
            Dict with additional player details
        """
        url = f"{self.BASE_URL}/players/{player_slug}/"
        soup = self._get_soup(url)

        profile = {
            'player_slug': player_slug,
            'photos': []
        }

        if not soup:
            return profile

        # Get bio information
        bio_section = soup.find(class_=re.compile(r'bio|info|details'))
        if bio_section:
            # Look for birth place
            birth_elem = bio_section.find(text=re.compile(r'birth|born', re.I))
            if birth_elem:
                parent = birth_elem.parent
                if parent:
                    profile['birth_info'] = self.extract_text(parent)

        # Get all images
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and 'player' in src.lower():
                profile['photos'].append(src)

        # Get primary photo
        main_photo = soup.find('img', class_=re.compile(r'player|profile|main'))
        if main_photo:
            profile['photo_url'] = main_photo.get('src', '')

        return profile

    def scrape_schedule(self, season: str = None) -> List[Dict]:
        """
        Scrape season schedule.

        Args:
            season: Season code (e.g., 'E2024')

        Returns:
            List of game dicts
        """
        season = season or self.current_season

        # Try API first
        api_schedule = self._scrape_schedule_api(season)
        if api_schedule:
            return api_schedule

        # Fallback to web
        return self._scrape_schedule_web(season)

    def _scrape_schedule_api(self, season: str) -> List[Dict]:
        """Scrape schedule from API."""
        url = f"{self.api_base}/v2/competitions/E/seasons/{season}/games"

        data = self._get_json(url)
        if not data:
            return []

        games = []
        game_list = data if isinstance(data, list) else data.get('data', data.get('games', []))

        for game_data in game_list:
            game = self._parse_api_game(game_data, season)
            if game:
                games.append(game)

        self.logger.info(f"Found {len(games)} games from API")
        return games

    def _parse_api_game(self, game_data: Dict, season: str) -> Optional[Dict]:
        """Parse game from API response."""
        if not game_data:
            return None

        game_code = game_data.get('gameCode', game_data.get('code', ''))
        if not game_code:
            return None

        # Parse teams
        home_team = game_data.get('homeTeam', game_data.get('home', {}))
        away_team = game_data.get('awayTeam', game_data.get('away', {}))

        home_name = home_team.get('name', home_team.get('clubName', ''))
        away_name = away_team.get('name', away_team.get('clubName', ''))

        home_team_id = self.normalize_team_id(self.LEAGUE_ID, home_name) if home_name else None
        away_team_id = self.normalize_team_id(self.LEAGUE_ID, away_name) if away_name else None

        # Parse date/time
        game_date_str = game_data.get('date', game_data.get('gameDate', ''))
        game_time_str = game_data.get('time', game_data.get('gameTime', ''))

        game_date = None
        game_time = None
        game_datetime = None

        try:
            if game_date_str:
                if 'T' in game_date_str:
                    # ISO format
                    dt = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
                    game_date = dt.date()
                    game_time = dt.time()
                    game_datetime = dt
                else:
                    game_date = datetime.strptime(game_date_str[:10], '%Y-%m-%d').date()

            if game_time_str and not game_time:
                game_time = datetime.strptime(game_time_str[:5], '%H:%M').time()
        except:
            pass

        # Parse status
        status_str = game_data.get('status', game_data.get('gameStatus', 'scheduled')).lower()
        if 'played' in status_str or 'finished' in status_str or 'final' in status_str:
            status = 'completed'
        elif 'live' in status_str or 'progress' in status_str:
            status = 'in_progress'
        elif 'postponed' in status_str:
            status = 'postponed'
        elif 'cancelled' in status_str:
            status = 'cancelled'
        else:
            status = 'scheduled'

        # Parse scores
        home_score = game_data.get('homeScore', game_data.get('home', {}).get('score'))
        away_score = game_data.get('awayScore', game_data.get('away', {}).get('score'))

        # Parse round info
        round_number = game_data.get('round', game_data.get('roundNumber'))
        round_name = game_data.get('roundName', f"Round {round_number}" if round_number else '')
        phase = game_data.get('phase', game_data.get('phaseName', 'Regular Season'))

        return {
            'game_id': f"{self.LEAGUE_ID}_{season}_{game_code}",
            'league_id': self.LEAGUE_ID,
            'season': season[:5] if len(season) >= 5 else season,
            'season_code': season,
            'round_number': round_number,
            'round_name': round_name,
            'phase': phase,
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'game_date': game_date,
            'game_time': game_time,
            'game_datetime': game_datetime,
            'timezone': 'Europe/Madrid',
            'venue': game_data.get('arena', game_data.get('venue', '')),
            'city': game_data.get('city', ''),
            'country': game_data.get('country', ''),
            'status': status,
            'home_score': home_score,
            'away_score': away_score,
            'source_game_id': game_code,
            'game_url': f"{self.BASE_URL}/game-center/{season}/{game_code}/"
        }

    def _scrape_schedule_web(self, season: str) -> List[Dict]:
        """Scrape schedule from web page."""
        url = f"{self.BASE_URL}/game-center/"
        soup = self._get_soup(url)

        if not soup:
            return []

        games = []
        game_links = soup.find_all('a', href=re.compile(r'/game-center/\w+/\d+/'))

        for link in game_links:
            game = self._parse_web_game(link, season)
            if game:
                games.append(game)

        return games

    def _parse_web_game(self, elem, season: str) -> Optional[Dict]:
        """Parse game from web element."""
        href = elem.get('href', '')
        match = re.search(r'/game-center/(\w+)/(\d+)/', href)
        if not match:
            return None

        game_season = match.group(1)
        game_code = match.group(2)

        # Try to find team names
        team_elems = elem.find_all(class_=re.compile(r'team|club'))
        home_name = self.extract_text(team_elems[0]) if len(team_elems) > 0 else ''
        away_name = self.extract_text(team_elems[1]) if len(team_elems) > 1 else ''

        # Try to find date
        date_elem = elem.find(class_=re.compile(r'date|time'))
        date_str = self.extract_text(date_elem) if date_elem else ''

        return {
            'game_id': f"{self.LEAGUE_ID}_{game_season}_{game_code}",
            'league_id': self.LEAGUE_ID,
            'season': season,
            'season_code': game_season,
            'home_team_id': self.normalize_team_id(self.LEAGUE_ID, home_name) if home_name else None,
            'away_team_id': self.normalize_team_id(self.LEAGUE_ID, away_name) if away_name else None,
            'game_date': None,
            'status': 'scheduled',
            'source_game_id': game_code,
            'game_url': f"https://www.euroleaguebasketball.net{href}"
        }

    def scrape_game_stats(self, game_id: str) -> Dict:
        """
        Scrape box score for a completed game.

        Args:
            game_id: Game identifier (e.g., 'EUROLEAGUE_E2024_123')

        Returns:
            Dict with game stats including player stats
        """
        # Extract season and game code from game_id
        parts = game_id.split('_')
        if len(parts) < 3:
            return {}

        season = parts[1]
        game_code = parts[2]

        # Try API first
        api_stats = self._scrape_game_stats_api(season, game_code)
        if api_stats:
            return api_stats

        # Fallback to web
        return self._scrape_game_stats_web(season, game_code)

    def _scrape_game_stats_api(self, season: str, game_code: str) -> Dict:
        """Scrape game stats from API."""
        url = f"{self.api_base}/v2/competitions/E/seasons/{season}/games/{game_code}/boxscore"

        data = self._get_json(url)
        if not data:
            return {}

        game_stats = {
            'game_id': f"{self.LEAGUE_ID}_{season}_{game_code}",
            'final_score': {},
            'quarter_scores': {'home': [], 'away': []},
            'attendance': data.get('attendance'),
            'player_stats': []
        }

        # Parse team stats
        home_stats = data.get('homeTeam', data.get('home', {}))
        away_stats = data.get('awayTeam', data.get('away', {}))

        game_stats['final_score'] = {
            'home': home_stats.get('score', home_stats.get('total')),
            'away': away_stats.get('score', away_stats.get('total'))
        }

        # Parse quarter scores
        for team_data, key in [(home_stats, 'home'), (away_stats, 'away')]:
            quarters = team_data.get('quarters', team_data.get('byQuarter', []))
            if isinstance(quarters, list):
                game_stats['quarter_scores'][key] = [q.get('score', q) for q in quarters]

        # Parse player stats
        for team_data, is_home in [(home_stats, True), (away_stats, False)]:
            players = team_data.get('players', team_data.get('boxScore', []))
            team_code = team_data.get('code', team_data.get('clubCode', ''))

            for player_data in players:
                player_stat = self._parse_player_stat(player_data, is_home, team_code)
                if player_stat:
                    game_stats['player_stats'].append(player_stat)

        return game_stats

    def _parse_player_stat(self, data: Dict, is_home: bool, team_code: str) -> Optional[Dict]:
        """Parse individual player stats."""
        player_name = data.get('playerName', '')
        if not player_name:
            player_name = f"{data.get('name', '')} {data.get('surname', '')}".strip()

        if not player_name:
            return None

        # Parse minutes
        minutes_str = data.get('minutes', data.get('min', ''))
        minutes_decimal = None
        if minutes_str:
            try:
                if ':' in str(minutes_str):
                    parts = str(minutes_str).split(':')
                    minutes_decimal = float(parts[0]) + float(parts[1]) / 60
                else:
                    minutes_decimal = float(minutes_str)
            except:
                pass

        return {
            'player_id': self.normalize_player_id(self.LEAGUE_ID, player_name),
            'team_id': self.normalize_team_id(self.LEAGUE_ID, team_code) if team_code else None,
            'is_home_team': is_home,
            'is_starter': data.get('isStarter', data.get('starter', False)),
            'did_not_play': data.get('dnp', False) or minutes_str == 'DNP',
            'minutes_played': str(minutes_str),
            'minutes_decimal': minutes_decimal,
            'points': data.get('points', data.get('pts', 0)),
            'rebounds_total': data.get('totalRebounds', data.get('reb', 0)),
            'rebounds_offensive': data.get('offensiveRebounds', data.get('oReb', 0)),
            'rebounds_defensive': data.get('defensiveRebounds', data.get('dReb', 0)),
            'assists': data.get('assists', data.get('ast', 0)),
            'steals': data.get('steals', data.get('stl', 0)),
            'blocks': data.get('blocks', data.get('blk', 0)),
            'turnovers': data.get('turnovers', data.get('to', 0)),
            'fouls_personal': data.get('personalFouls', data.get('pf', 0)),
            'fouls_drawn': data.get('foulsDrawn', data.get('fd', 0)),
            'fg_made': data.get('fieldGoalsMade', data.get('fgm', 0)),
            'fg_attempted': data.get('fieldGoalsAttempted', data.get('fga', 0)),
            'fg_percentage': data.get('fieldGoalPercentage', data.get('fgPct')),
            'two_pt_made': data.get('twoPointersMade', data.get('2pm', 0)),
            'two_pt_attempted': data.get('twoPointersAttempted', data.get('2pa', 0)),
            'three_pt_made': data.get('threePointersMade', data.get('3pm', 0)),
            'three_pt_attempted': data.get('threePointersAttempted', data.get('3pa', 0)),
            'ft_made': data.get('freeThrowsMade', data.get('ftm', 0)),
            'ft_attempted': data.get('freeThrowsAttempted', data.get('fta', 0)),
            'plus_minus': data.get('plusMinus', data.get('pm')),
            'efficiency_rating': data.get('pir', data.get('efficiency', data.get('eff')))
        }

    def _scrape_game_stats_web(self, season: str, game_code: str) -> Dict:
        """Scrape game stats from web page."""
        url = f"{self.BASE_URL}/game-center/{season}/{game_code}/"
        soup = self._get_soup(url)

        if not soup:
            return {}

        # Basic structure - would need refinement based on actual page structure
        game_stats = {
            'game_id': f"{self.LEAGUE_ID}_{season}_{game_code}",
            'final_score': {},
            'player_stats': []
        }

        # Look for score elements
        score_elems = soup.find_all(class_=re.compile(r'score|result'))
        # Would need to parse based on actual structure

        return game_stats

    def _identify_american(self, nationality: str) -> bool:
        """Check if player nationality indicates American."""
        if not nationality:
            return False
        nationality_lower = nationality.lower()
        return any(ind.lower() in nationality_lower for ind in self.american_indicators)

    def _create_slug(self, name: str) -> str:
        """Create URL slug from name."""
        if not name:
            return ''
        slug = self.normalize_name(name).replace('_', '-')
        return slug
