"""
Orchestrates multi-source hometown lookup with priority order:
1. Basketball Reference (PRIMARY)
2. Wikipedia (SECONDARY)
3. Grokepedia (TERTIARY)
4. Flag for manual review

Caches results to avoid repeated lookups.
"""

from typing import Dict, Optional, List
from scrapers.basketball_ref_scraper import BasketballRefScraper
from scrapers.wikipedia_scraper import WikipediaScraper
from scrapers.grokepedia_scraper import GrokepediaScraper
from scrapers.base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class HometownLookupService:
    """Service to look up hometown and high school for American players."""

    def __init__(self, db=None):
        """
        Initialize hometown lookup service.

        Args:
            db: Database connector instance (optional for caching)
        """
        self.db = db
        self.logger = logging.getLogger(__name__)

        # Initialize scrapers in priority order
        self.scrapers = [
            ('basketball_reference', BasketballRefScraper()),
            ('wikipedia', WikipediaScraper()),
            ('grokepedia', GrokepediaScraper()),
        ]

    def lookup_player_hometown(self, player_name: str, force_refresh: bool = False) -> Dict:
        """
        Look up hometown and high school for a player.

        Tries sources in priority order, caches results.

        Args:
            player_name: Full player name
            force_refresh: If True, skip cache and re-lookup

        Returns:
            Dict with hometown, high school info and lookup status
        """
        # Normalize name for cache lookup
        normalized_name = BaseScraper.normalize_name(player_name)

        # Check cache first
        if not force_refresh and self.db:
            cached = self._get_cached_result(normalized_name)
            if cached and cached.get('lookup_successful'):
                self.logger.info(f"Cache hit for {player_name}")
                return cached

        # Try each source in priority order
        result = {
            'hometown_city': None,
            'hometown_state': None,
            'high_school': None,
            'high_school_city': None,
            'high_school_state': None,
            'college': None,
            'photo_url': None,
            'profile_url': None,
            'source': None,
            'lookup_successful': False,
            'needs_manual_review': False
        }

        for source_name, scraper in self.scrapers:
            try:
                self.logger.info(f"Trying {source_name} for {player_name}")
                source_result = scraper.lookup_player(player_name)

                if source_result:
                    # Merge results, preferring earlier sources
                    self._merge_results(result, source_result, source_name)

                    # Cache this source's result
                    if self.db:
                        self._cache_result(normalized_name, source_name, source_result)

                    # Check if we have minimum required data
                    if self._has_required_data(result):
                        result['lookup_successful'] = True
                        self.logger.info(f"Found data from {source_name}: {result.get('hometown_city')}, {result.get('hometown_state')}")
                        break

            except Exception as e:
                self.logger.error(f"Error with {source_name}: {e}")
                continue

        # If still missing required data, mark for manual review
        if not result['lookup_successful']:
            result['needs_manual_review'] = True
            self.logger.warning(f"Could not find complete data for {player_name}")

        return result

    def _has_required_data(self, result: Dict) -> bool:
        """
        Check if we have the minimum required fields.

        Requires at least hometown state or high school.
        """
        return bool(result.get('hometown_state') or result.get('high_school'))

    def _merge_results(self, target: Dict, source: Dict, source_name: str):
        """
        Merge source data into target, not overwriting existing values.

        Earlier sources take priority.
        """
        fields_to_merge = [
            'hometown_city', 'hometown_state',
            'high_school', 'high_school_city', 'high_school_state',
            'college', 'photo_url', 'profile_url'
        ]

        for key in fields_to_merge:
            if not target.get(key) and source.get(key):
                target[key] = source[key]

        # Set source if not already set
        if not target.get('source') and source.get('lookup_successful'):
            target['source'] = source_name

    def _get_cached_result(self, normalized_name: str) -> Optional[Dict]:
        """
        Retrieve cached lookup result from database.

        Args:
            normalized_name: Normalized player name

        Returns:
            Cached result dict or None
        """
        if not self.db:
            return None

        try:
            cached = self.db.get_hometown_cache(normalized_name)
            if cached:
                return {
                    'hometown_city': cached.get('hometown_city'),
                    'hometown_state': cached.get('hometown_state'),
                    'high_school': cached.get('high_school'),
                    'high_school_city': cached.get('high_school_city'),
                    'high_school_state': cached.get('high_school_state'),
                    'college': cached.get('college'),
                    'photo_url': cached.get('photo_url'),
                    'profile_url': cached.get('profile_url'),
                    'source': cached.get('lookup_source'),
                    'lookup_successful': cached.get('lookup_successful', False)
                }
        except Exception as e:
            self.logger.error(f"Error retrieving cache: {e}")

        return None

    def _cache_result(self, normalized_name: str, source: str, result: Dict):
        """
        Store lookup result in cache table.

        Args:
            normalized_name: Normalized player name
            source: Source name (basketball_reference, wikipedia, etc.)
            result: Result dict to cache
        """
        if not self.db:
            return

        try:
            self.db.cache_hometown_lookup(normalized_name, source, result)
        except Exception as e:
            self.logger.error(f"Error caching result: {e}")

    def process_all_american_players(self) -> Dict:
        """
        Process all American players that need hometown lookup.

        Returns:
            Summary dict with counts
        """
        if not self.db:
            self.logger.error("Database connection required for batch processing")
            return {'error': 'No database connection'}

        summary = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'needs_review': 0
        }

        # Get players needing lookup
        players = self.db.get_players_needing_hometown_lookup()
        summary['total'] = len(players)
        self.logger.info(f"Found {len(players)} players needing hometown lookup")

        for player in players:
            player_id = player.get('player_id')
            player_name = player.get('full_name')

            self.logger.info(f"Processing: {player_name}")

            result = self.lookup_player_hometown(player_name)

            if result.get('lookup_successful'):
                # Update player record
                self.db.update_player_hometown(
                    player_id,
                    hometown_city=result.get('hometown_city'),
                    hometown_state=result.get('hometown_state'),
                    high_school=result.get('high_school'),
                    high_school_city=result.get('high_school_city'),
                    high_school_state=result.get('high_school_state'),
                    college=result.get('college'),
                    hometown_source=result.get('source')
                )
                summary['success'] += 1
                self.logger.info(f"  Found: {result.get('hometown_city')}, {result.get('hometown_state')}")
            else:
                # Mark for manual review
                self.db.mark_player_for_review(player_id)
                summary['needs_review'] += 1
                summary['failed'] += 1
                self.logger.warning(f"  Could not find hometown for {player_name}")

        self.logger.info(f"Hometown processing complete: {summary}")
        return summary

    def lookup_batch(self, player_names: List[str]) -> List[Dict]:
        """
        Look up hometown for multiple players.

        Args:
            player_names: List of player names

        Returns:
            List of result dicts
        """
        results = []
        for name in player_names:
            result = self.lookup_player_hometown(name)
            result['player_name'] = name
            results.append(result)
        return results
