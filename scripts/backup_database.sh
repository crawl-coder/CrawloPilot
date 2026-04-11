#!/bin/bash
#===============================================================================
# CrawloPilot 数据库备份脚本
# Phase 7: 灾备方案
#===============================================================================

set -e  # 遇到错误立即退出

# 配置
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="${DB_NAME:-crawlo_pilot}"
DB_USER="${DB_USER:-root}"
DB_PASS="${DB_PASS:-}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"

# 备份文件名
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"
CONFIG_BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_config_${TIMESTAMP}.tar.gz"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v mysqldump &> /dev/null; then
        log_error "mysqldump 未安装"
        exit 1
    fi
    
    if ! command -v gzip &> /dev/null; then
        log_error "gzip 未安装"
        exit 1
    fi
    
    log_info "依赖检查完成"
}

# 创建备份目录
create_backup_dir() {
    log_info "创建备份目录..."
    mkdir -p "$BACKUP_DIR"
    log_info "备份目录: $BACKUP_DIR"
}

# 备份数据库
backup_database() {
    log_info "开始备份数据库..."
    
    if [ -n "$DB_PASS" ]; then
        export MYSQL_PWD="$DB_PASS"
        mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"
    else
        mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"
    fi
    
    if [ -f "$BACKUP_FILE" ]; then
        SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log_info "数据库备份完成: $BACKUP_FILE (大小: $SIZE)"
    else
        log_error "数据库备份失败"
        exit 1
    fi
}

# 备份配置文件
backup_config() {
    log_info "备份配置文件..."
    
    # 备份 .env 文件
    if [ -f "../.env" ]; then
        cp ../.env "$BACKUP_DIR/.env.$TIMESTAMP"
        log_info "配置文件已备份"
    else
        log_warn ".env 文件不存在，跳过"
    fi
    
    # 备份 docker-compose.yml
    if [ -f "../docker-compose.yml" ]; then
        cp ../docker-compose.yml "$BACKUP_DIR/docker-compose.yml.$TIMESTAMP"
        log_info "Docker 配置已备份"
    fi
}

# 清理旧备份
cleanup_old_backups() {
    log_info "清理超过 30 天的备份..."
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
    log_info "旧备份清理完成"
}

# 验证备份
verify_backup() {
    log_info "验证备份文件..."
    
    if [ -f "$BACKUP_FILE" ]; then
        # 检查 gzip 文件是否有效
        if gzip -t "$BACKUP_FILE" 2>/dev/null; then
            log_info "备份文件验证通过"
            return 0
        else
            log_error "备份文件损坏"
            return 1
        fi
    else
        log_error "备份文件不存在"
        return 1
    fi
}

# 上传到远程存储（可选）
upload_to_remote() {
    if [ -n "$S3_BUCKET" ]; then
        log_info "上传备份到 S3..."
        if command -v aws &> /dev/null; then
            aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/mysql/"
            log_info "上传完成"
        else
            log_warn "AWS CLI 未安装，跳过上传"
        fi
    fi
}

# 显示备份统计
show_backup_stats() {
    log_info "备份统计..."
    
    # 备份文件数量
    COUNT=$(find "$BACKUP_DIR" -name "*.sql.gz" | wc -l)
    log_info "数据库备份文件数量: $COUNT"
    
    # 备份总大小
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
    log_info "备份目录总大小: $TOTAL_SIZE"
}

# 主函数
main() {
    echo "========================================"
    echo "  CrawloPilot 数据库备份"
    echo "========================================"
    echo ""
    
    log_info "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    check_dependencies
    create_backup_dir
    backup_database
    backup_config
    cleanup_old_backups
    
    if verify_backup; then
        upload_to_remote
        show_backup_stats
        echo ""
        log_info "备份完成！"
        log_info "备份文件: $BACKUP_FILE"
    else
        log_error "备份验证失败"
        exit 1
    fi
    
    echo ""
    log_info "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
}

# 运行主函数
main
