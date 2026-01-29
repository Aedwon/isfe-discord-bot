CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    log_channel_id BIGINT NULL,
    ticket_category_id BIGINT NULL,
    ticket_transcript_channel_id BIGINT NULL,
    embed_log_channel_id BIGINT NULL
);

CREATE TABLE IF NOT EXISTS command_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    guild_id BIGINT,
    channel_id BIGINT,
    command_name VARCHAR(100),
    args TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    channel_id BIGINT UNIQUE,
    guild_id BIGINT,
    creator_id BIGINT,
    category VARCHAR(50),
    status ENUM('open', 'closed') DEFAULT 'open',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    claimed_by BIGINT NULL,
    is_test BOOLEAN DEFAULT FALSE,
    escalated_48h BOOLEAN DEFAULT FALSE,
    reminded_24h BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS ticket_ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_name VARCHAR(100),
    user_id BIGINT,
    handler_mention VARCHAR(100),
    stars INT,
    remarks TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reaction_roles (
    message_id BIGINT,
    channel_id BIGINT,
    guild_id BIGINT,
    emoji VARCHAR(100),
    role_id BIGINT,
    PRIMARY KEY (message_id, emoji)
);

CREATE TABLE IF NOT EXISTS scheduled_embeds (
    identifier VARCHAR(20) PRIMARY KEY,
    channel_id BIGINT,
    user_id BIGINT,
    content TEXT,
    embed_json JSON,
    schedule_for DATETIME,
    status ENUM('pending', 'sent', 'failed') DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS autocreate_configs (
    voice_channel_id BIGINT PRIMARY KEY,
    category_id BIGINT
);

CREATE TABLE IF NOT EXISTS teams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    game_name VARCHAR(20) NOT NULL,
    team_name VARCHAR(100) NOT NULL,
    UNIQUE KEY unique_team (game_name, team_name)
);

CREATE TABLE IF NOT EXISTS player_registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    discord_id BIGINT NOT NULL,
    team_id INT NOT NULL,
    ign VARCHAR(50) NULL,
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- Index for faster lookups by discord_id
CREATE INDEX IF NOT EXISTS idx_registrations_discord ON player_registrations(discord_id);

-- Unique constraint: one player per game (enforced in application logic since we need to join tables)
