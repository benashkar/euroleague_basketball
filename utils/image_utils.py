"""
Image and photo URL utilities.
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse, urljoin


class ImageUtils:
    """Utilities for image URL handling."""

    # Common image extensions
    IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']

    @staticmethod
    def is_valid_image_url(url: str) -> bool:
        """
        Check if URL appears to be a valid image URL.

        Args:
            url: URL to check

        Returns:
            True if URL looks like an image
        """
        if not url:
            return False

        # Check for common image extensions
        url_lower = url.lower()
        for ext in ImageUtils.IMAGE_EXTENSIONS:
            if ext in url_lower:
                return True

        # Check for common image URL patterns
        image_patterns = [
            r'/images?/',
            r'/photos?/',
            r'/media/',
            r'/assets/',
            r'/uploads/',
            r'\.cloudinary\.com',
            r'\.imgix\.net',
        ]

        for pattern in image_patterns:
            if re.search(pattern, url_lower):
                return True

        return False

    @staticmethod
    def normalize_url(url: str, base_url: str = None) -> str:
        """
        Normalize image URL to absolute path.

        Args:
            url: Image URL (may be relative)
            base_url: Base URL for relative paths

        Returns:
            Absolute URL
        """
        if not url:
            return ''

        url = url.strip()

        # Already absolute
        if url.startswith(('http://', 'https://')):
            return url

        # Protocol-relative
        if url.startswith('//'):
            return 'https:' + url

        # Relative path
        if base_url:
            return urljoin(base_url, url)

        return url

    @staticmethod
    def get_image_filename(url: str) -> str:
        """
        Extract filename from image URL.

        Args:
            url: Image URL

        Returns:
            Filename
        """
        if not url:
            return ''

        parsed = urlparse(url)
        path = parsed.path

        # Get last part of path
        parts = path.split('/')
        filename = parts[-1] if parts else ''

        # Remove query string if attached
        filename = filename.split('?')[0]

        return filename

    @staticmethod
    def extract_dimensions_from_url(url: str) -> Optional[Tuple[int, int]]:
        """
        Try to extract image dimensions from URL parameters.

        Some CDNs include dimensions in URL.

        Args:
            url: Image URL

        Returns:
            Tuple of (width, height) or None
        """
        if not url:
            return None

        # Common patterns: w=640, width=640, h=360, height=360
        width_match = re.search(r'[?&]w(?:idth)?=(\d+)', url)
        height_match = re.search(r'[?&]h(?:eight)?=(\d+)', url)

        if width_match and height_match:
            return (int(width_match.group(1)), int(height_match.group(1)))

        # Pattern: 640x360
        size_match = re.search(r'(\d{3,4})x(\d{3,4})', url)
        if size_match:
            return (int(size_match.group(1)), int(size_match.group(2)))

        return None

    @staticmethod
    def get_higher_res_url(url: str) -> str:
        """
        Try to get higher resolution version of image URL.

        Modifies common CDN URL parameters for higher resolution.

        Args:
            url: Original image URL

        Returns:
            Modified URL (or original if no pattern found)
        """
        if not url:
            return url

        # Remove size restrictions
        patterns_to_remove = [
            (r'/\d+x\d+/', '/'),  # Remove /640x360/
            (r'[?&]w=\d+', ''),   # Remove width param
            (r'[?&]h=\d+', ''),   # Remove height param
            (r'_\d+x\d+\.', '.'), # Remove _640x360.jpg
            (r'-\d+x\d+\.', '.'), # Remove -640x360.jpg
        ]

        result = url
        for pattern, replacement in patterns_to_remove:
            result = re.sub(pattern, replacement, result)

        return result

    @staticmethod
    def get_thumbnail_url(url: str, width: int = 200) -> str:
        """
        Try to get thumbnail version of image URL.

        Args:
            url: Original image URL
            width: Desired thumbnail width

        Returns:
            Thumbnail URL (or original if no pattern found)
        """
        if not url:
            return url

        # Try adding common thumbnail parameters
        if '?' in url:
            return f"{url}&w={width}"
        else:
            return f"{url}?w={width}"

    @staticmethod
    def calculate_aspect_ratio(width: int, height: int) -> float:
        """
        Calculate aspect ratio.

        Args:
            width: Image width
            height: Image height

        Returns:
            Aspect ratio (width/height)
        """
        if height == 0:
            return 0
        return width / height

    @staticmethod
    def get_aspect_ratio_label(width: int, height: int) -> str:
        """
        Get human-readable aspect ratio label.

        Args:
            width: Image width
            height: Image height

        Returns:
            Aspect ratio label ('16:9', '4:3', '1:1', or 'other')
        """
        ratio = ImageUtils.calculate_aspect_ratio(width, height)

        # Define tolerances
        ratios = {
            '16:9': 16/9,
            '4:3': 4/3,
            '3:2': 3/2,
            '1:1': 1.0,
            '9:16': 9/16,  # Portrait
            '3:4': 3/4,    # Portrait
        }

        for label, target in ratios.items():
            if abs(ratio - target) <= 0.1:
                return label

        return 'other'
