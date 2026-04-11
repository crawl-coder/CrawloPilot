#!/bin/bash
#===============================================================================
# CrawloPilot 数据库恢复脚本
# Phase 7: 灾备方案
#===============================================================================

set -e  # 遇到错误立即退出

# 配置
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_NAME="${DB_NAME:-crawlo_pilot}"
DB_USER="${DB_USER:-root}"
DB_PASS="${DB_PASS:-}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 显示用法
show_usage() {
    echo "用法: $0 <backup_file>"
    echo ""
    echo "示例:"
    echo "  $0 backups/crawlopilot_20240101_120000.sql.gz"
    echo ""
    echo "或者不指定文件，从列表中选择:"
    echo "  $0"
}

# 列出可用备份
list_backups() {
    log_info "可用备份文件:"
    echo ""
    
    BACKUPS=$(find "$BACKUP_DIR" -name "*.sql.gz" -type f 2>/dev/null | sort -r)
    
    if [ -z "$BACKUPS" ]; then
        log_error "没有找到备份文件"
        exit 1
    fi
    
    INDEX=1
    while IFS= read -r file; do
        SIZE=$(du -h "$file" | cut -f1)
        DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$file" 2>/dev/null || stat -c "%y" "$file" 2>/dev/null | cut -d' ' -f1,2 | head -c 16)
        echo "  [$INDEX] $file (大小: $SIZE, 日期: $DATE)"
        INDEX=$((INDEX+1))
    done <<< "$BACKUPS"
    
    echo ""
}

# 选择备份文件
select_backup() {
    list_backups
    
    read -p "请选择要恢复的备份编号 (1-${INDEX}): " choice
    
    if [ -z "$choice" ] || [ "$choice" -lt 1 ] || [ "$choice" -ge "$INDEX" ]; then
        log_error "无效的选择"
        exit 1
    fi
    
    BACKUP_FILE=$(find "$BACKUP_DIR" -name "*.sql.gz" -type f 2>/dev/null | sort -r | sed -n "${choice}p")
    
    if [ -z "$BACKUP_FILE" ]; then
        log_error "备份文件不存在"
        exit 1
    fi
    
    log_info "已选择: $BACKUP_FILE"
}

# 确认恢复
confirm_restore() {
    echo ""
    log_warn "⚠️  警告：此操作将覆盖现有数据库！"
    echo ""
    read -p "确认恢复数据库? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "取消恢复操作"
        exit 0
    fi
}

# 停止服务
stop_services() {
    log_step "停止 CrawloPilot 服务..."
    
    if [ -f "./dev.sh" ]; then
        ./dev.sh --stop
        log_info "服务已停止"
    else
        log_warn "未找到 dev.sh 脚本，请手动停止服务"
    fi
}

# 恢复数据库
restore_database() {
    log_step "恢复数据库..."
    
    log_info "数据库名称: $DB_NAME"
    log_info "备份文件: $BACKUP_FILE"
    
    # 解压并恢复
    if [ -n "$DB_PASS" ]; then
        export MYSQL_PWD="$DB_PASS"
        gunzip < "$BACKUP_FILE" | mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME"
    else
        gunzip < "$BACKUP_FILE" | mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME"
    fi
    
    log_info "数据库恢复完成"
}

# 验证恢复
verify_restore() {
    log_step "验证恢复结果..."
    
    # 检查表是否存在
    TABLES=$(mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" ${DB_PASS:+-p$DB_PASS} "$DB_NAME" -e "SHOW TABLES;" 2>/dev/null | wc -l)
    
    if [ "$TABLES" -gt 0 ]; then
        log_info "验证通过: 发现 $TABLES 个表"
    else
        log_error "验证失败: 未找到表"
        exit 1
    fi
}

# 启动服务
start_services() {
    log_step "启动 CrawloPilot 服务..."
    
    if [ -f "./start-dev.sh" ]; then
        ./start-dev.sh
        log_info "服务已启动"
    else
        log_warn "未找到 start-dev.sh 脚本，请手动启动服务"
    fi
}

# 显示恢复统计
show_restore_stats() {
    log_step "恢复统计..."
    
    # 记录数量
    USER_COUNT=$(mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" ${DB_PASS:+-p$DB_PASS} "$DB_NAME" -e "SELECT COUNT(*) FROM user;" 2>/dev/null | tail -1)
    PROJECT_COUNT=$(mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" ${DB_PASS:+-p$DB_PASS} "$DB_NAME" -e "SELECT COUNT(*) FROM project;" 2>/dev/null | tail -1)
    
    log_info "用户数量: $USER_COUNT"
    log_info "项目数量: $PROJECT_COUNT"
}

# 主函数
main() {
    echo "========================================"
    echo "  CrawloPilot 数据库恢复"
    echo "========================================"
    echo ""
    
    log_info "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # 检查参数
    if [ -n "$1" ]; then
        BACKUP_FILE="$1"
        if [ ! -f "$BACKUP_FILE" ]; then
            log_error "备份文件不存在: $BACKUP_FILE"
            exit 1
        fi
        log_info "使用指定备份文件: $BACKUP_FILE"
    else
        select_backup
    fi
    
    confirm_restore
    stop_services
    restore_database
    verify_restore
    start_services
    show_restore_stats
    
    echo ""
    log_info "恢复完成！"
    log_info "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
}

# 运行主函数
if [ "$#" -eq 0 ]; then
    main
else
    main "$1"
fi
