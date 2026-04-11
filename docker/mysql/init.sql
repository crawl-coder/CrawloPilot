-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS crawlopilot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户（如果不存在）
CREATE USER IF NOT EXISTS 'crawlopilot'@'%' IDENTIFIED BY 'crawlopilot123';

-- 授予权限
GRANT ALL PRIVILEGES ON crawlopilot.* TO 'crawlopilot'@'%';

-- 刷新权限
FLUSH PRIVILEGES;

-- 使用数据库
USE crawlopilot;

-- 这里可以添加初始数据，例如默认管理员账户
-- 注意：密码需要使用 bcrypt 哈希
