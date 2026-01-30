"""
Handles player photo URL processing.

Goals:
- Find best available photo for each player
- Prefer 16:9 aspect ratio images
- Track multiple photo sources
- Validate URLs are accessible
"""

from typing import Dict, List, Optional, Tuple
import requests
from io import BytesIO
import logging

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL not available. Photo dimension checking disabled.")


class PhotoProcessor:
    """Service to process and categorize player photos."""

    PREFERRED_ASPECT_RATIO = 16 / 9  # 1.778
    TOLERANCE = 0.1  # Allow 10% variance from ideal ratio

    def __init__(self):
        """Initialize photo processor."""
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_image_dimensions(self, url: str) -> Optional[Tuple[int, int]]:
        """
        Fetch image and return (width, height).

        Args:
            url: Image URL

        Returns:
            Tuple of (width, height) or None if image can't be fetched
        """
        if not PIL_AVAILABLE:
            return None

        try:
            response = self.session.get(url, timeout=10, stream=True)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            return img.size
        except Exception as e:
            self.logger.warning(f"Could not fetch image {url}: {e}")
            return None

    def validate_url(self, url: str) -> bool:
        """
        Check if URL is accessible.

        Args:
            url: URL to validate

        Returns:
            True if URL returns 200 OK
        """
        try:
            response = self.session.head(url, timeout=5, allow_redirects=True)
            return response.status_code == 200
        except:
            return False

    def calculate_aspect_ratio(self, width: int, height: int) -> float:
        """Calculate aspect ratio as width/height."""
        if height == 0:
            return 0
        return width / height

    def is_16x9(self, width: int, height: int) -> bool:
        """Check if dimensions are approximately 16:9."""
        ratio = self.calculate_aspect_ratio(width, height)
        return abs(ratio - self.PREFERRED_ASPECT_RATIO) <= self.TOLERANCE

    def is_square(self, width: int, height: int) -> bool:
        """Check if dimensions are approximately square (1:1)."""
        ratio = self.calculate_aspect_ratio(width, height)
        return abs(ratio - 1.0) <= self.TOLERANCE

    def is_4x3(self, width: int, height: int) -> bool:
        """Check if dimensions are approximately 4:3."""
        ratio = self.calculate_aspect_ratio(width, height)
        return abs(ratio - (4/3)) <= self.TOLERANCE

    def get_aspect_ratio_label(self, width: int, height: int) -> str:
        """
        Get human-readable aspect ratio label.

        Returns:
            '16:9', '4:3', '1:1', or 'other'
        """
        if self.is_16x9(width, height):
            return '16:9'
        elif self.is_square(width, height):
            return '1:1'
        elif self.is_4x3(width, height):
            return '4:3'
        else:
            return 'other'

    def categorize_photo(self, url: str) -> Dict:
        """
        Analyze a photo URL and return metadata.

        Args:
            url: Photo URL

        Returns:
            Dict with URL, dimensions, aspect ratio info
        """
        result = {
            'url': url,
            'width': None,
            'height': None,
            'aspect_ratio': None,
            'aspect_ratio_label': 'unknown',
            'is_16x9': False,
            'is_square': False,
            'is_4x3': False,
            'is_valid': False
        }

        # First validate URL is accessible
        if not self.validate_url(url):
            return result

        result['is_valid'] = True

        # Get dimensions if PIL is available
        dimensions = self.get_image_dimensions(url)
        if dimensions:
            width, height = dimensions
            result['width'] = width
            result['height'] = height
            result['aspect_ratio'] = self.calculate_aspect_ratio(width, height)
            result['is_16x9'] = self.is_16x9(width, height)
            result['is_square'] = self.is_square(width, height)
            result['is_4x3'] = self.is_4x3(width, height)
            result['aspect_ratio_label'] = self.get_aspect_ratio_label(width, height)

        return result

    def select_best_photo(self, photos: List[Dict]) -> Optional[Dict]:
        """
        From a list of photo metadata dicts, select the best one.

        Priority:
        1. Valid 16:9 image with largest dimensions
        2. Valid 4:3 image with largest dimensions
        3. Any valid image with largest dimensions

        Args:
            photos: List of photo metadata dicts

        Returns:
            Best photo dict or None
        """
        if not photos:
            return None

        valid_photos = [p for p in photos if p.get('is_valid')]
        if not valid_photos:
            return None

        # Sort by preference
        def photo_score(p):
            score = 0
            if p.get('is_16x9'):
                score += 1000000
            elif p.get('is_4x3'):
                score += 500000
            elif p.get('is_square'):
                score += 250000
            # Add size bonus
            width = p.get('width') or 0
            height = p.get('height') or 0
            score += (width * height) / 1000
            return score

        valid_photos.sort(key=photo_score, reverse=True)
        return valid_photos[0]

    def process_player_photos(self, player_id: str, photo_urls: List[str], db=None) -> Dict:
        """
        Process all photos for a player.

        Args:
            player_id: Player identifier
            photo_urls: List of photo URLs to process
            db: Database connector (optional)

        Returns:
            Summary dict with selected photos
        """
        results = {
            'player_id': player_id,
            'primary_photo': None,
            'photo_16x9': None,
            'photo_square': None,
            'photos_processed': 0,
            'photos_valid': 0
        }

        analyzed_photos = []
        for url in photo_urls:
            if not url:
                continue

            metadata = self.categorize_photo(url)
            results['photos_processed'] += 1

            if metadata['is_valid']:
                analyzed_photos.append(metadata)
                results['photos_valid'] += 1

                # Track specific types
                if metadata['is_16x9'] and not results['photo_16x9']:
                    results['photo_16x9'] = url
                if metadata['is_square'] and not results['photo_square']:
                    results['photo_square'] = url

        # Select best as primary
        best = self.select_best_photo(analyzed_photos)
        if best:
            results['primary_photo'] = best['url']

        # Save to database if provided
        if db and analyzed_photos:
            self._save_photos_to_db(player_id, analyzed_photos, db)

        return results

    def _save_photos_to_db(self, player_id: str, photos: List[Dict], db):
        """
        Save photo metadata to database.

        Args:
            player_id: Player identifier
            photos: List of photo metadata dicts
            db: Database connector
        """
        for i, photo in enumerate(photos):
            try:
                query = """
                    INSERT INTO player_photos (
                        player_id, photo_url, photo_source,
                        width, height, aspect_ratio, aspect_ratio_decimal,
                        is_primary, is_16x9, is_square, url_valid
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        width = VALUES(width),
                        height = VALUES(height),
                        url_valid = VALUES(url_valid),
                        last_validated = CURRENT_TIMESTAMP
                """
                params = (
                    player_id,
                    photo['url'],
                    photo.get('source', 'unknown'),
                    photo.get('width'),
                    photo.get('height'),
                    photo.get('aspect_ratio_label'),
                    photo.get('aspect_ratio'),
                    i == 0,  # First photo is primary
                    photo.get('is_16x9', False),
                    photo.get('is_square', False),
                    photo.get('is_valid', False)
                )
                db.execute(query, params)
            except Exception as e:
                self.logger.error(f"Error saving photo for {player_id}: {e}")

    def find_best_photos_for_player(self, player_id: str, db) -> Dict:
        """
        Find best available photos for a player from database.

        Args:
            player_id: Player identifier
            db: Database connector

        Returns:
            Dict with best photo URLs by type
        """
        result = {
            'primary': None,
            'photo_16x9': None,
            'photo_square': None
        }

        try:
            # Get 16:9 photo
            query = """
                SELECT photo_url FROM player_photos
                WHERE player_id = %s AND is_16x9 = TRUE AND url_valid = TRUE
                ORDER BY width DESC LIMIT 1
            """
            photo_16x9 = db.fetch_one(query, (player_id,))
            if photo_16x9:
                result['photo_16x9'] = photo_16x9['photo_url']

            # Get square photo
            query = """
                SELECT photo_url FROM player_photos
                WHERE player_id = %s AND is_square = TRUE AND url_valid = TRUE
                ORDER BY width DESC LIMIT 1
            """
            photo_square = db.fetch_one(query, (player_id,))
            if photo_square:
                result['photo_square'] = photo_square['photo_url']

            # Get primary photo
            query = """
                SELECT photo_url FROM player_photos
                WHERE player_id = %s AND is_primary = TRUE AND url_valid = TRUE
                LIMIT 1
            """
            primary = db.fetch_one(query, (player_id,))
            if primary:
                result['primary'] = primary['photo_url']
            elif result['photo_16x9']:
                result['primary'] = result['photo_16x9']
            elif result['photo_square']:
                result['primary'] = result['photo_square']

        except Exception as e:
            self.logger.error(f"Error finding photos for {player_id}: {e}")

        return result
