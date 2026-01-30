"""
=============================================================================
HOMETOWN LOOKUP - WIKIPEDIA VERSION
=============================================================================

PURPOSE:
    This script finds the hometown and college information for American
    EuroLeague players by looking them up on Wikipedia.

WHY WIKIPEDIA:
    - The EuroLeague API doesn't include hometown/college data
    - Basketball Reference blocks automated requests (403 Forbidden)
    - Wikipedia has a free, public API that allows data collection
    - Wikipedia articles for basketball players usually have an "infobox"
      with birth_place, college, and high_school information

HOW IT WORKS:
    1. Load the list of American players from the most recent JSON export
    2. For each player:
       a. Search Wikipedia for "{player name} basketball player"
       b. Find the best matching article
       c. Download the raw "wikitext" (the markup code behind the article)
       d. Parse the infobox to extract birth_place, college, high_school
       e. Clean up the data (remove wiki markup, validate state names)
    3. Save results to JSON files

WHAT IS WIKITEXT?
    Wikipedia articles are stored in a special markup format called "wikitext".
    For example, a birth_place might look like:
        | birth_place = [[Chicago, Illinois]], U.S.
    or:
        | birth_place = [[Chicago]], [[Illinois]]

    We need to parse this markup to extract "Chicago, Illinois".

IMPORTANT NOTES FOR MAINTAINERS:
    - Wikipedia requires a User-Agent header or it will block requests
    - We add 0.3 second delays between requests to be respectful
    - Not all players have Wikipedia articles (newer/less famous players)
    - Success rate is typically 60-70% of players found

OUTPUT FILES (saved to output/json/):
    - american_hometowns_TIMESTAMP.json: All lookup results (found and not found)
    - american_hometowns_found_TIMESTAMP.json: Only players where we found data

SCHEDULE:
    - Runs as part of daily scrape via GitHub Actions
    - Uses || true in the workflow so failures don't stop the pipeline
"""

# =============================================================================
# IMPORTS
# =============================================================================
# json: For reading player data and saving results
import json

# os: For file path operations
import os

# re: Regular expressions for parsing wikitext markup
# Regular expressions are patterns for finding/matching text
import re

# requests: For making HTTP requests to Wikipedia API
# If you get "ModuleNotFoundError", run: pip install requests
import requests

# datetime: For timestamps in output files
from datetime import datetime

# logging: For status messages
import logging

# time: For adding delays between API requests (be nice to Wikipedia!)
import time

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
# Wikipedia API endpoint - this is the English Wikipedia API
WIKI_API = "https://en.wikipedia.org/w/api.php"

# CRITICAL: Wikipedia requires a User-Agent header!
# Without this, you'll get empty responses or errors.
# The format should identify your project and provide contact info.
HEADERS = {'User-Agent': 'EuroLeagueTracker/1.0 (basketball data collection)'}

# =============================================================================
# MANUAL OVERRIDES
# =============================================================================
# Some players share names with more famous NBA players, causing Wikipedia
# lookups to return the wrong person. This dictionary provides correct data
# for those players. Key is the player's name (as it appears in the data).
#
# To add a new override:
#   1. Find the correct Wikipedia page for the player
#   2. Add an entry with hometown_city, hometown_state, college, high_school
#
MANUAL_OVERRIDES = {
    # Devin Booker (born 1991) plays in EuroLeague - NOT the Phoenix Suns player
    # Source: https://en.wikipedia.org/wiki/Devin_Booker_(basketball,_born_1991)
    'BOOKER, DEVIN': {
        'hometown_city': 'Union',
        'hometown_state': 'South Carolina',
        'college': 'Clemson',
        'high_school': 'Union County High School',
    },
}

# =============================================================================
# US STATE DATA
# =============================================================================
# We need to validate that a location is actually in the US.
# These sets let us check if a state name is valid.

# Full state names
US_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming', 'District of Columbia', 'D.C.'
}

# Two-letter abbreviations mapped to full names
# Used when Wikipedia uses "Chicago, IL" instead of "Chicago, Illinois"
STATE_ABBREVS = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
}


# =============================================================================
# NAME CLEANING FUNCTION
# =============================================================================

def clean_name(name):
    """
    Clean a player's name for Wikipedia search.

    WHAT IT DOES:
        The EuroLeague API stores names as "Last, First" (e.g., "James, LeBron").
        We need to convert this to "First Last" for Wikipedia searches.
        Also removes suffixes like Jr., Sr., II, III that might confuse search.

    PARAMETERS:
        name (str): The player's name from the API (e.g., "James, LeBron")

    RETURNS:
        str: Cleaned name suitable for search (e.g., "LeBron James")

    EXAMPLE:
        >>> clean_name("James, LeBron")
        'Lebron James'
        >>> clean_name("Thompson, Klay Jr.")
        'Klay Thompson'
        >>> clean_name("Porter, Michael Jr.")
        'Michael Porter'
    """
    # Check if name is in "Last, First" format
    if ', ' in name:
        # Split on comma and reverse the order
        parts = name.split(', ', 1)  # Split only on first comma
        name = f"{parts[1]} {parts[0]}"  # Rearrange to "First Last"

    # Convert to title case (first letter of each word capitalized)
    name = name.title()

    # Remove common suffixes that might interfere with search
    # \s+ matches one or more whitespace characters
    # $ means end of string
    # flags=re.IGNORECASE makes it case-insensitive
    name = re.sub(r'\s+(Ii|Iii|Iv|Jr\.?|Sr\.?)$', '', name, flags=re.IGNORECASE)

    return name.strip()


# =============================================================================
# WIKIPEDIA API FUNCTIONS
# =============================================================================

def search_wikipedia(name):
    """
    Search Wikipedia for a basketball player's article.

    WHAT IT DOES:
        Uses Wikipedia's search API to find articles matching the player's name.
        Searches for "{name} basketball player" to filter out non-basketball results.
        (e.g., there are many people named "Michael Jordan")

    PARAMETERS:
        name (str): The cleaned player name (e.g., "LeBron James")

    RETURNS:
        str or None: The title of the best matching Wikipedia article,
                     or None if no match found

    HOW IT CHOOSES THE BEST MATCH:
        1. First, look for articles where the title contains the player's name
        2. If no exact match, return the first search result
        3. If no results at all, return None

    EXAMPLE:
        >>> search_wikipedia("LeBron James")
        'LeBron James'
        >>> search_wikipedia("Unknown Player Who Doesnt Exist")
        None
    """
    # Build the API request parameters
    params = {
        'action': 'query',       # We're querying Wikipedia
        'list': 'search',        # Specifically, doing a search
        'srsearch': f'{name} basketball player',  # The search query
        'format': 'json',        # Return results as JSON
        'srlimit': 5             # Get up to 5 results
    }

    try:
        # Make the API request
        # IMPORTANT: Must include headers with User-Agent!
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
        data = resp.json()

        # Extract the search results
        results = data.get('query', {}).get('search', [])

        # Try to find an exact name match first
        # This helps avoid finding the wrong person with a similar name
        name_lower = name.lower()
        for result in results:
            title = result.get('title', '')
            # If the player's name appears in the article title, that's our match
            if name_lower in title.lower():
                return title

        # No exact match - just return the first result if we have any
        if results:
            return results[0].get('title')

    except Exception as e:
        # Log the error but don't crash - just return None
        logger.debug(f"Wikipedia search error: {e}")

    return None


def get_wiki_wikitext(title):
    """
    Get the raw wikitext content of a Wikipedia article.

    WHAT IS WIKITEXT?
        Wikitext is the markup language used to write Wikipedia articles.
        It includes special formatting for links, templates, infoboxes, etc.

        For example, a player's article might start with:
        {{Infobox basketball biography
        | name = LeBron James
        | birth_date = {{birth date and age|1984|12|30}}
        | birth_place = [[Akron, Ohio]], U.S.
        | college = (did not attend)
        ...
        }}

    PARAMETERS:
        title (str): The exact title of the Wikipedia article

    RETURNS:
        str or None: The raw wikitext content, or None if error

    WHY WE NEED THIS:
        We could use Wikipedia's "extract" API to get plain text, but that
        doesn't include the structured infobox data. The wikitext lets us
        parse out specific fields like birth_place and college.
    """
    # Build the API request parameters
    params = {
        'action': 'query',       # We're querying Wikipedia
        'titles': title,         # The specific article we want
        'prop': 'revisions',     # We want revision content
        'rvprop': 'content',     # Specifically, the content of the revision
        'rvslots': 'main',       # Get the main content slot
        'format': 'json'         # Return as JSON
    }

    try:
        # Make the API request
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        data = resp.json()

        # The response has a nested structure:
        # { 'query': { 'pages': { '12345': { 'revisions': [...] } } } }
        pages = data.get('query', {}).get('pages', {})

        # Loop through pages (there should only be one)
        for page_id, page in pages.items():
            # page_id of '-1' means the page doesn't exist
            if page_id != '-1':
                revisions = page.get('revisions', [])
                if revisions:
                    # Get the content from the first (and only) revision
                    # The content is nested under 'slots' -> 'main' -> '*'
                    return revisions[0].get('slots', {}).get('main', {}).get('*', '')

    except Exception as e:
        logger.debug(f"Wiki content error: {e}")

    return None


# =============================================================================
# WIKITEXT PARSING FUNCTION
# =============================================================================

def parse_infobox(wikitext):
    """
    Parse a Wikipedia article's wikitext to extract player information.

    WHAT IT DOES:
        Searches the wikitext for the infobox fields we care about:
        - birth_place: Where the player is from (e.g., "Chicago, Illinois")
        - college: Where they went to college (e.g., "Duke")
        - high_school: Their high school (e.g., "Oak Hill Academy")

        Then cleans up the wiki markup to get plain text values.

    PARAMETERS:
        wikitext (str): The raw wikitext content of the article

    RETURNS:
        dict: A dictionary with the extracted information:
            {
                'hometown_city': 'Chicago',
                'hometown_state': 'Illinois',
                'high_school': 'Oak Hill Academy',
                'college': 'Duke',
                'lookup_successful': True
            }

    WIKI MARKUP EXAMPLES:
        The birth_place field might look like any of these:
        - | birth_place = [[Chicago, Illinois]], U.S.
        - | birth_place = [[Chicago]], [[Illinois]], [[United States|U.S.]]
        - | birth_place = {{city-state|Chicago|Illinois}}

        We need to handle all these formats!

    PARSING STRATEGY:
        1. Use regex to find the field (e.g., "| birth_place = ...")
        2. Extract everything until the next field or end of infobox
        3. Remove wiki link markup: [[text]] -> text
        4. Remove template markup: {{template}} -> (removed)
        5. Split on commas to separate city and state
        6. Validate that the state is a real US state
    """
    # Initialize the result dictionary with all fields set to None
    result = {
        'hometown_city': None,
        'hometown_state': None,
        'high_school': None,
        'college': None,
        'lookup_successful': False  # Will set to True if we find data
    }

    # If no wikitext provided, return empty result
    if not wikitext:
        return result

    # =========================================================================
    # Parse birth_place
    # =========================================================================
    # Regex pattern explanation:
    # \|           - Match a literal pipe character (fields start with |)
    # \s*          - Match zero or more whitespace characters
    # birth_place  - Match the literal text "birth_place"
    # \s*=\s*      - Match = sign with optional whitespace around it
    # (.+?)        - CAPTURE GROUP: match one or more characters (non-greedy)
    # (?=\n\||\n\}\})  - LOOK AHEAD: stop when we hit newline+pipe or newline+}}
    #
    # The (?=...) is a "look ahead" - it finds the boundary but doesn't include it
    # The (.+?) being non-greedy (?) means it takes the smallest match possible

    birth_match = re.search(r'\|\s*birth_place\s*=\s*(.+?)(?=\n\||\n\}\})', wikitext, re.DOTALL)

    if birth_match:
        # Get the raw birth_place text
        birth_text = birth_match.group(1).strip()

        # Clean up wiki markup
        # Pattern 1: [[Link|Display Text]] -> Display Text
        # Example: [[United States|U.S.]] -> U.S.
        birth_text = re.sub(r'\[\[([^\]|]+)\|[^\]]+\]\]', r'\1', birth_text)

        # Pattern 2: [[Simple Link]] -> Simple Link
        # Example: [[Chicago, Illinois]] -> Chicago, Illinois
        birth_text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', birth_text)

        # Pattern 3: Remove templates like {{birth date|1990|5|15}}
        # We don't need these for location data
        birth_text = re.sub(r'\{\{[^}]+\}\}', '', birth_text)

        # Remove "U.S." and "USA" since we already know they're American
        birth_text = birth_text.replace('U.S.', '').replace('USA', '').strip().rstrip(',')

        # Split on commas to get city and state
        # "Chicago, Illinois" -> ["Chicago", "Illinois"]
        parts = [p.strip() for p in birth_text.split(',') if p.strip()]

        if len(parts) >= 2:
            city = parts[0]
            state = parts[1]

            # Validate the state - make sure it's a real US state
            if state in US_STATES:
                result['hometown_city'] = city
                result['hometown_state'] = state
            elif state in STATE_ABBREVS:
                # Convert abbreviation to full name
                result['hometown_city'] = city
                result['hometown_state'] = STATE_ABBREVS[state]

    # =========================================================================
    # Parse college
    # =========================================================================
    # Same pattern as birth_place but looking for "college" field
    college_match = re.search(r'\|\s*college\s*=\s*(.+?)(?=\n\||\n\}\})', wikitext, re.DOTALL)

    if college_match:
        college_text = college_match.group(1).strip()

        # College links often look like:
        # [[Duke Blue Devils men's basketball|Duke]]
        # We want "Duke" not "Duke Blue Devils men's basketball"

        # First try to extract from [[Full Name|Short Name]] format
        college_link = re.search(r'\[\[([^\]|]+)\|([^\]]+)\]\]', college_text)
        if college_link:
            result['college'] = college_link.group(2).strip()
        else:
            # Try simple [[College Name]] format
            college_link = re.search(r'\[\[([^\]]+)\]\]', college_text)
            if college_link:
                result['college'] = college_link.group(1).strip()
            else:
                # No wiki links - just clean up templates and use the text
                college_text = re.sub(r'\{\{[^}]+\}\}', '', college_text).strip()
                if college_text and len(college_text) > 2:
                    result['college'] = college_text

    # =========================================================================
    # Parse high_school
    # =========================================================================
    # Same pattern as college
    hs_match = re.search(r'\|\s*high_school\s*=\s*(.+?)(?=\n\||\n\}\})', wikitext, re.DOTALL)

    if hs_match:
        hs_text = hs_match.group(1).strip()

        # Extract from wiki links
        hs_link = re.search(r'\[\[([^\]|]+)\|([^\]]+)\]\]', hs_text)
        if hs_link:
            result['high_school'] = hs_link.group(2).strip()
        else:
            hs_link = re.search(r'\[\[([^\]]+)\]\]', hs_text)
            if hs_link:
                result['high_school'] = hs_link.group(1).strip()
            else:
                hs_text = re.sub(r'\{\{[^}]+\}\}', '', hs_text).strip()
                if hs_text and len(hs_text) > 2:
                    result['high_school'] = hs_text

    # =========================================================================
    # Determine if lookup was successful
    # =========================================================================
    # We consider it successful if we found either hometown OR college
    # (Some players might not have college listed if they went straight to pros)
    if result['hometown_state'] or result['college']:
        result['lookup_successful'] = True

    return result


# =============================================================================
# MAIN LOOKUP FUNCTION
# =============================================================================

def lookup_player(name):
    """
    Look up a player's hometown and college information.

    WHAT IT DOES:
        This is the main function that combines all the steps:
        1. Clean the player's name
        2. Search Wikipedia for their article
        3. Download the article's wikitext
        4. Parse the infobox for hometown/college
        5. Return the results

    PARAMETERS:
        name (str): The player's name (can be "Last, First" format)

    RETURNS:
        dict or None: The lookup results, or None if player not found

    EXAMPLE:
        >>> lookup_player("James, LeBron")
        {
            'hometown_city': 'Akron',
            'hometown_state': 'Ohio',
            'college': None,  # LeBron didn't go to college
            'high_school': 'St. Vincent-St. Mary',
            'wiki_title': 'LeBron James',
            'lookup_successful': True
        }
    """
    # Step 1: Clean the name for searching
    clean = clean_name(name)

    # Step 2: Search Wikipedia
    title = search_wikipedia(clean)
    if not title:
        # No Wikipedia article found
        return None

    # Step 3: Get the wikitext
    wikitext = get_wiki_wikitext(title)
    if not wikitext:
        # Couldn't get the article content
        return None

    # Step 4: Parse the infobox
    result = parse_infobox(wikitext)

    # Add the Wikipedia title to the result (useful for debugging)
    result['wiki_title'] = title

    # Only return if we found useful data
    return result if result['lookup_successful'] else None


# =============================================================================
# DATA LOADING AND SAVING FUNCTIONS
# =============================================================================

def load_american_players():
    """
    Load the list of American players from the most recent JSON export.

    WHAT IT DOES:
        Looks in the output/json/ directory for files that contain American
        player data and loads the most recent one.

    RETURNS:
        list: A list of player dictionaries, or empty list if not found

    FILE NAMING:
        We look for files starting with:
        - 'american_players_full_' (from full scrapes)
        - 'american_players_2026' (daily scrapes with timestamps)

        We exclude files that have 'hometown', 'wiki', 'performance', or 'stats'
        in the name since those are output files from this script.
    """
    # Build path to output directory
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')

    # File prefixes that contain source player data
    valid_prefixes = ['american_players_full_', 'american_players_2026']

    # Find matching files
    files = []
    for f in os.listdir(output_dir):
        for prefix in valid_prefixes:
            # Check if file matches our criteria
            if (f.startswith(prefix) and
                'hometown' not in f and
                'wiki' not in f and
                'performance' not in f and
                'stats' not in f):
                files.append(f)
                break  # Don't add same file twice

    if not files:
        return []

    # Sort to get most recent (timestamps sort chronologically)
    files = sorted(files)

    # Load the most recent file
    filepath = os.path.join(output_dir, files[-1])
    logger.info(f"Loading from: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('players', [])


def save_json(data, filename):
    """
    Save data to a JSON file in the output directory.

    PARAMETERS:
        data (dict): The data to save
        filename (str): The filename (e.g., 'american_hometowns_20240115.json')

    This is the same save function used in other scripts - keeps output
    format consistent across the project.
    """
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main entry point for the hometown lookup script.

    WHAT IT DOES:
        1. Load American players from JSON
        2. Deduplicate the list (some players appear twice)
        3. For each player, look up their hometown on Wikipedia
        4. Save all results to JSON
        5. Save successful lookups to a separate JSON file
        6. Print a summary of what was found
    """
    logger.info("=" * 60)
    logger.info("HOMETOWN LOOKUP - FIXED VERSION")
    logger.info("=" * 60)

    # Generate timestamp for output files
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # =========================================================================
    # Step 1: Load Players
    # =========================================================================
    players = load_american_players()
    if not players:
        logger.error("No players found")
        return

    # =========================================================================
    # Step 2: Deduplicate
    # =========================================================================
    # Some players might appear twice if they transferred teams mid-season
    seen = set()
    unique = []
    for p in players:
        code = p.get('code')
        if code and code not in seen:
            seen.add(code)
            unique.append(p)

    logger.info(f"Processing {len(unique)} unique players")

    # =========================================================================
    # Step 3: Look Up Each Player
    # =========================================================================
    results = []
    success = 0
    failed = 0

    for i, player in enumerate(unique):
        name = player.get('name', '')
        team = player.get('team_name', 'Unknown')
        clean = clean_name(name)

        # Show progress
        logger.info(f"[{i+1}/{len(unique)}] {clean} ({team})")

        # Build the result record (includes original player data)
        player_result = {
            'code': player.get('code'),
            'name': name,
            'clean_name': clean,
            'team_code': player.get('team_code'),
            'team_name': team,
            'nationality': player.get('nationality'),
            'birth_date': player.get('birth_date'),
        }

        # Check for manual override first (handles name collisions with famous players)
        if name.upper() in MANUAL_OVERRIDES:
            override = MANUAL_OVERRIDES[name.upper()]
            player_result['hometown_city'] = override.get('hometown_city')
            player_result['hometown_state'] = override.get('hometown_state')
            player_result['college'] = override.get('college')
            player_result['high_school'] = override.get('high_school')
            player_result['lookup_successful'] = True
            player_result['source'] = 'manual_override'
            success += 1
            logger.info(f"  OVERRIDE: {override.get('hometown_city')}, {override.get('hometown_state')} | College: {override.get('college')}")
        else:
            # Look up on Wikipedia
            info = lookup_player(name)

            if info and info.get('lookup_successful'):
                # Merge the lookup results into our record
                player_result.update(info)
                success += 1
                logger.info(f"  FOUND: {info.get('hometown_city')}, {info.get('hometown_state')} | College: {info.get('college')}")
            else:
                player_result['lookup_successful'] = False
                failed += 1
                logger.info(f"  Not found")

            # IMPORTANT: Rate limiting!
            # Be respectful to Wikipedia's servers - wait between requests
            time.sleep(0.3)

        results.append(player_result)

    # =========================================================================
    # Step 4: Save Results
    # =========================================================================
    # Save all results (both found and not found)
    save_json({
        'export_date': datetime.now().isoformat(),
        'total': len(unique),
        'found': success,
        'not_found': failed,
        'players': results
    }, f'american_hometowns_{timestamp}.json')

    # Save just the successful lookups (easier to work with)
    found = [p for p in results if p.get('lookup_successful')]
    save_json({
        'export_date': datetime.now().isoformat(),
        'count': len(found),
        'players': found
    }, f'american_hometowns_found_{timestamp}.json')

    # =========================================================================
    # Step 5: Print Summary
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total: {len(unique)}")
    logger.info(f"Found: {success} ({success/len(unique)*100:.1f}%)")
    logger.info(f"Not found: {failed}")

    # Show some examples of what we found
    if found:
        logger.info("\nPlayers with hometown:")
        for p in found[:20]:  # Show first 20
            logger.info(f"  {p['clean_name']}: {p.get('hometown_city')}, {p.get('hometown_state')} | {p.get('college')}")


# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    main()
