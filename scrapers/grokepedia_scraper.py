"""
Grokepedia scraper for hometown/high school lookup.

This is the TERTIARY source, used when both Basketball Reference
and Wikipedia don't have the needed data.
"""

from typing import Dict, Optional
from .base_scraper import BaseScraper
import re
from config.settings import US_STATES, STATE_ABBREVIATIONS


class GrokepediaScraper(BaseScraper):
    """Scraper for Grokepedia player data."""

    BASE_URL = "https://grokepedia.com"

    def __init__(self, config: dict = None):
        """
        Initialize Grokepedia scraper.

        Args:
            config: Configuration dict
        """
        config = config or {'rate_limit_seconds': 2}
        config['base_url'] = self.BASE_URL
        super().__init__(config)

    def search_player(self, player_name: str) -> Optional[str]:
        """
        Search for player on Grokepedia.

        Args:
            player_name: Player name to search

        Returns:
            Player page URL if found
        """
        self.logger.info(f"Searching Grokepedia for: {player_name}")

        # Try search endpoint
        search_url = f"{self.BASE_URL}/search"
        params = {'q': f"{player_name} basketball"}

        response = self._get(search_url, params=params)
        if not response:
            return None

        soup = self._parse_html(response)
        if not soup:
            return None

        # Look for player links in search results
        player_links = soup.find_all('a', href=re.compile(r'/wiki/|/player/|/person/'))

        for link in player_links:
            link_text = self.extract_text(link).lower()
            # Check if this looks like our player
            if self._name_matches(player_name, link_text):
                href = link.get('href', '')
                if href.startswith('/'):
                    return self.BASE_URL + href
                return href

        return None

    def _name_matches(self, search_name: str, found_name: str) -> bool:
        """Check if names approximately match."""
        search_parts = set(search_name.lower().split())
        found_parts = set(found_name.lower().split())

        # Check if most search parts are in found name
        matches = len(search_parts & found_parts)
        return matches >= len(search_parts) * 0.7

    def scrape_player_info(self, player_url: str) -> Dict:
        """
        Scrape player info from Grokepedia page.

        Args:
            player_url: URL to player page

        Returns:
            Dict with player info
        """
        info = {
            'hometown_city': None,
            'hometown_state': None,
            'high_school': None,
            'high_school_city': None,
            'high_school_state': None,
            'college': None,
            'photo_url': None,
            'profile_url': player_url,
            'source': 'grokepedia',
            'lookup_successful': False
        }

        soup = self._get_soup(player_url)
        if not soup:
            return info

        # Look for info sections - structure may vary
        content = soup.find(['article', 'main', 'div'], class_=re.compile(r'content|article|main'))
        if not content:
            content = soup

        # Get all text and look for key information
        full_text = self.extract_text(content)

        # Look for birthplace patterns
        birthplace_patterns = [
            r'born\s+(?:in\s+)?([^,\n]+),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'birthplace[:\s]+([^,\n]+),\s*([A-Za-z\s]+)',
            r'from\s+([^,\n]+),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]

        for pattern in birthplace_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                city = match.group(1).strip()
                state = match.group(2).strip()

                if state.upper() in STATE_ABBREVIATIONS:
                    state = STATE_ABBREVIATIONS[state.upper()]

                if state in US_STATES:
                    info['hometown_city'] = city
                    info['hometown_state'] = state
                    break

        # Look for high school patterns
        hs_patterns = [
            r'high\s+school[:\s]+([^,\n]+)',
            r'attended\s+([^,\n]+)\s+high\s+school',
            r'([A-Za-z\s]+)\s+High\s+School',
        ]

        for pattern in hs_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                info['high_school'] = match.group(1).strip()
                break

        # Look for college patterns
        college_patterns = [
            r'college[:\s]+([^\n(]+)',
            r'played\s+(?:college\s+)?(?:basketball\s+)?(?:at|for)\s+([A-Za-z\s]+(?:University|College))',
            r'attended\s+([A-Za-z\s]+(?:University|College))',
        ]

        for pattern in college_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                info['college'] = match.group(1).strip()
                break

        # Look for images
        images = content.find_all('img')
        for img in images:
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            if 'player' in alt or 'photo' in alt or 'portrait' in alt:
                info['photo_url'] = src if src.startswith('http') else self.BASE_URL + src
                break

        # Check if lookup was successful
        if info.get('hometown_state') or info.get('high_school'):
            info['lookup_successful'] = True

        return info

    def lookup_player(self, player_name: str) -> Optional[Dict]:
        """
        Search and scrape player info from Grokepedia.

        Args:
            player_name: Player name to look up

        Returns:
            Dict with hometown/school info or None if not found
        """
        player_url = self.search_player(player_name)
        if player_url:
            return self.scrape_player_info(player_url)
        return None
