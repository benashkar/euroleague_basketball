-- EuroLeague Tracker Database Schema
-- Version: 1.0

CREATE DATABASE IF NOT EXISTS euroleague_tracker
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE euroleague_tracker;

-- ============================================
-- LEAGUES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS leagues (
    league_id VARCHAR(20) PRIMARY KEY,
    league_name VARCHAR(100) NOT NULL,
    league_code VARCHAR(10) NOT NULL,
    region VARCHAR(50),
    website_url VARCHAR(255),
    api_url VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'Europe/Madrid',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Insert EuroLeague
INSERT INTO leagues (league_id, league_name, league_code, region, website_url)
VALUES ('EUROLEAGUE', 'EuroLeague', 'EL', 'Europe', 'https://www.euroleaguebasketball.net/euroleague/')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- ============================================
-- TEAMS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS teams (
    team_id VARCHAR(50) PRIMARY KEY,
    league_id VARCHAR(20) NOT NULL,
    team_name VARCHAR(100) NOT NULL,
    team_name_normalized VARCHAR(100) NOT NULL,
    team_code VARCHAR(20),
    team_slug VARCHAR(100),
    city VARCHAR(100),
    country VARCHAR(100),
    arena VARCHAR(150),
    arena_capacity INT,
    logo_url VARCHAR(500),
    website_url VARCHAR(255),
    source_team_id VARCHAR(50) COMMENT 'Original ID from EuroLeague source',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (league_id) REFERENCES leagues(league_id),
    INDEX idx_team_normalized (team_name_normalized),
    INDEX idx_league (league_id),
    INDEX idx_team_code (team_code)
) ENGINE=InnoDB;

-- ============================================
-- PLAYERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS players (
    player_id VARCHAR(50) PRIMARY KEY,
    team_id VARCHAR(50),
    league_id VARCHAR(20) NOT NULL DEFAULT 'EUROLEAGUE',

    -- Basic Info
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(200) NOT NULL,
    full_name_normalized VARCHAR(200) NOT NULL,
    jersey_number VARCHAR(5),
    position VARCHAR(20),

    -- Physical
    height_cm INT,
    height_display VARCHAR(20) COMMENT 'Original format e.g. 6-5 or 196cm',
    weight_kg INT,
    weight_display VARCHAR(20),

    -- Birth Info
    birth_date DATE,
    birth_year INT,
    birth_country VARCHAR(100),
    birth_city VARCHAR(100),

    -- American Player Flag
    is_american BOOLEAN DEFAULT FALSE,

    -- Hometown Info (for American players)
    hometown_city VARCHAR(100),
    hometown_state VARCHAR(50),
    hometown_source VARCHAR(50) COMMENT 'basketball_reference, wikipedia, grokepedia, manual',
    hometown_lookup_date DATE,

    -- Education
    high_school VARCHAR(200),
    high_school_city VARCHAR(100),
    high_school_state VARCHAR(50),
    college VARCHAR(200),
    college_years VARCHAR(50) COMMENT 'e.g. 2018-2022',

    -- Photos
    photo_url VARCHAR(500) COMMENT 'Primary photo URL',
    photo_url_16x9 VARCHAR(500) COMMENT 'Preferred 16:9 aspect ratio photo',
    photo_url_square VARCHAR(500) COMMENT 'Square/headshot photo',
    photo_source VARCHAR(50) COMMENT 'Source of photo',

    -- Profile Links
    euroleague_profile_url VARCHAR(500),
    basketball_ref_url VARCHAR(500),
    wikipedia_url VARCHAR(500),

    -- Meta
    source_player_id VARCHAR(50) COMMENT 'Original ID from EuroLeague',
    needs_hometown_lookup BOOLEAN DEFAULT FALSE,
    needs_manual_review BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (league_id) REFERENCES leagues(league_id),
    INDEX idx_american (is_american),
    INDEX idx_hometown_state (hometown_state),
    INDEX idx_hometown_city (hometown_city, hometown_state),
    INDEX idx_high_school (high_school),
    INDEX idx_name_normalized (full_name_normalized),
    INDEX idx_needs_lookup (needs_hometown_lookup),
    INDEX idx_team (team_id)
) ENGINE=InnoDB;

-- ============================================
-- SCHEDULE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS schedule (
    game_id VARCHAR(50) PRIMARY KEY,
    league_id VARCHAR(20) NOT NULL DEFAULT 'EUROLEAGUE',
    season VARCHAR(20),
    season_code VARCHAR(20),

    -- Round Info
    round_number INT,
    round_name VARCHAR(50),
    phase VARCHAR(50) COMMENT 'Regular Season, Playoffs, Final Four',

    -- Teams
    home_team_id VARCHAR(50),
    away_team_id VARCHAR(50),

    -- Date/Time
    game_date DATE NOT NULL,
    game_time TIME,
    game_datetime DATETIME,
    timezone VARCHAR(50) DEFAULT 'Europe/Madrid',
    game_date_utc DATETIME,

    -- Venue
    venue VARCHAR(200),
    city VARCHAR(100),
    country VARCHAR(100),

    -- Status
    status ENUM('scheduled', 'in_progress', 'completed', 'postponed', 'cancelled') DEFAULT 'scheduled',

    -- Scores (populated after game)
    home_score INT,
    away_score INT,
    home_score_q1 INT,
    home_score_q2 INT,
    home_score_q3 INT,
    home_score_q4 INT,
    home_score_ot INT,
    away_score_q1 INT,
    away_score_q2 INT,
    away_score_q3 INT,
    away_score_q4 INT,
    away_score_ot INT,
    overtime_periods INT DEFAULT 0,

    -- Attendance
    attendance INT,

    -- Tracking flags
    has_american_player BOOLEAN DEFAULT FALSE,
    american_player_count INT DEFAULT 0,
    stats_scraped BOOLEAN DEFAULT FALSE,
    stats_scraped_at DATETIME,

    -- Meta
    source_game_id VARCHAR(50),
    game_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (league_id) REFERENCES leagues(league_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id),
    INDEX idx_date (game_date),
    INDEX idx_status (status),
    INDEX idx_american_games (has_american_player, game_date),
    INDEX idx_season (season, round_number),
    INDEX idx_needs_stats (status, stats_scraped)
) ENGINE=InnoDB;

-- ============================================
-- GAME STATISTICS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS game_stats (
    stat_id INT AUTO_INCREMENT PRIMARY KEY,
    game_id VARCHAR(50) NOT NULL,
    player_id VARCHAR(50) NOT NULL,
    team_id VARCHAR(50),

    -- Game context
    is_home_team BOOLEAN,
    is_starter BOOLEAN,
    did_not_play BOOLEAN DEFAULT FALSE,
    dnp_reason VARCHAR(100),

    -- Time
    minutes_played VARCHAR(10) COMMENT 'Original format MM:SS',
    minutes_decimal DECIMAL(5,2) COMMENT 'Converted to decimal',

    -- Scoring
    points INT DEFAULT 0,

    -- Rebounds
    rebounds_total INT DEFAULT 0,
    rebounds_offensive INT DEFAULT 0,
    rebounds_defensive INT DEFAULT 0,

    -- Assists/Steals/Blocks
    assists INT DEFAULT 0,
    steals INT DEFAULT 0,
    blocks INT DEFAULT 0,
    blocks_against INT DEFAULT 0,

    -- Turnovers/Fouls
    turnovers INT DEFAULT 0,
    fouls_personal INT DEFAULT 0,
    fouls_drawn INT DEFAULT 0,
    fouls_technical INT DEFAULT 0,

    -- Field Goals
    fg_made INT DEFAULT 0,
    fg_attempted INT DEFAULT 0,
    fg_percentage DECIMAL(5,2),

    -- Two Pointers
    two_pt_made INT DEFAULT 0,
    two_pt_attempted INT DEFAULT 0,
    two_pt_percentage DECIMAL(5,2),

    -- Three Pointers
    three_pt_made INT DEFAULT 0,
    three_pt_attempted INT DEFAULT 0,
    three_pt_percentage DECIMAL(5,2),

    -- Free Throws
    ft_made INT DEFAULT 0,
    ft_attempted INT DEFAULT 0,
    ft_percentage DECIMAL(5,2),

    -- Advanced
    plus_minus INT,
    efficiency_rating INT COMMENT 'EuroLeague PIR',

    -- Meta
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (game_id) REFERENCES schedule(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE KEY unique_game_player (game_id, player_id),
    INDEX idx_player_stats (player_id),
    INDEX idx_game_stats (game_id)
) ENGINE=InnoDB;

-- ============================================
-- HOMETOWN LOOKUP CACHE TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS hometown_cache (
    cache_id INT AUTO_INCREMENT PRIMARY KEY,
    player_name_search VARCHAR(200) NOT NULL COMMENT 'Normalized name used for search',
    lookup_source VARCHAR(50) NOT NULL COMMENT 'basketball_reference, wikipedia, grokepedia',
    lookup_successful BOOLEAN DEFAULT FALSE,

    -- Found Data
    hometown_city VARCHAR(100),
    hometown_state VARCHAR(50),
    high_school VARCHAR(200),
    high_school_city VARCHAR(100),
    high_school_state VARCHAR(50),
    college VARCHAR(200),

    -- Source URLs
    source_url VARCHAR(500),
    profile_url VARCHAR(500),
    photo_url VARCHAR(500),

    -- Raw data for debugging
    raw_response TEXT,

    -- Meta
    lookup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_player_lookup (player_name_search),
    INDEX idx_source (lookup_source),
    INDEX idx_successful (lookup_successful)
) ENGINE=InnoDB;

-- ============================================
-- PLAYER PHOTOS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS player_photos (
    photo_id INT AUTO_INCREMENT PRIMARY KEY,
    player_id VARCHAR(50) NOT NULL,

    photo_url VARCHAR(500) NOT NULL,
    photo_source VARCHAR(50) COMMENT 'euroleague, basketball_reference, wikipedia',

    -- Dimensions
    width INT,
    height INT,
    aspect_ratio VARCHAR(10) COMMENT 'e.g. 16:9, 4:3, 1:1',
    aspect_ratio_decimal DECIMAL(5,3),

    -- Preferences
    is_primary BOOLEAN DEFAULT FALSE,
    is_16x9 BOOLEAN DEFAULT FALSE,
    is_square BOOLEAN DEFAULT FALSE,

    -- Validation
    url_valid BOOLEAN DEFAULT TRUE,
    last_validated DATETIME,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (player_id) REFERENCES players(player_id),
    INDEX idx_player_photos (player_id),
    INDEX idx_aspect (is_16x9),
    INDEX idx_primary (is_primary)
) ENGINE=InnoDB;

-- ============================================
-- SCRAPE LOG TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS scrape_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    scrape_type VARCHAR(50) NOT NULL COMMENT 'teams, rosters, schedule, game_stats, hometown',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',
    items_processed INT DEFAULT 0,
    items_success INT DEFAULT 0,
    items_failed INT DEFAULT 0,
    error_message TEXT,

    INDEX idx_scrape_type (scrape_type),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- ============================================
-- VIEWS FOR COMMON QUERIES
-- ============================================

-- American players with hometown data
CREATE OR REPLACE VIEW v_american_players AS
SELECT
    p.player_id,
    p.full_name,
    p.position,
    p.jersey_number,
    p.hometown_city,
    p.hometown_state,
    p.high_school,
    p.college,
    p.photo_url_16x9,
    p.photo_url,
    t.team_name,
    t.team_id,
    p.hometown_source,
    p.needs_manual_review
FROM players p
JOIN teams t ON p.team_id = t.team_id
WHERE p.is_american = TRUE
  AND p.is_active = TRUE
ORDER BY p.hometown_state, p.hometown_city, p.last_name;

-- Upcoming games with American players
CREATE OR REPLACE VIEW v_upcoming_american_games AS
SELECT
    s.game_id,
    s.game_date,
    s.game_time,
    s.game_datetime,
    s.venue,
    ht.team_name AS home_team,
    ht.team_id AS home_team_id,
    at.team_name AS away_team,
    at.team_id AS away_team_id,
    s.status,
    s.american_player_count
FROM schedule s
JOIN teams ht ON s.home_team_id = ht.team_id
JOIN teams at ON s.away_team_id = at.team_id
WHERE s.has_american_player = TRUE
  AND s.game_date >= CURDATE()
  AND s.status IN ('scheduled', 'in_progress')
ORDER BY s.game_date, s.game_time;

-- Games needing stats scraped
CREATE OR REPLACE VIEW v_games_needing_stats AS
SELECT
    s.game_id,
    s.game_date,
    ht.team_name AS home_team,
    at.team_name AS away_team,
    s.home_score,
    s.away_score
FROM schedule s
JOIN teams ht ON s.home_team_id = ht.team_id
JOIN teams at ON s.away_team_id = at.team_id
WHERE s.status = 'completed'
  AND s.stats_scraped = FALSE
ORDER BY s.game_date DESC;

-- Players needing hometown lookup
CREATE OR REPLACE VIEW v_players_needing_hometown AS
SELECT
    p.player_id,
    p.full_name,
    p.full_name_normalized,
    t.team_name,
    p.birth_country,
    p.hometown_city,
    p.hometown_state,
    p.high_school
FROM players p
JOIN teams t ON p.team_id = t.team_id
WHERE p.is_american = TRUE
  AND p.is_active = TRUE
  AND p.needs_hometown_lookup = TRUE
  AND (p.hometown_state IS NULL OR p.high_school IS NULL)
ORDER BY p.full_name;
