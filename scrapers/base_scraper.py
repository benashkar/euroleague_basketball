"""
=============================================================================
BASE SCRAPER MODULE
=============================================================================

This module provides the foundation for all web scrapers in our application.
Think of it as a "template" or "blueprint" that other scrapers inherit from.

WHY DO WE NEED THIS?
--------------------
When scraping multiple websites (EuroLeague, Basketball Reference, Wikipedia),
we need to do similar things on each site:
- Make HTTP requests
- Wait between requests (rate limiting) to avoid getting blocked
- Parse HTML into usable data
- Handle errors gracefully
- Normalize names for consistent database storage

Instead of writing this code multiple times, we write it ONCE here,
and all our other scrapers inherit these capabilities.

WHAT IS INHERITANCE?
--------------------
In Python, a class can "inherit" from another class. This means:
- The child class gets all the methods (functions) of the parent class
- The child class can add its own methods
- The child class can override parent methods if needed

Example:
    class EuroLeagueScraper(BaseScraper):  # Inherits from BaseScraper
        # EuroLeagueScraper automatically has all BaseScraper methods!
        pass

KEY CONCEPTS IN THIS FILE:
--------------------------
1. Rate Limiting: Waiting between requests to not overload websites
2. Retry Logic: Automatically retrying failed requests
3. Session Management: Reusing HTTP connections for efficiency
4. HTML Parsing: Converting raw HTML into searchable objects
5. Name Normalization: Making names consistent for database matching

DEPENDENCIES:
-------------
- requests: For making HTTP requests (pip install requests)
- beautifulsoup4: For parsing HTML (pip install beautifulsoup4)
- lxml: Fast HTML parser (pip install lxml)
- unidecode: For removing accents from names (pip install unidecode)
"""

# =============================================================================
# IMPORTS
# =============================================================================

# ABC = Abstract Base Class - allows us to create "template" classes
# abstractmethod = marks methods that MUST be implemented by child classes
from abc import ABC, abstractmethod

# Type hints - these help document what types of data functions expect/return
# List = a list like [1, 2, 3]
# Dict = a dictionary like {'name': 'John', 'age': 30}
# Optional = the value could be the type OR None
# Any = any type of data
from typing import List, Dict, Optional, Any

# requests is the most popular library for making HTTP requests in Python
# It handles all the complexity of HTTP (headers, cookies, redirects, etc.)
import requests

# HTTPAdapter lets us customize how requests handles connections
from requests.adapters import HTTPAdapter

# Retry configures automatic retry behavior for failed requests
from urllib3.util.retry import Retry

# time module for sleeping/waiting between requests
import time

# logging lets us output debug/info/error messages
# Much better than print() because you can control verbosity levels
import logging

# BeautifulSoup is THE library for parsing HTML in Python
# It lets you search HTML like: soup.find('div', class_='player-name')
from bs4 import BeautifulSoup

# unidecode converts Unicode characters to ASCII
# Example: "José García" becomes "Jose Garcia"
# This is crucial for matching names across different data sources
from unidecode import unidecode

# re = regular expressions for pattern matching in strings
import re


# =============================================================================
# BASE SCRAPER CLASS
# =============================================================================

class BaseScraper(ABC):
    """
    Abstract base class that all scrapers inherit from.

    WHAT IS AN ABSTRACT CLASS?
    --------------------------
    An abstract class is a class that:
    1. Cannot be instantiated directly (you can't do BaseScraper())
    2. Serves as a template for other classes
    3. Can have abstract methods that child classes MUST implement

    WHY USE ABC (Abstract Base Class)?
    ----------------------------------
    It enforces that all our scrapers follow the same pattern.
    If a child class forgets to implement a required method,
    Python will raise an error immediately.

    ATTRIBUTES:
    -----------
    config : dict
        Configuration settings passed in during initialization
    base_url : str
        The base URL of the website being scraped
    rate_limit : float
        Seconds to wait between requests
    last_request_time : float
        Timestamp of the last request (for rate limiting)
    session : requests.Session
        Reusable HTTP session for making requests
    logger : logging.Logger
        Logger instance for this scraper

    EXAMPLE USAGE:
    --------------
    # You would create a child class, not use BaseScraper directly:

    class MyScraper(BaseScraper):
        def __init__(self):
            super().__init__({'base_url': 'https://example.com'})

        def scrape_data(self):
            soup = self._get_soup('https://example.com/page')
            # ... process the soup ...
    """

    def __init__(self, config: dict):
        """
        Initialize the base scraper with configuration settings.

        This is called automatically when you create a new scraper instance.
        Child classes should call super().__init__(config) to run this.

        WHAT HAPPENS HERE:
        ------------------
        1. Store the configuration
        2. Set up rate limiting parameters
        3. Create an HTTP session with retry logic
        4. Set up request headers to look like a real browser
        5. Create a logger for this scraper

        Parameters:
        -----------
        config : dict
            Configuration dictionary. Expected keys:
            - 'base_url': The base URL of the site to scrape
            - 'rate_limit_seconds': How long to wait between requests
            - 'user_agent': Custom user agent string (optional)

        Example:
        --------
        config = {
            'base_url': 'https://www.euroleaguebasketball.net',
            'rate_limit_seconds': 2,
        }
        scraper = MyScraper(config)
        """
        # Store the entire config dict for later use
        self.config = config

        # Get the base URL, defaulting to empty string if not provided
        # The base_url is the root of the website (e.g., https://example.com)
        self.base_url = config.get('base_url', '')

        # Rate limit: how many seconds to wait between requests
        # This is CRUCIAL - websites will block you if you request too fast!
        # Default is 2 seconds, which is respectful to most websites
        self.rate_limit = config.get('rate_limit_seconds', 2)

        # Track when we made our last request (for rate limiting)
        # Starts at 0 so the first request happens immediately
        self.last_request_time = 0

        # =====================================================================
        # SET UP HTTP SESSION WITH RETRY LOGIC
        # =====================================================================
        #
        # A Session object persists certain parameters across requests:
        # - Cookies are automatically handled
        # - TCP connections are reused (faster!)
        # - Headers persist across requests
        #
        # This is more efficient than making individual requests

        self.session = requests.Session()

        # Configure automatic retry behavior
        # This handles temporary failures gracefully
        retry_strategy = Retry(
            total=3,  # Maximum number of retry attempts
            backoff_factor=1,  # Wait 1, 2, 4 seconds between retries (exponential backoff)
            status_forcelist=[429, 500, 502, 503, 504]  # HTTP status codes to retry on
            # 429 = Too Many Requests (rate limited)
            # 500 = Internal Server Error
            # 502 = Bad Gateway
            # 503 = Service Unavailable
            # 504 = Gateway Timeout
        )

        # Create an adapter with our retry strategy
        # An adapter lets us customize how the session handles requests
        adapter = HTTPAdapter(max_retries=retry_strategy)

        # Mount the adapter for both HTTP and HTTPS URLs
        # This means ALL requests will use our retry logic
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # =====================================================================
        # SET UP REQUEST HEADERS
        # =====================================================================
        #
        # Headers tell the website about our "browser"
        # Without proper headers, many sites will block us!
        #
        # These headers make our requests look like they're from a real browser

        self.session.headers.update({
            # User-Agent identifies the browser/application making the request
            # We use a realistic browser user agent to avoid being blocked
            'User-Agent': config.get(
                'user_agent',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            # Accept tells the server what content types we can handle
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            # Accept-Language specifies preferred languages
            'Accept-Language': 'en-US,en;q=0.5',
            # Connection: keep-alive tells the server to keep the TCP connection open
            # This makes subsequent requests faster
            'Connection': 'keep-alive',
        })

        # =====================================================================
        # SET UP LOGGING
        # =====================================================================
        #
        # Logging is essential for debugging scrapers!
        # It lets us track what the scraper is doing without using print()
        #
        # Benefits over print():
        # - Can filter by severity (DEBUG, INFO, WARNING, ERROR)
        # - Automatically includes timestamps
        # - Can write to files, not just console
        # - Can be turned off in production

        # Get a logger named after this class (e.g., "EuroLeagueScraper")
        # This helps identify which scraper is producing each log message
        self.logger = logging.getLogger(self.__class__.__name__)

    def _rate_limit_wait(self):
        """
        Enforce rate limiting between requests.

        WHY RATE LIMITING?
        ------------------
        Websites don't like being hammered with requests!
        If you request too fast:
        1. You might get temporarily blocked (HTTP 429)
        2. You might get permanently banned
        3. You could crash the website (unethical!)

        HOW IT WORKS:
        -------------
        1. Calculate how long since our last request
        2. If it's been less than our rate limit, sleep for the difference
        3. Record the current time for the next rate limit check

        This method is called BEFORE every request.

        Example:
        --------
        If rate_limit = 2 seconds:
        - Request 1 at t=0: No wait needed, request goes through
        - Request 2 at t=0.5: Wait 1.5 seconds, then request
        - Request 3 at t=3.0: No wait needed (already 2+ seconds since request 2)
        """
        # Calculate how many seconds have passed since our last request
        elapsed = time.time() - self.last_request_time

        # If we haven't waited long enough, sleep for the remaining time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            self.logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        # Update the last request time to NOW
        self.last_request_time = time.time()

    def _get(self, url: str, params: dict = None, **kwargs) -> Optional[requests.Response]:
        """
        Make a rate-limited GET request.

        This is a wrapper around requests.get() that adds:
        1. Rate limiting (waits between requests)
        2. Error handling (catches exceptions)
        3. Logging (records what's happening)

        Parameters:
        -----------
        url : str
            The URL to fetch
        params : dict, optional
            Query parameters to add to the URL
            Example: {'search': 'john'} becomes ?search=john
        **kwargs : dict
            Additional arguments passed to requests.get()
            Common ones: timeout, headers, allow_redirects

        Returns:
        --------
        requests.Response or None
            The response object if successful, None if the request failed

        Example:
        --------
        # Simple GET request
        response = self._get('https://example.com/page')

        # GET request with parameters
        response = self._get('https://example.com/search', params={'q': 'basketball'})
        # This fetches: https://example.com/search?q=basketball

        # GET request with custom timeout
        response = self._get('https://example.com/slow-page', timeout=60)
        """
        # Wait if necessary to respect rate limits
        self._rate_limit_wait()

        try:
            # Get timeout from kwargs, defaulting to 30 seconds
            # We pop() it so it's not passed twice to session.get()
            timeout = kwargs.pop('timeout', 30)

            # Make the actual HTTP request
            response = self.session.get(url, params=params, timeout=timeout, **kwargs)

            # raise_for_status() raises an exception for HTTP errors (4xx, 5xx)
            # This lets us catch errors in the except block below
            response.raise_for_status()

            # Log successful requests at DEBUG level
            self.logger.debug(f"GET {url} -> {response.status_code}")

            return response

        except requests.RequestException as e:
            # RequestException is the base class for all requests errors
            # This catches: connection errors, timeouts, HTTP errors, etc.
            self.logger.error(f"Request failed: {url} - {e}")
            return None

    def _post(self, url: str, data: dict = None, json_data: dict = None,
              **kwargs) -> Optional[requests.Response]:
        """
        Make a rate-limited POST request.

        POST requests are used when you need to send data TO the server.
        Common uses:
        - Submitting forms
        - Sending JSON data to APIs
        - Login/authentication

        Parameters:
        -----------
        url : str
            The URL to post to
        data : dict, optional
            Form data to send (Content-Type: application/x-www-form-urlencoded)
        json_data : dict, optional
            JSON data to send (Content-Type: application/json)
        **kwargs : dict
            Additional arguments passed to requests.post()

        Returns:
        --------
        requests.Response or None
            The response object if successful, None if the request failed

        Example:
        --------
        # POST form data
        response = self._post('https://example.com/login', data={
            'username': 'user',
            'password': 'pass'
        })

        # POST JSON data (common for APIs)
        response = self._post('https://api.example.com/data', json_data={
            'query': 'search term'
        })
        """
        # Wait if necessary to respect rate limits
        self._rate_limit_wait()

        try:
            timeout = kwargs.pop('timeout', 30)

            # Make the POST request
            response = self.session.post(
                url, data=data, json=json_data, timeout=timeout, **kwargs
            )
            response.raise_for_status()

            self.logger.debug(f"POST {url} -> {response.status_code}")
            return response

        except requests.RequestException as e:
            self.logger.error(f"POST request failed: {url} - {e}")
            return None

    def _get_json(self, url: str, params: dict = None) -> Optional[dict]:
        """
        Fetch URL and parse the response as JSON.

        Many websites have APIs that return JSON data instead of HTML.
        JSON is easier to work with than HTML - it's already structured data!

        Parameters:
        -----------
        url : str
            The URL to fetch
        params : dict, optional
            Query parameters

        Returns:
        --------
        dict or None
            Parsed JSON as a Python dictionary, or None if request/parsing failed

        Example:
        --------
        # Fetch JSON from an API
        data = self._get_json('https://api.example.com/players')
        if data:
            for player in data['players']:
                print(player['name'])
        """
        # Make the GET request
        response = self._get(url, params=params)

        if response:
            try:
                # Parse the response body as JSON
                # This converts JSON string to Python dict/list
                return response.json()
            except ValueError as e:
                # ValueError is raised if the response isn't valid JSON
                self.logger.error(f"JSON parse error for {url}: {e}")

        return None

    def _parse_html(self, response: requests.Response) -> Optional[BeautifulSoup]:
        """
        Parse an HTTP response into a BeautifulSoup object.

        WHAT IS BEAUTIFULSOUP?
        ----------------------
        BeautifulSoup is a library that parses HTML/XML and lets you
        search through it easily. It turns this:

            <html><div class="player">John Smith</div></html>

        Into something you can search:

            soup.find('div', class_='player').text  # Returns: "John Smith"

        Parameters:
        -----------
        response : requests.Response
            The HTTP response to parse

        Returns:
        --------
        BeautifulSoup or None
            Parsed HTML, or None if response was None

        Example:
        --------
        response = self._get('https://example.com')
        soup = self._parse_html(response)
        if soup:
            title = soup.find('title').text
        """
        if response:
            # 'lxml' is the parser we're using - it's fast and lenient
            # Other options: 'html.parser' (built-in), 'html5lib' (most lenient)
            return BeautifulSoup(response.text, 'lxml')
        return None

    def _get_soup(self, url: str, params: dict = None) -> Optional[BeautifulSoup]:
        """
        Convenience method: Fetch URL and parse as HTML in one step.

        This combines _get() and _parse_html() for common use case.

        Parameters:
        -----------
        url : str
            The URL to fetch
        params : dict, optional
            Query parameters

        Returns:
        --------
        BeautifulSoup or None
            Parsed HTML, or None if request failed

        Example:
        --------
        # Instead of:
        response = self._get(url)
        soup = self._parse_html(response)

        # You can just do:
        soup = self._get_soup(url)
        if soup:
            players = soup.find_all('div', class_='player')
        """
        response = self._get(url, params=params)
        return self._parse_html(response)

    # =========================================================================
    # STATIC METHODS FOR NAME NORMALIZATION
    # =========================================================================
    #
    # These methods are "static" - they don't use 'self' and can be called
    # without creating an instance: BaseScraper.normalize_name("John Smith")
    #
    # WHY NORMALIZE NAMES?
    # --------------------
    # The same player might appear differently in different sources:
    # - EuroLeague: "José García"
    # - Basketball Ref: "Jose Garcia"
    # - Wikipedia: "Jose García"
    #
    # To match them in our database, we need a consistent format:
    # - All lowercase
    # - No accents
    # - Spaces replaced with underscores
    #
    # Result: "jose_garcia" matches from all sources!

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize a name for consistent matching across data sources.

        WHAT THIS DOES:
        ---------------
        1. Converts to lowercase
        2. Removes accents (José → Jose)
        3. Removes special characters
        4. Replaces spaces with underscores

        Parameters:
        -----------
        name : str
            The name to normalize

        Returns:
        --------
        str
            Normalized name

        Examples:
        ---------
        >>> BaseScraper.normalize_name("José García")
        'jose_garcia'

        >>> BaseScraper.normalize_name("LeBron James Jr.")
        'lebron_james_jr'

        >>> BaseScraper.normalize_name("  John   Smith  ")
        'john_smith'
        """
        if not name:
            return ''

        # Step 1: Remove accents using unidecode
        # unidecode converts Unicode to closest ASCII representation
        # "José" → "Jose", "Müller" → "Muller"
        normalized = unidecode(name.lower().strip())

        # Step 2: Remove all characters that aren't letters, numbers, or spaces
        # The regex [^a-z0-9\s] means "anything NOT a-z, 0-9, or whitespace"
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)

        # Step 3: Replace all whitespace (including multiple spaces) with single underscore
        # \s+ means "one or more whitespace characters"
        normalized = re.sub(r'\s+', '_', normalized)

        return normalized

    @staticmethod
    def normalize_team_id(league_id: str, team_name: str) -> str:
        """
        Create a consistent team ID for database storage.

        We need consistent IDs because team names vary:
        - "Real Madrid" vs "Real Madrid Baloncesto" vs "Real Madrid CF"

        By normalizing, they all become: EUROLEAGUE_real_madrid

        Parameters:
        -----------
        league_id : str
            League identifier (e.g., 'EUROLEAGUE')
        team_name : str
            Team name to normalize

        Returns:
        --------
        str
            Normalized team ID

        Example:
        --------
        >>> BaseScraper.normalize_team_id('EUROLEAGUE', 'Real Madrid')
        'EUROLEAGUE_real_madrid'
        """
        normalized = BaseScraper.normalize_name(team_name)
        return f"{league_id}_{normalized}"

    @staticmethod
    def normalize_player_id(league_id: str, player_name: str) -> str:
        """
        Create a consistent player ID for database storage.

        Parameters:
        -----------
        league_id : str
            League identifier
        player_name : str
            Player's full name

        Returns:
        --------
        str
            Normalized player ID

        Example:
        --------
        >>> BaseScraper.normalize_player_id('EUROLEAGUE', 'LeBron James')
        'EUROLEAGUE_lebron_james'
        """
        normalized = BaseScraper.normalize_name(player_name)
        return f"{league_id}_{normalized}"

    @staticmethod
    def parse_height_cm(height_str: str) -> Optional[int]:
        """
        Parse various height formats and convert to centimeters.

        Basketball sites use many different height formats:
        - "196 cm" (European)
        - "6'5\"" (American feet-inches)
        - "6-5" (American alternative)
        - "6ft 5in"

        This function handles all of them!

        Parameters:
        -----------
        height_str : str
            Height string in any common format

        Returns:
        --------
        int or None
            Height in centimeters, or None if parsing failed

        Examples:
        ---------
        >>> BaseScraper.parse_height_cm("196 cm")
        196

        >>> BaseScraper.parse_height_cm("6'5")
        196  # (6 * 30.48) + (5 * 2.54) ≈ 196

        >>> BaseScraper.parse_height_cm("6-5")
        196
        """
        if not height_str:
            return None

        height_str = height_str.strip().lower()

        # Try to match centimeter format: "196 cm", "196cm"
        cm_match = re.search(r'(\d+)\s*cm', height_str)
        if cm_match:
            return int(cm_match.group(1))

        # Try to match feet-inches format: "6'5", "6-5", "6ft 5in"
        # This regex matches: digit(s), then ' or - or ft or space, then digit(s)
        ft_in_match = re.search(r"(\d+)['\-ft\s]+(\d+)", height_str)
        if ft_in_match:
            feet = int(ft_in_match.group(1))
            inches = int(ft_in_match.group(2))
            # Convert to cm: feet * 30.48 + inches * 2.54
            return int(feet * 30.48 + inches * 2.54)

        # Try to match feet only: "6ft", "6'"
        ft_only_match = re.search(r"(\d+)\s*(?:ft|')", height_str)
        if ft_only_match:
            feet = int(ft_only_match.group(1))
            return int(feet * 30.48)

        return None

    @staticmethod
    def parse_weight_kg(weight_str: str) -> Optional[int]:
        """
        Parse various weight formats and convert to kilograms.

        Similar to height, weight can be in different formats:
        - "95 kg" (European)
        - "210 lbs" (American)
        - "210 pounds"

        Parameters:
        -----------
        weight_str : str
            Weight string in any common format

        Returns:
        --------
        int or None
            Weight in kilograms, or None if parsing failed

        Examples:
        ---------
        >>> BaseScraper.parse_weight_kg("95 kg")
        95

        >>> BaseScraper.parse_weight_kg("210 lbs")
        95  # 210 * 0.453592 ≈ 95
        """
        if not weight_str:
            return None

        weight_str = weight_str.strip().lower()

        # Try kg format
        kg_match = re.search(r'(\d+)\s*kg', weight_str)
        if kg_match:
            return int(kg_match.group(1))

        # Try pounds format
        lbs_match = re.search(r'(\d+)\s*(?:lbs?|pounds?)', weight_str)
        if lbs_match:
            lbs = int(lbs_match.group(1))
            # Convert pounds to kg: lbs * 0.453592
            return int(lbs * 0.453592)

        return None

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean text by removing extra whitespace and newlines.

        Web pages often have messy formatting:
        - Random newlines
        - Multiple spaces
        - Tabs

        This cleans it up for consistent storage.

        Parameters:
        -----------
        text : str
            Text to clean

        Returns:
        --------
        str
            Cleaned text

        Example:
        --------
        >>> BaseScraper.clean_text("  John\\n  Smith  ")
        'John Smith'
        """
        if not text:
            return ''

        # Replace newlines, tabs, carriage returns with spaces
        text = re.sub(r'[\n\t\r]+', ' ', text)

        # Collapse multiple spaces into single space
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    @staticmethod
    def extract_text(element, default: str = '') -> str:
        """
        Safely extract text from a BeautifulSoup element.

        This handles the common case where an element might be None.
        Instead of crashing, it returns a default value.

        Parameters:
        -----------
        element : BeautifulSoup element or None
            The HTML element to extract text from
        default : str
            Value to return if element is None

        Returns:
        --------
        str
            Extracted and cleaned text, or default if element is None

        Example:
        --------
        # Without this helper (crashes if element not found):
        name = soup.find('div', class_='player-name').text

        # With this helper (safe):
        name_element = soup.find('div', class_='player-name')
        name = BaseScraper.extract_text(name_element, 'Unknown')
        """
        if element:
            return BaseScraper.clean_text(element.get_text())
        return default
