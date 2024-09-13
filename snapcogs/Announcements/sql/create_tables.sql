CREATE TABLE IF NOT EXISTS announcements_birthday (
    birthday DATE,
    guild_id INTEGER,
    user_id INTEGER,
    UNIQUE (guild_id, user_id)
)
