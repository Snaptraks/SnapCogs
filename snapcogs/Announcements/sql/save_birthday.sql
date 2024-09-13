INSERT INTO announcements_birthday
VALUES (:birthday, :guild_id, :user_id) ON CONFLICT(user_id, guild_id) DO
UPDATE
SET birthday = :birthday
WHERE user_id = :user_id
    AND guild_id = :guild_id
