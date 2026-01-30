"""
=============================================================================
SCRAPE EUROLEAGUE ROSTERS WITH SELENIUM
=============================================================================

Uses Selenium to scrape roster pages that load via JavaScript.
This allows us to get player nationality data which isn't available via API.
"""

import json
import os
import re
import time
from datetime import datetime
import logging

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# American nationality indicators
AMERICAN_NATIONALITIES = ['USA', 'United States', 'US', 'U.S.A.', 'American', 'United States of America']


def is_american(nationality):
    """Check if nationality indicates American player."""
    if not nationality:
        return False
    nationality_lower = str(nationality).lower()
    return any(ind.lower() in nationality_lower for ind in AMERICAN_NATIONALITIES)


def save_json(data, filename):
    """Save data to JSON file."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output', 'json')
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved: {filepath}")
    return filepath


def setup_driver():
    """Set up Chrome driver with headless mode."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def get_team_urls(driver):
    """Get all team roster URLs from the standings page."""
    logger.info("Fetching team list from EuroLeague standings page...")

    # Try standings page which has all current teams
    driver.get("https://www.euroleaguebasketball.net/euroleague/standings/")
    time.sleep(4)

    page_source = driver.page_source

    # Find all team links - look for team codes in various patterns
    team_patterns = [
        r'href="[^"]*(/euroleague/teams/([^/"]+))/?"',
        r'href="/euroleague/teams/([^/"]+)/?["\']',
        r'/euroleague/teams/([a-z0-9-]+)/',
    ]

    team_codes = set()
    for pattern in team_patterns:
        matches = re.findall(pattern, page_source, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                code = match[1] if len(match) > 1 else match[0]
            else:
                code = match
            # Filter out invalid codes
            if code and len(code) > 2 and code not in ['teams', 'roster', 'stats']:
                team_codes.add(code.lower())

    # If still no teams, try the main page
    if not team_codes:
        logger.info("No teams from standings, trying main page...")
        driver.get("https://www.euroleaguebasketball.net/euroleague/")
        time.sleep(3)
        page_source = driver.page_source

        for pattern in team_patterns:
            matches = re.findall(pattern, page_source, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    code = match[1] if len(match) > 1 else match[0]
                else:
                    code = match
                if code and len(code) > 2 and code not in ['teams', 'roster', 'stats']:
                    team_codes.add(code.lower())

    # If still no teams, use known 2024-25 EuroLeague teams
    if not team_codes:
        logger.info("Using hardcoded team list for 2024-25 season")
        team_codes = {
            'real-madrid', 'fc-barcelona', 'olympiacos-piraeus', 'panathinaikos-athens',
            'fenerbahce-beko-istanbul', 'anadolu-efes-istanbul', 'virtus-segafredo-bologna',
            'ea7-emporio-armani-milan', 'maccabi-playtika-tel-aviv', 'zalgiris-kaunas',
            'ldlc-asvel-villeurbanne', 'monaco', 'partizan-mozzart-bet-belgrade',
            'fc-bayern-munich', 'crvena-zvezda-meridianbet-belgrade', 'alba-berlin',
            'baskonia-vitoria-gasteiz', 'paris-basketball'
        }

    # Build team URLs
    team_urls = []
    for code in sorted(team_codes):
        roster_url = f"https://www.euroleaguebasketball.net/euroleague/teams/{code}/roster/"
        team_urls.append({
            'code': code,
            'roster_url': roster_url
        })

    logger.info(f"Found {len(team_urls)} teams")
    return team_urls


def scrape_team_roster(driver, team_info):
    """Scrape a single team's roster for player data including nationality."""
    team_code = team_info['code']
    roster_url = team_info['roster_url']

    logger.info(f"Scraping roster: {team_code}")

    players = []

    try:
        driver.get(roster_url)
        time.sleep(3)

        # Wait for roster to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            pass

        # Get page source
        page_source = driver.page_source

        # Try to get team name from page
        team_name = team_code.replace('-', ' ').title()
        team_name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', page_source)
        if team_name_match:
            team_name = team_name_match.group(1).strip()

        # Debug: save page source for inspection
        # with open(f'debug_{team_code}.html', 'w', encoding='utf-8') as f:
        #     f.write(page_source)

        # Try to find players using Selenium elements
        try:
            # Look for any player-related elements
            player_elements = driver.find_elements(By.CSS_SELECTOR,
                "a[href*='/players/'], .player-card, .roster-player, [data-player]")

            for elem in player_elements:
                try:
                    href = elem.get_attribute('href') or ''
                    if '/players/' in href:
                        player_code = href.split('/players/')[1].strip('/').split('/')[0]

                        # Try to get player name
                        name = elem.text.strip() or player_code.replace('-', ' ').title()

                        # Try to find nationality nearby
                        nationality = None
                        try:
                            # Look for flag or country in parent elements
                            parent = elem.find_element(By.XPATH, '..')
                            parent_html = parent.get_attribute('innerHTML')

                            # Check for flag images
                            flag_match = re.search(r'/flags?/([a-z]{2,3})\.', parent_html, re.IGNORECASE)
                            if flag_match:
                                flag_code = flag_match.group(1).upper()
                                nationality = flag_code

                            # Check for country text
                            country_match = re.search(r'(?:nationality|country)["\s:>]*([A-Za-z\s]+)', parent_html, re.IGNORECASE)
                            if country_match and not nationality:
                                nationality = country_match.group(1).strip()
                        except:
                            pass

                        if player_code not in [p['player_code'] for p in players]:
                            players.append({
                                'player_code': player_code,
                                'name': name,
                                'player_url': href,
                                'team_code': team_code,
                                'team_name': team_name,
                                'nationality': nationality
                            })
                except Exception as e:
                    continue
        except Exception as e:
            logger.debug(f"Element search failed: {e}")

        # Fallback: regex search for player links
        if not players:
            player_links = re.findall(
                r'href="(https?://[^"]*euroleague[^"]*/players/([^/"]+)/?)"',
                page_source
            )

            seen_players = set()
            for link, player_code in player_links:
                if player_code not in seen_players and player_code not in ['stats', 'news']:
                    seen_players.add(player_code)
                    players.append({
                        'player_code': player_code,
                        'name': player_code.replace('-', ' ').title(),
                        'player_url': link,
                        'team_code': team_code,
                        'team_name': team_name,
                        'nationality': None
                    })

        logger.info(f"  Found {len(players)} players on {team_code}")

    except Exception as e:
        logger.error(f"Error scraping {team_code}: {e}")

    return players


def scrape_player_details(driver, player_info):
    """Scrape individual player page for nationality and details."""
    player_url = player_info['player_url']
    player_code = player_info['player_code']

    try:
        driver.get(player_url)
        time.sleep(1.5)

        # Wait for content
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
        except:
            pass

        page_source = driver.page_source

        # Extract player name
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', page_source)
        if name_match:
            player_info['name'] = name_match.group(1).strip()

        # Look for nationality/country
        # Common patterns: "Country: USA", flag images, nationality spans

        # Pattern 1: Text with country label
        country_patterns = [
            r'(?:Country|Nationality)[:\s]*([A-Za-z\s]+)',
            r'class="[^"]*country[^"]*"[^>]*>([^<]+)',
            r'class="[^"]*nationality[^"]*"[^>]*>([^<]+)',
            r'data-country="([^"]+)"',
            r'<span[^>]*class="[^"]*flag[^"]*"[^>]*title="([^"]+)"',
        ]

        for pattern in country_patterns:
            match = re.search(pattern, page_source, re.IGNORECASE)
            if match:
                country = match.group(1).strip()
                if country and len(country) < 50:  # Sanity check
                    player_info['nationality'] = country
                    break

        # Pattern 2: Look for flag images
        flag_match = re.search(r'/flags?/([a-z]{2,3})\.', page_source, re.IGNORECASE)
        if flag_match and 'nationality' not in player_info:
            flag_code = flag_match.group(1).upper()
            # Map common flag codes
            flag_map = {'US': 'USA', 'USA': 'USA', 'ES': 'Spain', 'FR': 'France',
                       'DE': 'Germany', 'IT': 'Italy', 'RS': 'Serbia', 'TR': 'Turkey',
                       'GR': 'Greece', 'LT': 'Lithuania', 'SI': 'Slovenia'}
            player_info['nationality'] = flag_map.get(flag_code, flag_code)

        # Look for position
        position_match = re.search(r'(?:Position|Pos)[:\s]*([A-Za-z\s/]+)', page_source, re.IGNORECASE)
        if position_match:
            player_info['position'] = position_match.group(1).strip()

        # Look for height
        height_match = re.search(r'(\d{3})\s*cm|(\d[\'"]\d+[\'""]?)', page_source)
        if height_match:
            player_info['height'] = height_match.group(0)

        # Look for birthdate/age
        birth_match = re.search(r'(?:Born|Birth|DOB)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})', page_source, re.IGNORECASE)
        if birth_match:
            player_info['birthdate'] = birth_match.group(1)

    except Exception as e:
        logger.error(f"Error scraping player {player_code}: {e}")

    return player_info


def main():
    logger.info("=" * 60)
    logger.info("SCRAPING EUROLEAGUE DATA WITH SELENIUM")
    logger.info("=" * 60)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Set up the driver
    logger.info("Setting up Chrome driver...")
    driver = setup_driver()

    try:
        # Get all team URLs
        teams = get_team_urls(driver)

        if not teams:
            logger.error("No teams found!")
            return

        # Scrape each team's roster
        all_players = []
        for team in teams:
            roster = scrape_team_roster(driver, team)
            all_players.extend(roster)
            time.sleep(1)  # Rate limiting

        logger.info(f"\nTotal players found: {len(all_players)}")

        # Now scrape individual player pages for nationality
        logger.info("\nScraping individual player pages for nationality...")

        for i, player in enumerate(all_players):
            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i+1}/{len(all_players)}")

            scrape_player_details(driver, player)
            time.sleep(0.5)  # Rate limiting

        # Identify American players
        american_players = [p for p in all_players if is_american(p.get('nationality', ''))]

        logger.info(f"\nFound {len(american_players)} American players")

        # Print American players
        for player in american_players:
            logger.info(f"  USA: {player.get('name', player['player_code'])} - {player.get('team_name', 'Unknown')}")

        # Save all players
        players_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'season': '2024-25',
            'player_count': len(all_players),
            'players': all_players
        }
        save_json(players_export, f'euroleague_players_selenium_{timestamp}.json')

        # Save American players
        american_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'season': '2024-25',
            'american_player_count': len(american_players),
            'players': american_players
        }
        save_json(american_export, f'american_players_selenium_{timestamp}.json')

        # Save teams
        teams_export = {
            'export_date': datetime.now().isoformat(),
            'league': 'EuroLeague',
            'season': '2024-25',
            'team_count': len(teams),
            'teams': teams
        }
        save_json(teams_export, f'euroleague_teams_selenium_{timestamp}.json')

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Teams scraped: {len(teams)}")
        logger.info(f"Total players: {len(all_players)}")
        logger.info(f"American players: {len(american_players)}")

        # Show players with nationality found
        players_with_nationality = [p for p in all_players if p.get('nationality')]
        logger.info(f"Players with nationality data: {len(players_with_nationality)}")

    finally:
        driver.quit()
        logger.info("\nBrowser closed.")


if __name__ == '__main__':
    main()
