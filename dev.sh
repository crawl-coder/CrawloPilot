#!/bin/bash

# CrawloPilot 完整启动脚本
# 支持本地开发模式和 Docker 模式

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo -e "${CYAN}=========================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}=========================================${NC}"
    echo ""
}

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -m, --mode MODE      启动模式 (local|docker), 默认: local"
    echo "  -b, --backend        仅启动后端"
    echo "  -f, --frontend       仅启动前端"
    echo "  -d, --database       仅启动数据库"
    echo "  -s, --stop           停止所有服务"
    echo "  -r, --restart        重启所有服务"
    echo "  -c, --clean          清理所有数据和日志"
    echo "  -h, --help           显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                   # 本地开发模式启动前后端"
    echo "  $0 -m docker         # Docker 模式启动所有服务"
    echo "  $0 -b                # 仅启动后端"
    echo "  $0 -f                # 仅启动前端"
    echo "  $0 --stop            # 停止所有服务"
    echo ""
}

# 检查依赖
check_dependencies() {
    print_header "检查依赖"
    
    local has_error=false
    
    # 检查 Python
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version | cut -d' ' -f2)
        print_success "Python $python_version 已安装"
    else
        print_error "Python3 未安装"
        has_error=true
    fi
    
    # 检查 pip
    if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
        print_success "pip 已安装"
    else
        print_error "pip 未安装"
        has_error=true
    fi
    
    # 检查 Node.js
    if command -v node &> /dev/null; then
        local node_version=$(node --version)
        print_success "Node.js $node_version 已安装"
    else
        print_warning "Node.js 未安装（前端开发需要）"
    fi
    
    # 检查 npm
    if command -v npm &> /dev/null; then
        local npm_version=$(npm --version)
        print_success "npm $npm_version 已安装"
    else
        print_warning "npm 未安装（前端开发需要）"
    fi
    
    # 检查 Docker (可选)
    if command -v docker &> /dev/null; then
        local docker_version=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
        print_success "Docker $docker_version 已安装"
    else
        print_warning "Docker 未安装（Docker 模式需要）"
    fi
    
    if [ "$has_error" = true ]; then
        print_error "缺少必要依赖，请先安装"
        exit 1
    fi
    
    echo ""
}

# 初始化环境
init_environment() {
    print_header "初始化环境"
    
    # 检查 .env 文件
    if [ ! -f .env ]; then
        print_warning ".env 文件不存在，从 .env.example 复制..."
        cp .env.example .env
        print_success "已创建 .env 文件"
        print_warning "请检查并修改 .env 文件中的配置"
    else
        print_success ".env 文件已存在"
    fi
    
    # 创建必要的目录
    print_info "创建数据目录..."
    mkdir -p docker/mysql/data
    mkdir -p docker/redis/data
    mkdir -p docker/minio/data
    mkdir -p docker/prometheus/data
    mkdir -p docker/grafana/data
    mkdir -p logs
    print_success "数据目录创建完成"
    
    echo ""
}

# 安装后端依赖
install_backend_deps() {
    print_header "安装后端依赖"
    
    cd backend
    
    if [ -f "requirements.txt" ]; then
        print_info "安装 Python 依赖..."
        pip3 install -r requirements.txt -q
        print_success "后端依赖安装完成"
    else
        print_error "requirements.txt 不存在"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
    echo ""
}

# 安装前端依赖
install_frontend_deps() {
    print_header "安装前端依赖"
    
    cd frontend
    
    if [ -f "package.json" ]; then
        print_info "安装 Node.js 依赖..."
        npm install --silent
        print_success "前端依赖安装完成"
    else
        print_error "package.json 不存在"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
    echo ""
}

# 启动数据库（Docker）
start_database() {
    print_header "启动数据库服务"
    
    if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null compose; then
        print_error "docker-compose 未安装"
        exit 1
    fi
    
    print_info "启动 MySQL 和 Redis..."
    
    # 使用 docker-compose 仅启动数据库服务
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d mysql redis
    else
        docker compose up -d mysql redis
    fi
    
    print_info "等待数据库启动..."
    sleep 5
    
    # 检查 MySQL 是否就绪
    local max_retries=10
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if docker-compose exec mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
            print_success "MySQL 已就绪"
            break
        fi
        retry_count=$((retry_count + 1))
        print_info "等待 MySQL 启动... ($retry_count/$max_retries)"
        sleep 2
    done
    
    if [ $retry_count -eq $max_retries ]; then
        print_error "MySQL 启动超时"
        exit 1
    fi
    
    print_success "Redis 已就绪"
    echo ""
}

# 运行数据库迁移
run_migrations() {
    print_header "运行数据库迁移"
    
    cd backend
    
    if [ -f "alembic.ini" ]; then
        print_info "执行 Alembic 迁移..."
        alembic upgrade head
        print_success "数据库迁移完成"
    else
        print_warning "Alembic 配置文件不存在，跳过迁移"
    fi
    
    cd "$PROJECT_ROOT"
    echo ""
}

# 启动后端
start_backend() {
    print_header "启动后端服务"
    
    cd backend
    
    print_info "启动 FastAPI 服务器..."
    print_info "API 文档: http://localhost:8000/docs"
    print_info "日志文件: logs/backend.log"
    
    # 在后台启动 uvicorn
    nohup uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        > ../logs/backend.log 2>&1 &
    
    local pid=$!
    echo $pid > ../logs/backend.pid
    
    # 等待服务器启动
    sleep 3
    
    # 检查是否成功启动
    if kill -0 $pid 2>/dev/null; then
        print_success "后端服务已启动 (PID: $pid)"
    else
        print_error "后端服务启动失败，查看日志: logs/backend.log"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
    echo ""
}

# 启动前端
start_frontend() {
    print_header "启动前端服务"
    
    cd frontend
    
    print_info "启动 Vite 开发服务器..."
    print_info "前端界面: http://localhost:3000"
    print_info "日志文件: logs/frontend.log"
    
    # 在后台启动 vite
    nohup npm run dev \
        > ../logs/frontend.log 2>&1 &
    
    local pid=$!
    echo $pid > ../logs/frontend.pid
    
    # 等待服务器启动
    sleep 3
    
    # 检查是否成功启动
    if kill -0 $pid 2>/dev/null; then
        print_success "前端服务已启动 (PID: $pid)"
    else
        print_error "前端服务启动失败，查看日志: logs/frontend.log"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
    echo ""
}

# 启动 Docker 模式
start_docker() {
    print_header "Docker 模式启动"
    
    print_info "启动所有服务..."
    
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    
    print_info "等待服务启动..."
    sleep 10
    
    print_info "检查服务状态..."
    if command -v docker-compose &> /dev/null; then
        docker-compose ps
    else
        docker compose ps
    fi
    
    echo ""
    print_success "所有服务已启动"
    echo ""
}

# 停止服务
stop_services() {
    print_header "停止服务"
    
    # 停止后端
    if [ -f "logs/backend.pid" ]; then
        local pid=$(cat logs/backend.pid)
        if kill -0 $pid 2>/dev/null; then
            print_info "停止后端服务 (PID: $pid)..."
            kill $pid
            print_success "后端服务已停止"
        fi
        rm -f logs/backend.pid
    fi
    
    # 停止前端
    if [ -f "logs/frontend.pid" ]; then
        local pid=$(cat logs/frontend.pid)
        if kill -0 $pid 2>/dev/null; then
            print_info "停止前端服务 (PID: $pid)..."
            kill $pid
            print_success "前端服务已停止"
        fi
        rm -f logs/frontend.pid
    fi
    
    # 停止 Docker 服务
    if command -v docker-compose &> /dev/null; then
        if docker-compose ps --quiet 2>/dev/null | grep -q .; then
            print_info "停止 Docker 服务..."
            docker-compose down
            print_success "Docker 服务已停止"
        fi
    elif command -v docker &> /dev/null; then
        if docker compose ps --quiet 2>/dev/null | grep -q .; then
            print_info "停止 Docker 服务..."
            docker compose down
            print_success "Docker 服务已停止"
        fi
    fi
    
    echo ""
    print_success "所有服务已停止"
    echo ""
}

# 重启服务
restart_services() {
    stop_services
    sleep 2
    start_local
}

# 清理数据
clean_data() {
    print_header "清理数据"
    
    print_warning "此操作将删除所有数据和日志！"
    read -p "确认继续？(yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        # 停止服务
        stop_services
        
        print_info "清理数据目录..."
        rm -rf docker/mysql/data/*
        rm -rf docker/redis/data/*
        rm -rf docker/minio/data/*
        rm -rf docker/prometheus/data/*
        rm -rf docker/grafana/data/*
        rm -rf logs/*
        
        print_success "数据清理完成"
    else
        print_info "操作已取消"
    fi
    
    echo ""
}

# 本地开发模式
start_local() {
    print_header "本地开发模式启动"
    
    # 检查依赖
    check_dependencies
    
    # 初始化环境
    init_environment
    
    # 安装依赖
    install_backend_deps
    install_frontend_deps
    
    # 启动数据库（可选，使用远程数据库则跳过）
    # start_database
    
    # 运行迁移
    run_migrations
    
    # 启动后端
    start_backend
    
    # 启动前端
    start_frontend
    
    # 显示访问信息
    print_header "启动完成"
    echo -e "${GREEN}访问地址:${NC}"
    echo -e "  ${CYAN}前端界面:${NC} http://localhost:3000"
    echo -e "  ${CYAN}API 文档:${NC} http://localhost:8000/docs"
    echo -e "  ${CYAN}后端日志:${NC} tail -f logs/backend.log"
    echo -e "  ${CYAN}前端日志:${NC} tail -f logs/frontend.log"
    echo ""
    echo -e "${GREEN}常用命令:${NC}"
    echo -e "  ${CYAN}停止服务:${NC} $0 --stop"
    echo -e "  ${CYAN}查看日志:${NC} tail -f logs/backend.log"
    echo -e "  ${CYAN}重启服务:${NC} $0 --restart"
    echo ""
}

# 显示服务状态
show_status() {
    print_header "服务状态"
    
    # 检查后端
    if [ -f "logs/backend.pid" ]; then
        local pid=$(cat logs/backend.pid)
        if kill -0 $pid 2>/dev/null; then
            print_success "后端服务运行中 (PID: $pid)"
        else
            print_error "后端服务未运行"
        fi
    else
        print_warning "后端服务未启动"
    fi
    
    # 检查前端
    if [ -f "logs/frontend.pid" ]; then
        local pid=$(cat logs/frontend.pid)
        if kill -0 $pid 2>/dev/null; then
            print_success "前端服务运行中 (PID: $pid)"
        else
            print_error "前端服务未运行"
        fi
    else
        print_warning "前端服务未启动"
    fi
    
    # 检查 Docker 服务
    if command -v docker-compose &> /dev/null; then
        if docker-compose ps --quiet 2>/dev/null | grep -q .; then
            print_success "Docker 服务运行中"
            docker-compose ps
        fi
    fi
    
    echo ""
}

# 解析参数
MODE="local"
ACTION="start"

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -b|--backend)
            ACTION="backend"
            shift
            ;;
        -f|--frontend)
            ACTION="frontend"
            shift
            ;;
        -d|--database)
            ACTION="database"
            shift
            ;;
        -s|--stop)
            ACTION="stop"
            shift
            ;;
        -r|--restart)
            ACTION="restart"
            shift
            ;;
        -c|--clean)
            ACTION="clean"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 执行动作
case $ACTION in
    start)
        if [ "$MODE" = "docker" ]; then
            start_docker
        else
            start_local
        fi
        ;;
    backend)
        install_backend_deps
        run_migrations
        start_backend
        ;;
    frontend)
        install_frontend_deps
        start_frontend
        ;;
    database)
        start_database
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    clean)
        clean_data
        ;;
    status)
        show_status
        ;;
esac
