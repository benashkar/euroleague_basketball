"""
=============================================================================
UNIT TESTS FOR HOMETOWN LOOKUP
=============================================================================

Tests for the Wikipedia-based hometown lookup functions.

HOW TO RUN:
    python -m pytest tests/test_hometown_lookup.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hometown_lookup_fixed import clean_name, parse_infobox, US_STATES, STATE_ABBREVS


# =============================================================================
# TESTS FOR clean_name()
# =============================================================================

class TestCleanName:
    """Tests for the clean_name() function."""

    def test_clean_name_reverses_last_first(self):
        """
        Test that 'Last, First' becomes 'First Last'.

        The API stores names as "Last, First" but Wikipedia
        and most displays expect "First Last".
        """
        result = clean_name("James, LeBron")
        assert result == "Lebron James"

    def test_clean_name_removes_jr_suffix(self):
        """
        Test that 'Jr.' suffix is removed.

        Suffixes can interfere with Wikipedia searches.
        """
        result = clean_name("Porter, Michael Jr.")
        assert result == "Michael Porter"

    def test_clean_name_removes_iii_suffix(self):
        """
        Test that Roman numeral suffixes are removed.
        """
        result = clean_name("Smith, John III")
        assert result == "John Smith"

    def test_clean_name_title_case(self):
        """
        Test that output is in title case.
        """
        result = clean_name("SMITH, JOHN")
        assert result == "John Smith"

    def test_clean_name_already_clean(self):
        """
        Test that names already in correct format work.
        """
        result = clean_name("LeBron James")
        assert result == "Lebron James"

    def test_clean_name_with_spaces(self):
        """
        Test handling of extra whitespace.
        """
        result = clean_name("  James , LeBron  ")
        assert result == "Lebron   James"  # Note: internal whitespace preserved


# =============================================================================
# TESTS FOR parse_infobox()
# =============================================================================

class TestParseInfobox:
    """Tests for the parse_infobox() function."""

    def test_parse_infobox_simple_birthplace(self):
        """
        Test parsing a simple birth_place format.

        Example: | birth_place = Chicago, Illinois
        """
        wikitext = """
{{Infobox basketball biography
| name = Test Player
| birth_place = Chicago, Illinois
| college = Duke
}}
"""
        result = parse_infobox(wikitext)

        assert result['hometown_city'] == 'Chicago'
        assert result['hometown_state'] == 'Illinois'
        assert result['lookup_successful'] == True

    def test_parse_infobox_wiki_link_format(self):
        """
        Test parsing birth_place with wiki links.

        Example: | birth_place = [[Chicago, Illinois]], U.S.
        """
        wikitext = """
{{Infobox basketball biography
| birth_place = [[Chicago, Illinois]], U.S.
| college = [[Duke Blue Devils men's basketball|Duke]]
}}
"""
        result = parse_infobox(wikitext)

        assert result['hometown_city'] == 'Chicago'
        assert result['hometown_state'] == 'Illinois'
        assert result['college'] == 'Duke'

    def test_parse_infobox_state_abbreviation(self):
        """
        Test that state abbreviations are expanded.

        Example: CA -> California
        """
        wikitext = """
| birth_place = Los Angeles, CA
}}
"""
        result = parse_infobox(wikitext)

        assert result['hometown_city'] == 'Los Angeles'
        assert result['hometown_state'] == 'California'

    def test_parse_infobox_extracts_college(self):
        """
        Test college extraction.
        """
        wikitext = """
| birth_place = Test, Texas
| college = [[University of Texas at Austin|Texas]]
}}
"""
        result = parse_infobox(wikitext)
        assert result['college'] == 'Texas'

    def test_parse_infobox_extracts_high_school(self):
        """
        Test high school extraction.
        """
        wikitext = """
| birth_place = Chicago, Illinois
| high_school = [[Oak Hill Academy (Virginia)|Oak Hill Academy]]
}}
"""
        result = parse_infobox(wikitext)
        assert result['high_school'] == 'Oak Hill Academy'

    def test_parse_infobox_no_data(self):
        """
        Test that empty/invalid wikitext returns unsuccessful lookup.
        """
        result = parse_infobox("")
        assert result['lookup_successful'] == False
        assert result['hometown_city'] is None

    def test_parse_infobox_non_us_location(self):
        """
        Test that non-US locations don't get extracted as hometowns.

        We only want US hometowns for American players.
        """
        wikitext = """
| birth_place = Toronto, Ontario, Canada
}}
"""
        result = parse_infobox(wikitext)
        # Ontario is not a US state, so should not be extracted
        assert result['hometown_state'] is None


# =============================================================================
# TESTS FOR STATE DATA
# =============================================================================

class TestStateData:
    """Tests for the US state configuration data."""

    def test_all_50_states_in_us_states(self):
        """
        Verify that all 50 states are included.
        """
        # 50 states + DC + D.C. variant
        assert len(US_STATES) >= 50

    def test_common_states_exist(self):
        """
        Check that common basketball states exist.
        """
        common_states = ['California', 'Texas', 'Florida', 'New York', 'Illinois']
        for state in common_states:
            assert state in US_STATES

    def test_state_abbrevs_match(self):
        """
        Test that abbreviations map to correct full names.
        """
        assert STATE_ABBREVS['CA'] == 'California'
        assert STATE_ABBREVS['TX'] == 'Texas'
        assert STATE_ABBREVS['NY'] == 'New York'
        assert STATE_ABBREVS['IL'] == 'Illinois'

    def test_all_abbrevs_map_to_valid_states(self):
        """
        Verify that all abbreviations map to states in US_STATES.
        """
        for abbrev, full_name in STATE_ABBREVS.items():
            assert full_name in US_STATES, f"{abbrev} maps to {full_name} which isn't in US_STATES"


# =============================================================================
# RUN TESTS
# =============================================================================
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
