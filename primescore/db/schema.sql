-- ============================================================================
-- PrimeScore Database Schema  |  Group 7A  |  SETaP Iteration 2
-- Run:  psql primescore < schema.sql
-- ============================================================================

-- Create the database (run once, separately if needed)
-- CREATE DATABASE primescore;

-- ============================================================
--  USERS  (FR10: Registration & Login)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(100),
    display_name  VARCHAR(100),          -- BUG FIX #6: Added for profile support
    bio           TEXT,                  -- BUG FIX #6: Added for profile support
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login    TIMESTAMP,
    CONSTRAINT username_min_length CHECK (char_length(username) >= 3)
);

-- ============================================================
--  USER FAVOURITES  (FR2: max 5 teams, 25 players, 3 leagues)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_favourites (
    user_id          INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    favourite_teams   INTEGER[]    DEFAULT '{}',
    favourite_players INTEGER[]    DEFAULT '{}',
    favourite_leagues VARCHAR(10)[] DEFAULT '{}',
    favourite_team_names TEXT[] DEFAULT '{}',
    favourite_player_names TEXT[] DEFAULT '{}',
    favourite_league_names TEXT[] DEFAULT '{}',
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Enforce FR2 limits at the database level
    CONSTRAINT max_teams   CHECK (array_length(favourite_teams,   1) <= 5  OR favourite_teams   IS NULL),
    CONSTRAINT max_players CHECK (array_length(favourite_players, 1) <= 10 OR favourite_players IS NULL),
    CONSTRAINT max_leagues CHECK (array_length(favourite_leagues, 1) <= 3  OR favourite_leagues IS NULL)
);

-- ============================================================
--  NOTIFICATION SETTINGS  (FR9: Notification Preferences)
-- ============================================================
CREATE TABLE IF NOT EXISTS notification_settings (
    user_id                       INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    goals_notifications           BOOLEAN DEFAULT FALSE,
    match_start_notifications     BOOLEAN DEFAULT FALSE,
    match_end_notifications       BOOLEAN DEFAULT FALSE,
    -- FIX: these two columns were missing from the original schema
    favourite_team_notifications  BOOLEAN DEFAULT FALSE,
    favourite_player_notifications BOOLEAN DEFAULT FALSE,
    updated_at                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  POPULAR LEAGUES  (Reference data)
-- ============================================================
CREATE TABLE IF NOT EXISTS popular_leagues (
    league_code   VARCHAR(10) PRIMARY KEY,
    league_name   VARCHAR(100),
    country       VARCHAR(50),
    display_order INTEGER
);

INSERT INTO popular_leagues (league_code, league_name, country, display_order) VALUES
    ('PL',  'Premier League',               'England',       1),
    ('CL',  'UEFA Champions League',        'Europe',        2),
    ('BL1', 'Bundesliga',                   'Germany',       3),
    ('SA',  'Serie A',                      'Italy',         4),
    ('PD',  'La Liga',                      'Spain',         5),
    ('FL1', 'Ligue 1',                      'France',        6),
    ('ELC', 'Championship',                 'England',       7),
    ('EL',  'UEFA Europa League',           'Europe',        8),
    ('WC',  'FIFA World Cup',               'International', 9),
    ('EC',  'UEFA European Championship',   'Europe',        10)
ON CONFLICT (league_code) DO NOTHING;

-- ============================================================
--  INDEXES  (NFR1: Performance)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_users_username         ON users(username);

-- ============================================================
--  AUTO-UPDATE TIMESTAMPS  (trigger function)
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_user_favourites_updated_at      ON user_favourites;
DROP TRIGGER IF EXISTS update_notification_settings_updated_at ON notification_settings;

CREATE TRIGGER update_user_favourites_updated_at
    BEFORE UPDATE ON user_favourites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_settings_updated_at
    BEFORE UPDATE ON notification_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
--  TABLE COMMENTS  (documentation)
-- ============================================================
COMMENT ON TABLE users                   IS 'User accounts (FR10)';
COMMENT ON TABLE user_favourites         IS 'Favourite teams/players/leagues – max 5/25/3 (FR2)';
COMMENT ON TABLE notification_settings   IS 'Notification preferences (FR9)';
COMMENT ON TABLE popular_leagues         IS 'Reference list of leagues and display order';
