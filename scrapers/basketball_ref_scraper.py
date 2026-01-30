"""
Basketball Reference scraper for hometown/high school lookup.

This is the PRIMARY source for finding hometown and high school data
for American players.

Target URLs:
- Search: https://www.basketball-reference.com/search/search.fcgi?search={name}
- Player page: https://www.basketball-reference.com/players/{letter}/{player_id}.html
- International players: https://www.basketball-reference.com/international/players/{player_id}.html

IMPORTANT: Basketball Reference has strict rate limiting.
Use 3+ seconds between requests.
"""

from typing import Dict, Optional, List
from .base_scraper import BaseScraper
import re
from config.settings import US_STATES, STATE_ABBREVIATIONS


class BasketballRefScraper(BaseScraper):
    """Scraper for Basketball Reference player data."""

    BASE_URL = "https://www.basketball-reference.com"
    SEARCH_URL = f"{BASE_URL}/search/search.fcgi"

    def __init__(self, config: dict = None):
        """
        Initialize Basketball Reference scraper.

        Args:
            config: Configuration dict
        """
        config = config or {'rate_limit_seconds': 3}
        config['base_url'] = self.BASE_URL
        # Enforce minimum 3 second rate limit
        config['rate_limit_seconds'] = max(config.get('rate_limit_seconds', 3), 3)
        super().__init__(config)

    def search_player(self, player_name: str) -> Optional[str]:
        """
        Search for player and return their profile URL.

        Args:
            player_name: Full name to search

        Returns:
            Profile URL if found, None otherwise
        """
        self.logger.info(f"Searching Basketball Reference for: {player_name}")

        params = {'search': player_name}
        response = self._get(self.SEARCH_URL, params=params, allow_redirects=True)

        if not response:
            return None

        # Check if we were redirected directly to a player page
        if '/players/' in response.url:
            self.logger.info(f"Direct redirect to: {response.url}")
            return response.url

        # Parse search results
        soup = self._parse_html(response)
        if not soup:
            return None

        # Look for player links in search results
        search_results = soup.find('div', {'id': 'players'})
        if not search_results:
            search_results = soup.find('div', class_='search-results')

        if not search_results:
            # Check for single result redirect in the page content
            player_link = soup.find('a', href=re.compile(r'/players/\w/\w+\.html'))
            if player_link:
                return self.BASE_URL + player_link['href']
            return None

        # Find best matching player
        player_links = search_results.find_all('a', href=re.compile(r'/players/'))
        if not player_links:
            return None

        # Return first result (best match)
        best_match = player_links[0]
        href = best_match.get('href', '')
        if href:
            return self.BASE_URL + href if not href.startswith('http') else href

        return None

    def scrape_player_info(self, player_url: str) -> Dict:
        """
        Scrape player biographical info from their page.

        Args:
            player_url: Full URL to player's Basketball Reference page

        Returns:
            Dict with hometown, high school, college info
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
            'source': 'basketball_reference',
            'lookup_successful': False
        }

        soup = self._get_soup(player_url)
        if not soup:
            return info

        # Find the info box (usually in #meta div or similar)
        info_box = soup.find('div', {'id': 'meta'})
        if not info_box:
            info_box = soup.find('div', {'id': 'info'})
        if not info_box:
            info_box = soup

        # Get photo
        photo_elem = soup.find('img', {'itemscope': 'image'})
        if not photo_elem:
            photo_elem = info_box.find('img') if info_box else None
        if photo_elem:
            info['photo_url'] = photo_elem.get('src', '')

        # Parse the player info paragraphs
        for p in info_box.find_all('p') if info_box else []:
            text = self.extract_text(p)

            # Born/Birthplace
            if 'born:' in text.lower() or 'birthplace' in text.lower():
                self._parse_birthplace_text(text, info)

            # High School
            if 'high school' in text.lower():
                self._parse_high_school_text(text, info)

            # College
            if 'college' in text.lower():
                self._parse_college_text(text, info)

        # Also look for structured data
        born_span = info_box.find('span', {'id': 'necro-birth'}) if info_box else None
        if born_span:
            # Get the parent or nearby text for location
            parent = born_span.parent
            if parent:
                parent_text = self.extract_text(parent)
                self._parse_birthplace_text(parent_text, info)

        # Check if we got the minimum data
        if info.get('hometown_state') or info.get('high_school'):
            info['lookup_successful'] = True

        return info

    def _parse_birthplace_text(self, text: str, info: Dict):
        """Parse birthplace text to extract city and state."""
        # Look for patterns like "in Chicago, Illinois" or "Chicago, IL"
        location_patterns = [
            r'in\s+([^,]+),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # in City, State
            r'in\s+([^,]+),\s*([A-Z]{2})\b',  # in City, ST
            r'born[^,]*,\s*([^,]+),\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',  # born date, City, State
        ]

        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                city = match.group(1).strip()
                state = match.group(2).strip()

                # Validate state
                if state in STATE_ABBREVIATIONS:
                    state = STATE_ABBREVIATIONS[state]

                if state in US_STATES:
                    info['hometown_city'] = city
                    info['hometown_state'] = state
                    self.logger.debug(f"Found birthplace: {city}, {state}")
                    return

    def _parse_high_school_text(self, text: str, info: Dict):
        """Parse high school text."""
        # Pattern: "High School: Name (City, State)" or "High School: Name in City, State"
        patterns = [
            r'high school[:\s]+([^(]+)\(([^,]+),\s*([^)]+)\)',  # Name (City, State)
            r'high school[:\s]+([^,]+),?\s+(?:in\s+)?([^,]+),\s*([A-Z][a-z]+)',  # Name in City, State
            r'high school[:\s]+([^\n(]+)',  # Just the name
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) >= 3:
                    info['high_school'] = match.group(1).strip()
                    info['high_school_city'] = match.group(2).strip()
                    state = match.group(3).strip()
                    if state in STATE_ABBREVIATIONS:
                        state = STATE_ABBREVIATIONS[state]
                    if state in US_STATES:
                        info['high_school_state'] = state
                elif len(match.groups()) >= 1:
                    info['high_school'] = match.group(1).strip()
                self.logger.debug(f"Found high school: {info.get('high_school')}")
                return

    def _parse_college_text(self, text: str, info: Dict):
        """Parse college text."""
        # Pattern: "College: University Name"
        match = re.search(r'college[:\s]+([^\n(]+)', text, re.IGNORECASE)
        if match:
            college = match.group(1).strip()
            # Clean up common suffixes
            college = re.sub(r'\s*\([^)]+\)\s*$', '', college)
            info['college'] = college
            self.logger.debug(f"Found college: {college}")

    def lookup_player(self, player_name: str) -> Optional[Dict]:
        """
        Complete lookup: search then scrape.

        Args:
            player_name: Full player name

        Returns:
            Dict with hometown/school info or None if not found
        """
        player_url = self.search_player(player_name)
        if player_url:
            return self.scrape_player_info(player_url)
        return None

    def _parse_birthplace(self, text: str) -> tuple:
        """
        Parse birthplace string into city and state.

        Args:
            text: Birthplace text

        Returns:
            Tuple of (city, state) or (None, None)
        """
        # Handle various formats
        patterns = [
            r'([^,]+),\s*([A-Za-z\s]+)$',  # City, State
            r'([^,]+),\s*([A-Z]{2})\b',  # City, ST
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                city = match.group(1).strip()
                state = match.group(2).strip()

                # Convert abbreviation to full name
                if state.upper() in STATE_ABBREVIATIONS:
                    state = STATE_ABBREVIATIONS[state.upper()]

                # Validate it's a US state
                if state in US_STATES:
                    return (city, state)

        return (None, None)

    def _parse_high_school(self, text: str) -> Dict:
        """
        Parse high school string.

        Args:
            text: High school text

        Returns:
            Dict with school_name, city, state
        """
        result = {
            'school_name': None,
            'city': None,
            'state': None
        }

        # Pattern: "School Name (City, State)"
        match = re.search(r'([^(]+)\s*\(([^,]+),\s*([^)]+)\)', text)
        if match:
            result['school_name'] = match.group(1).strip()
            result['city'] = match.group(2).strip()
            state = match.group(3).strip()
            if state.upper() in STATE_ABBREVIATIONS:
                state = STATE_ABBREVIATIONS[state.upper()]
            result['state'] = state
        else:
            # Just the school name
            result['school_name'] = text.strip()

        return result
