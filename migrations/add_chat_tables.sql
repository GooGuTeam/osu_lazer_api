-- 聊天功能相关表
-- 基于osu! lazer源码实现的聊天功能

-- 频道用户关系表
CREATE TABLE IF NOT EXISTS channel_users (
    channel_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_read_message_id INT DEFAULT NULL,
    PRIMARY KEY (channel_id, user_id),
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_channel_users_user_id (user_id),
    INDEX idx_channel_users_joined_at (joined_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 聊天消息表
CREATE TABLE IF NOT EXISTS chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    channel_id INT NOT NULL,
    user_id INT NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_action TINYINT(1) DEFAULT 0,
    uuid VARCHAR(36) DEFAULT NULL,
    FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_chat_messages_channel_id (channel_id),
    INDEX idx_chat_messages_user_id (user_id),
    INDEX idx_chat_messages_timestamp (timestamp),
    INDEX idx_chat_messages_uuid (uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户静音记录表
CREATE TABLE IF NOT EXISTS user_silences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    silenced_by INT NOT NULL,
    reason VARCHAR(512) NOT NULL,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME DEFAULT NULL,
    is_active TINYINT(1) DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (silenced_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_silences_user_id (user_id),
    INDEX idx_user_silences_is_active (is_active),
    INDEX idx_user_silences_start_time (start_time),
    INDEX idx_user_silences_end_time (end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 插入一些默认频道（如果不存在）
INSERT IGNORE INTO channels (name, topic, read_priv, write_priv, auto_join) VALUES
('osu', 'General discussion for osu!', 1, 1, 1),
('help', 'Help and support channel', 1, 1, 0),
('announce', 'Official announcements', 1, 64, 0);
