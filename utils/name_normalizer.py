"""
Name normalization utilities for consistent matching across sources.
"""

import re
from unidecode import unidecode
from typing import Optional


class NameNormalizer:
    """Utilities for normalizing player and team names."""

    @staticmethod
    def normalize(name: str) -> str:
        """
        Normalize a name for consistent matching.

        - Removes accents
        - Converts to lowercase
        - Removes special characters
        - Replaces spaces with underscores

        Args:
            name: Name to normalize

        Returns:
            Normalized name
        """
        if not name:
            return ''

        # Remove accents
        normalized = unidecode(name.lower().strip())
        # Remove special characters except spaces
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)
        # Replace spaces with underscores
        normalized = normalized.replace(' ', '_')

        return normalized

    @staticmethod
    def normalize_for_search(name: str) -> str:
        """
        Normalize name for search queries.

        Keeps spaces, removes accents and special characters.

        Args:
            name: Name to normalize

        Returns:
            Search-friendly name
        """
        if not name:
            return ''

        normalized = unidecode(name.strip())
        # Remove special characters but keep spaces
        normalized = re.sub(r'[^a-zA-Z0-9\s]', '', normalized)
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)

        return normalized

    @staticmethod
    def create_id(prefix: str, name: str) -> str:
        """
        Create a standardized ID from prefix and name.

        Args:
            prefix: ID prefix (e.g., 'EUROLEAGUE')
            name: Name to include in ID

        Returns:
            Formatted ID (e.g., 'EUROLEAGUE_john_smith')
        """
        normalized = NameNormalizer.normalize(name)
        return f"{prefix}_{normalized}"

    @staticmethod
    def split_name(full_name: str) -> tuple:
        """
        Split full name into first and last name.

        Args:
            full_name: Full player name

        Returns:
            Tuple of (first_name, last_name)
        """
        if not full_name:
            return ('', '')

        parts = full_name.strip().split()
        if len(parts) == 0:
            return ('', '')
        elif len(parts) == 1:
            return (parts[0], '')
        else:
            return (parts[0], ' '.join(parts[1:]))

    @staticmethod
    def create_slug(name: str) -> str:
        """
        Create URL slug from name.

        Args:
            name: Name to convert

        Returns:
            URL-friendly slug (e.g., 'john-smith')
        """
        if not name:
            return ''

        slug = NameNormalizer.normalize(name)
        return slug.replace('_', '-')

    @staticmethod
    def names_match(name1: str, name2: str, threshold: float = 0.8) -> bool:
        """
        Check if two names match approximately.

        Uses word overlap to determine match.

        Args:
            name1: First name
            name2: Second name
            threshold: Minimum overlap ratio (0-1)

        Returns:
            True if names match above threshold
        """
        if not name1 or not name2:
            return False

        words1 = set(NameNormalizer.normalize(name1).split('_'))
        words2 = set(NameNormalizer.normalize(name2).split('_'))

        if not words1 or not words2:
            return False

        intersection = words1 & words2
        min_len = min(len(words1), len(words2))

        overlap = len(intersection) / min_len if min_len > 0 else 0
        return overlap >= threshold

    @staticmethod
    def extract_initials(name: str) -> str:
        """
        Extract initials from name.

        Args:
            name: Full name

        Returns:
            Initials (e.g., 'JS' for 'John Smith')
        """
        if not name:
            return ''

        parts = name.strip().split()
        initials = ''.join(p[0].upper() for p in parts if p)
        return initials
