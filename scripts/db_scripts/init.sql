-- 农业智能问答系统数据库初始化脚本
-- 适用于MySQL数据库

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS agri_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE agri_db;

-- 删除现有表（如果存在）
DROP TABLE IF EXISTS schedules;
DROP TABLE IF EXISTS expert_consultations;
DROP TABLE IF EXISTS planting_plans;
DROP TABLE IF EXISTS chat_messages;
DROP TABLE IF EXISTS users;

-- 创建用户表
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100),
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建聊天消息表
CREATE TABLE chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建种植计划表
CREATE TABLE planting_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    crop_name VARCHAR(100) NOT NULL,
    plan_details TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT '进行中',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建专家咨询表
CREATE TABLE expert_consultations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    expert_name VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    reply TEXT,
    status VARCHAR(20) NOT NULL DEFAULT '待回复',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建日程表
CREATE TABLE schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    date DATETIME NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX idx_planting_plans_user_id ON planting_plans(user_id);
CREATE INDEX idx_expert_consultations_user_id ON expert_consultations(user_id);
CREATE INDEX idx_schedules_user_id ON schedules(user_id);
CREATE INDEX idx_users_username ON users(username);

-- 插入默认管理员用户
-- 密码：admin123
INSERT INTO users (username, email, hashed_password, is_admin) VALUES
('admin', 'admin@example.com', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', TRUE);

-- 插入默认测试用户
INSERT INTO users (username, email, hashed_password) VALUES
('test', 'test@example.com', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW');

-- 插入测试数据
INSERT INTO planting_plans (user_id, crop_name, plan_details, status) VALUES
(2, '水稻', '水稻种植计划：1. 整地 2. 育苗 3. 插秧 4. 田间管理 5. 收获', '进行中'),
(2, '小麦', '小麦种植计划：1. 整地 2. 播种 3. 田间管理 4. 收获', '进行中');

INSERT INTO expert_consultations (user_id, expert_name, category, content, status) VALUES
(2, '张专家', '病虫害防治', '我的水稻出现了稻瘟病，应该如何防治？', '待回复'),
(2, '李专家', '种植技术', '如何提高小麦的产量？', '待回复');

INSERT INTO schedules (user_id, title, content, date, is_completed) VALUES
(2, '水稻施肥', '给水稻施加分蘖肥', '2026-05-01 09:00:00', FALSE),
(2, '小麦浇水', '给小麦浇水', '2026-05-02 10:00:00', FALSE);

-- 插入测试聊天消息
INSERT INTO chat_messages (user_id, role, content) VALUES
(2, 'user', '如何种植水稻？'),
(2, 'assistant', '水稻种植步骤：1. 整地 2. 育苗 3. 插秧 4. 田间管理 5. 收获');

-- 提交事务
COMMIT;

-- 显示创建结果
SHOW TABLES;
SELECT '数据库初始化完成' AS message;