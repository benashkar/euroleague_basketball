"""
Date and timezone utilities for handling European basketball schedules.
"""

from datetime import datetime, date, time, timedelta
from typing import Optional, Union
import pytz
from dateutil import parser as date_parser


class DateUtils:
    """Utilities for date and timezone handling."""

    # Common timezones for European basketball
    MADRID_TZ = pytz.timezone('Europe/Madrid')
    UTC_TZ = pytz.UTC

    @staticmethod
    def parse_date(date_str: str) -> Optional[date]:
        """
        Parse various date string formats.

        Supports:
        - ISO format: 2024-01-15
        - European format: 15/01/2024, 15-01-2024
        - US format: 01/15/2024

        Args:
            date_str: Date string to parse

        Returns:
            date object or None
        """
        if not date_str:
            return None

        try:
            # Use dateutil for flexible parsing
            parsed = date_parser.parse(date_str, dayfirst=True)
            return parsed.date()
        except:
            pass

        # Try common formats manually
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%m-%d-%Y',
            '%m/%d/%Y',
            '%d.%m.%Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str[:10], fmt).date()
            except:
                continue

        return None

    @staticmethod
    def parse_time(time_str: str) -> Optional[time]:
        """
        Parse various time string formats.

        Supports:
        - 24-hour: 20:00, 20:00:00
        - 12-hour: 8:00 PM, 8:00pm

        Args:
            time_str: Time string to parse

        Returns:
            time object or None
        """
        if not time_str:
            return None

        try:
            parsed = date_parser.parse(time_str)
            return parsed.time()
        except:
            pass

        formats = [
            '%H:%M',
            '%H:%M:%S',
            '%I:%M %p',
            '%I:%M%p',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(time_str.strip(), fmt).time()
            except:
                continue

        return None

    @staticmethod
    def parse_datetime(datetime_str: str) -> Optional[datetime]:
        """
        Parse datetime string.

        Args:
            datetime_str: Datetime string (ISO format preferred)

        Returns:
            datetime object or None
        """
        if not datetime_str:
            return None

        try:
            return date_parser.parse(datetime_str)
        except:
            return None

    @staticmethod
    def combine_date_time(d: date, t: time, timezone: str = 'Europe/Madrid') -> datetime:
        """
        Combine date and time with timezone.

        Args:
            d: Date object
            t: Time object
            timezone: Timezone name

        Returns:
            Timezone-aware datetime
        """
        tz = pytz.timezone(timezone)
        dt = datetime.combine(d, t)
        return tz.localize(dt)

    @staticmethod
    def to_utc(dt: datetime, from_tz: str = 'Europe/Madrid') -> datetime:
        """
        Convert datetime to UTC.

        Args:
            dt: Datetime to convert
            from_tz: Source timezone

        Returns:
            UTC datetime
        """
        if dt.tzinfo is None:
            # Assume the given timezone
            tz = pytz.timezone(from_tz)
            dt = tz.localize(dt)

        return dt.astimezone(pytz.UTC)

    @staticmethod
    def to_timezone(dt: datetime, to_tz: str) -> datetime:
        """
        Convert datetime to specified timezone.

        Args:
            dt: Datetime to convert
            to_tz: Target timezone

        Returns:
            Localized datetime
        """
        tz = pytz.timezone(to_tz)
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(tz)

    @staticmethod
    def format_date(d: Union[date, datetime], fmt: str = '%Y-%m-%d') -> str:
        """
        Format date to string.

        Args:
            d: Date or datetime
            fmt: Output format

        Returns:
            Formatted date string
        """
        if d is None:
            return ''
        return d.strftime(fmt)

    @staticmethod
    def format_time(t: Union[time, datetime], fmt: str = '%H:%M') -> str:
        """
        Format time to string.

        Args:
            t: Time or datetime
            fmt: Output format

        Returns:
            Formatted time string
        """
        if t is None:
            return ''
        return t.strftime(fmt)

    @staticmethod
    def is_today(d: date) -> bool:
        """Check if date is today."""
        return d == date.today()

    @staticmethod
    def is_past(d: date) -> bool:
        """Check if date is in the past."""
        return d < date.today()

    @staticmethod
    def is_future(d: date) -> bool:
        """Check if date is in the future."""
        return d > date.today()

    @staticmethod
    def days_until(d: date) -> int:
        """
        Calculate days until a date.

        Args:
            d: Target date

        Returns:
            Number of days (negative if past)
        """
        return (d - date.today()).days

    @staticmethod
    def get_date_range(days_ahead: int = 14, days_back: int = 0) -> tuple:
        """
        Get date range from today.

        Args:
            days_ahead: Days into future
            days_back: Days into past

        Returns:
            Tuple of (start_date, end_date)
        """
        today = date.today()
        start = today - timedelta(days=days_back)
        end = today + timedelta(days=days_ahead)
        return (start, end)

    @staticmethod
    def format_game_datetime(game_date: date, game_time: time = None,
                            timezone: str = 'Europe/Madrid') -> str:
        """
        Format game date and time for display.

        Args:
            game_date: Game date
            game_time: Game time (optional)
            timezone: Timezone for display

        Returns:
            Formatted string (e.g., "Fri, Jan 15 at 20:00 CET")
        """
        if game_date is None:
            return 'TBD'

        day_str = game_date.strftime('%a, %b %d')

        if game_time:
            time_str = game_time.strftime('%H:%M')
            return f"{day_str} at {time_str} CET"

        return day_str
