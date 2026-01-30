"""
Wikipedia scraper for hometown/high school lookup.

This is the SECONDARY source, used when Basketball Reference
doesn't have the player or is missing data.

Uses Wikipedia API for reliable data access.

API Endpoints:
- Page summary: https://en.wikipedia.org/api/rest_v1/page/summary/{title}
- Search: https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}
- Parse (for infobox): https://en.wikipedia.org/w/api.php?action=parse&page={title}&prop=wikitext
"""

from typing import Dict, Optional
from .base_scraper import BaseScraper
import re
import urllib.parse
from config.settings import US_STATES, STATE_ABBREVIATIONS


class WikipediaScraper(BaseScraper):
    """Scraper for Wikipedia player data."""

    API_BASE = "https://en.wikipedia.org/api/rest_v1"
    WIKI_API = "https://en.wikipedia.org/w/api.php"

    def __init__(self, config: dict = None):
        """
        Initialize Wikipedia scraper.

        Args:
            config: Configuration dict
        """
        config = config or {'rate_limit_seconds': 1}
        config['base_url'] = self.API_BASE
        super().__init__(config)

    def search_player(self, player_name: str) -> Optional[str]:
        """
        Search Wikipedia for player.

        Args:
            player_name: Player name to search

        Returns:
            Wikipedia page title if found
        """
        self.logger.info(f"Searching Wikipedia for: {player_name}")

        # Search with "basketball player" to narrow results
        search_query = f"{player_name} basketball player"

        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': search_query,
            'format': 'json',
            'srlimit': 5
        }

        data = self._get_json(self.WIKI_API, params=params)
        if not data:
            return None

        search_results = data.get('query', {}).get('search', [])
        if not search_results:
            # Try without "basketball player"
            params['srsearch'] = player_name
            data = self._get_json(self.WIKI_API, params=params)
            if data:
                search_results = data.get('query', {}).get('search', [])

        if not search_results:
            return None

        # Return best match (first result)
        return search_results[0].get('title')

    def get_page_summary(self, title: str) -> Optional[Dict]:
        """
        Get page summary via REST API.

        Args:
            title: Wikipedia page title

        Returns:
            Summary data including extract and thumbnail
        """
        encoded_title = urllib.parse.quote(title.replace(' ', '_'))
        url = f"{self.API_BASE}/page/summary/{encoded_title}"

        data = self._get_json(url)
        if not data:
            return None

        return {
            'title': data.get('title'),
            'extract': data.get('extract', ''),
            'thumbnail': data.get('thumbnail', {}).get('source'),
            'originalimage': data.get('originalimage', {}).get('source'),
            'page_url': data.get('content_urls', {}).get('desktop', {}).get('page')
        }

    def get_infobox_data(self, title: str) -> Dict:
        """
        Parse page to extract infobox data.

        Args:
            title: Wikipedia page title

        Returns:
            Dict with parsed infobox fields
        """
        info = {
            'birth_place': None,
            'high_school': None,
            'college': None,
            'image': None
        }

        params = {
            'action': 'parse',
            'page': title,
            'prop': 'wikitext',
            'format': 'json'
        }

        data = self._get_json(self.WIKI_API, params=params)
        if not data:
            return info

        wikitext = data.get('parse', {}).get('wikitext', {}).get('*', '')
        if not wikitext:
            return info

        # Parse infobox fields
        infobox_match = re.search(r'\{\{Infobox[^}]+\}\}', wikitext, re.DOTALL | re.IGNORECASE)
        if not infobox_match:
            # Try alternative infobox patterns
            infobox_match = re.search(r'\{\{(?:Infobox|Basketball biography)[^}]*\}\}',
                                      wikitext, re.DOTALL | re.IGNORECASE)

        if infobox_match:
            infobox = infobox_match.group(0)

            # Extract birth_place
            birth_match = re.search(r'\|\s*birth_place\s*=\s*([^\n|]+)', infobox)
            if birth_match:
                info['birth_place'] = self._clean_wikitext(birth_match.group(1))

            # Extract high_school
            hs_match = re.search(r'\|\s*(?:high_?school|hs)\s*=\s*([^\n|]+)', infobox)
            if hs_match:
                info['high_school'] = self._clean_wikitext(hs_match.group(1))

            # Extract college
            college_match = re.search(r'\|\s*college\s*=\s*([^\n|]+)', infobox)
            if college_match:
                info['college'] = self._clean_wikitext(college_match.group(1))

            # Extract image
            image_match = re.search(r'\|\s*image\s*=\s*([^\n|]+)', infobox)
            if image_match:
                image_name = self._clean_wikitext(image_match.group(1))
                if image_name:
                    # Convert to image URL
                    info['image'] = self._get_image_url(image_name)

        return info

    def _clean_wikitext(self, text: str) -> str:
        """Clean wikitext markup from text."""
        if not text:
            return ''

        # Remove [[ ]] links, keeping the display text
        text = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', text)
        # Remove {{ }} templates
        text = re.sub(r'\{\{[^}]+\}\}', '', text)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove ref tags and content
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
        text = re.sub(r'<ref[^/>]*/>', '', text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _get_image_url(self, image_name: str) -> Optional[str]:
        """Convert image name to full URL."""
        if not image_name:
            return None

        # Query for image info
        params = {
            'action': 'query',
            'titles': f"File:{image_name}",
            'prop': 'imageinfo',
            'iiprop': 'url',
            'format': 'json'
        }

        data = self._get_json(self.WIKI_API, params=params)
        if not data:
            return None

        pages = data.get('query', {}).get('pages', {})
        for page_id, page_data in pages.items():
            if page_id != '-1':
                imageinfo = page_data.get('imageinfo', [])
                if imageinfo:
                    return imageinfo[0].get('url')

        return None

    def lookup_player(self, player_name: str) -> Optional[Dict]:
        """
        Complete lookup: search, get summary, parse infobox.

        Args:
            player_name: Player name to look up

        Returns:
            Dict with hometown, school info, and photo
        """
        result = {
            'hometown_city': None,
            'hometown_state': None,
            'high_school': None,
            'high_school_city': None,
            'high_school_state': None,
            'college': None,
            'photo_url': None,
            'wikipedia_url': None,
            'source': 'wikipedia',
            'lookup_successful': False
        }

        # Search for player
        title = self.search_player(player_name)
        if not title:
            return None

        # Get page summary for photo and URL
        summary = self.get_page_summary(title)
        if summary:
            result['wikipedia_url'] = summary.get('page_url')
            result['photo_url'] = summary.get('originalimage') or summary.get('thumbnail')

        # Get infobox data
        infobox = self.get_infobox_data(title)

        # Parse birth place
        if infobox.get('birth_place'):
            city, state = self._parse_location(infobox['birth_place'])
            result['hometown_city'] = city
            result['hometown_state'] = state

        # Parse high school
        if infobox.get('high_school'):
            hs_info = self._parse_school(infobox['high_school'])
            result['high_school'] = hs_info.get('name')
            result['high_school_city'] = hs_info.get('city')
            result['high_school_state'] = hs_info.get('state')

        # Parse college
        if infobox.get('college'):
            result['college'] = infobox['college']

        # Use infobox image if we don't have one
        if not result['photo_url'] and infobox.get('image'):
            result['photo_url'] = infobox['image']

        # Check if lookup was successful
        if result.get('hometown_state') or result.get('high_school'):
            result['lookup_successful'] = True

        return result

    def _parse_location(self, location_text: str) -> tuple:
        """
        Parse location text into city and state.

        Args:
            location_text: Location text from infobox

        Returns:
            Tuple of (city, state)
        """
        if not location_text:
            return (None, None)

        # Common patterns
        # "Chicago, Illinois, U.S." or "Brooklyn, New York"
        parts = [p.strip() for p in location_text.split(',')]

        if len(parts) >= 2:
            city = parts[0]

            # Check each part for a US state
            for part in parts[1:]:
                part = part.strip()

                # Check for state abbreviation
                if part.upper() in STATE_ABBREVIATIONS:
                    return (city, STATE_ABBREVIATIONS[part.upper()])

                # Check for full state name
                if part in US_STATES:
                    return (city, part)

                # Check if state is embedded (e.g., "New York, U.S.")
                for state in US_STATES:
                    if state.lower() in part.lower():
                        return (city, state)

        return (None, None)

    def _parse_school(self, school_text: str) -> Dict:
        """
        Parse school text.

        Args:
            school_text: School text from infobox

        Returns:
            Dict with name, city, state
        """
        result = {
            'name': None,
            'city': None,
            'state': None
        }

        if not school_text:
            return result

        # Pattern: "School Name (City, State)"
        match = re.search(r'([^(]+)\s*\(([^,]+),\s*([^)]+)\)', school_text)
        if match:
            result['name'] = match.group(1).strip()
            result['city'] = match.group(2).strip()
            state = match.group(3).strip()

            if state.upper() in STATE_ABBREVIATIONS:
                state = STATE_ABBREVIATIONS[state.upper()]
            if state in US_STATES:
                result['state'] = state
        else:
            # Just the school name
            result['name'] = school_text.strip()

        return result
