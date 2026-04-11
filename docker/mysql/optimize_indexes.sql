-- CrawloPilot 数据库索引优化脚本
-- 用于提升查询性能

-- 使用数据库
USE crawlopilot;

-- ==================== 用户相关索引 ====================

-- 用户表（已有主键和unique索引，确认）
-- ALTER TABLE user ADD INDEX idx_user_username (username);
-- ALTER TABLE user ADD INDEX idx_user_email (email);
ALTER TABLE user ADD INDEX idx_user_is_active (is_active);
ALTER TABLE user ADD INDEX idx_user_created_at (created_at);

-- ==================== 项目相关索引 ====================

-- 项目表
ALTER TABLE project ADD INDEX idx_project_team_id (team_id);
ALTER TABLE project ADD INDEX idx_project_status (status);
ALTER TABLE project ADD INDEX idx_project_created_at (created_at);
ALTER TABLE project ADD INDEX idx_project_team_status (team_id, status);

-- 项目版本表
ALTER TABLE project_version ADD INDEX idx_project_version_project_id (project_id);
ALTER TABLE project_version ADD INDEX idx_project_version_status (status);
ALTER TABLE project_version ADD INDEX idx_project_version_created_at (created_at);
ALTER TABLE project_version ADD INDEX idx_project_version_project_status (project_id, status);

-- ==================== 调度相关索引 ====================

-- 调度表
ALTER TABLE schedule ADD INDEX idx_schedule_project_id (project_id);
ALTER TABLE schedule ADD INDEX idx_schedule_enabled (enabled);
ALTER TABLE schedule ADD INDEX idx_schedule_next_run_time (next_run_time);
ALTER TABLE schedule ADD INDEX idx_schedule_project_enabled (project_id, enabled);
ALTER TABLE schedule ADD INDEX idx_schedule_type_enabled (schedule_type, enabled);

-- 任务实例表
ALTER TABLE task_instance ADD INDEX idx_task_instance_schedule_id (schedule_id);
ALTER TABLE task_instance ADD INDEX idx_task_instance_status (status);
ALTER TABLE task_instance ADD INDEX idx_task_instance_created_at (created_at);
ALTER TABLE task_instance ADD INDEX idx_task_instance_started_at (started_at);
ALTER TABLE task_instance ADD INDEX idx_task_instance_schedule_status (schedule_id, status);
ALTER TABLE task_instance ADD INDEX idx_task_instance_status_created (status, created_at);

-- ==================== 容器相关索引 ====================

-- 节点表
ALTER TABLE node ADD INDEX idx_node_status (status);
ALTER TABLE node ADD INDEX idx_node_last_heartbeat (last_heartbeat);

-- 容器表
ALTER TABLE container ADD INDEX idx_container_node_id (node_id);
ALTER TABLE container ADD INDEX idx_container_project_id (project_id);
ALTER TABLE container ADD INDEX idx_container_status (status);
ALTER TABLE container ADD INDEX idx_container_started_at (started_at);

-- 部署表
ALTER TABLE deploy ADD INDEX idx_deploy_project_id (project_id);
ALTER TABLE deploy ADD INDEX idx_deploy_status (status);
ALTER TABLE deploy ADD INDEX idx_deploy_created_at (created_at);
ALTER TABLE deploy ADD INDEX idx_deploy_project_status (project_id, status);

-- ==================== 监控告警索引 ====================

-- 告警规则表
ALTER TABLE alert_rule ADD INDEX idx_alert_rule_project_id (project_id);
ALTER TABLE alert_rule ADD INDEX idx_alert_rule_enabled (enabled);
ALTER TABLE alert_rule ADD INDEX idx_alert_rule_type (rule_type);

-- ==================== 代理池索引 ====================

-- 代理池表
ALTER TABLE proxy_pool ADD INDEX idx_proxy_pool_status (status);
ALTER TABLE proxy_pool ADD INDEX idx_proxy_pool_group (group_name);
ALTER TABLE proxy_pool ADD INDEX idx_proxy_pool_health_score (health_score);
ALTER TABLE proxy_pool ADD INDEX idx_proxy_pool_group_status (group_name, status);

-- ==================== API配置索引 ====================

-- API配置表
ALTER TABLE api_config ADD INDEX idx_api_config_project_id (project_id);
ALTER TABLE api_config ADD INDEX idx_api_config_enabled (enabled);

-- ==================== 审计日志索引 ====================

-- 审计日志表（已有user_id和created_at索引，补充）
ALTER TABLE audit_log ADD INDEX idx_audit_log_action (action);
ALTER TABLE audit_log ADD INDEX idx_audit_log_resource (resource_type, resource_id);
ALTER TABLE audit_log ADD INDEX idx_audit_log_user_created (user_id, created_at);

-- ==================== 团队相关索引 ====================

-- 团队成员表
ALTER TABLE team_member ADD INDEX idx_team_member_user_id (user_id);
ALTER TABLE team_member ADD INDEX idx_team_member_team_id (team_id);

-- 用户角色表
ALTER TABLE user_role ADD INDEX idx_user_role_user_id (user_id);
ALTER TABLE user_role ADD INDEX idx_user_role_role_id (role_id);

-- ==================== 分析查询优化 ====================

-- 为常用聚合查询创建覆盖索引
ALTER TABLE task_instance ADD INDEX idx_task_stats (status, started_at, finished_at);

-- 为按时间范围查询创建复合索引
ALTER TABLE audit_log ADD INDEX idx_audit_time_range (created_at, user_id, action);

-- ==================== 查看索引创建结果 ====================

SELECT 
    TABLE_NAME,
    INDEX_NAME,
    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS COLUMNS,
    INDEX_TYPE
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'crawlopilot'
GROUP BY TABLE_NAME, INDEX_NAME, INDEX_TYPE
ORDER BY TABLE_NAME, INDEX_NAME;
