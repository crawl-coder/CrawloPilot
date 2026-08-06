#!/bin/bash

# CrawloPilot 快速启动脚本（优化版）
# 一键启动前后端服务
# 支持: 命令行参数、conda 环境检测、PID 管理、健康检查、环境选择

set -e

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 默认配置
MODE="start"
USE_CONDA=true
ENV_FILE=".env"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --stop|-s)   MODE="stop"; shift ;;
        --restart|-r) MODE="restart"; shift ;;
        --local|-l)  ENV_FILE=".env.example.local"; shift ;;
        --remote|-p) ENV_FILE=".env.example"; shift ;;
        --no-conda)  USE_CONDA=false; shift ;;
        --help|-h)
            echo "用法: ./start-dev.sh [选项]"
            echo ""
            echo "选项:"
            echo "  -s, --stop      停止服务"
            echo "  -r, --restart   重启服务"
            echo "  -l, --local     使用本地配置 (.env.example.local)"
            echo "  -p, --remote    使用远程配置 (.env.example) [默认]"
            echo "  --no-conda      不使用 conda 虚拟环境"
            echo "  -h, --help      显示帮助"
            exit 0 ;;
        *) echo "未知参数: $1 (使用 -h 查看帮助)"; exit 1 ;;
    esac
done

# 日志目录
mkdir -p logs

# ====== 辅助函数 ======

stop_service() {
    local name=$1
    local pidfile="logs/${name}.pid"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            sleep 1
            # 强制杀死
            kill -9 "$pid" 2>/dev/null || true
            echo -e "  ${YELLOW}已停止 $name (PID: $pid)${NC}"
        else
            echo -e "  ${YELLOW}$name 进程不存在 (PID: $pid)${NC}"
        fi
        rm -f "$pidfile"
    else
        echo -e "  ${YELLOW}$name PID 文件不存在${NC}"
    fi
}

check_port() {
    local port=$1
    if lsof -ti:"$port" >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=${3:-15}
    echo -n "  等待 $name 就绪..."
    for i in $(seq 1 "$max_attempts"); do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo -e " ${GREEN}OK${NC}"
            return 0
        fi
        sleep 1
        echo -n "."
    done
    echo -e " ${RED}超时${NC}"
    return 1
}

activate_conda() {
    if [ "$USE_CONDA" = true ]; then
        local conda_sh=""
        # 查找 conda
        for candidate in \
            "$HOME/software/miniconda3/etc/profile.d/conda.sh" \
            "$HOME/miniconda3/etc/profile.d/conda.sh" \
            "$HOME/anaconda3/etc/profile.d/conda.sh" \
            "/opt/miniconda3/etc/profile.d/conda.sh"; do
            if [ -f "$candidate" ]; then
                conda_sh="$candidate"
                break
            fi
        done

        if [ -n "$conda_sh" ]; then
            # shellcheck disable=SC1090
            source "$conda_sh"
            conda activate crawlo_pilot 2>/dev/null && \
                echo -e "  ${GREEN}conda: crawlo_pilot${NC}" || \
                echo -e "  ${YELLOW}conda: crawlo_pilot 未找到，使用系统 Python${NC}"
        else
            echo -e "  ${YELLOW}conda 未找到，使用系统 Python${NC}"
        fi
    fi
}

setup_env() {
    if [ ! -f .env ]; then
        echo "  创建 .env (来源: $ENV_FILE)..."
        cp "$ENV_FILE" .env
    fi
}

# ====== 命令处理 ======

case "$MODE" in
    stop)
        echo -e "${CYAN}=========================================${NC}"
        echo -e "${CYAN}  CrawloPilot 停止服务${NC}"
        echo -e "${CYAN}=========================================${NC}"
        stop_service backend
        stop_service frontend
        echo -e "${GREEN}  全部停止${NC}"
        exit 0
        ;;
    restart)
        echo -e "${CYAN}=========================================${NC}"
        echo -e "${CYAN}  CrawloPilot 重启服务${NC}"
        echo -e "${CYAN}=========================================${NC}"
        stop_service backend
        stop_service frontend
        echo ""
        # 继续启动流程
        ;;
esac

# ====== 启动流程 ======

echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}  CrawloPilot 快速启动${NC}"
echo -e "${CYAN}=========================================${NC}"
echo ""

# 1. 环境检查
echo -e "${BLUE}[1/7]${NC} 检查环境..."
setup_env
activate_conda

# 2. 检查依赖
echo -e "${BLUE}[2/7]${NC} 检查后端依赖..."
cd backend
if [ "$USE_CONDA" = true ]; then
    pip install -r requirements.txt -q 2>/dev/null || \
        echo -e "  ${YELLOW}部分依赖安装失败（可能已存在）${NC}"
else
    pip3 install -r requirements.txt -q 2>/dev/null || true
fi
echo -e "${GREEN}  ✓ 后端依赖就绪${NC}"

# 3. 前端依赖
echo -e "${BLUE}[3/7]${NC} 检查前端依赖..."
cd ../frontend
if [ ! -d "node_modules" ]; then
    echo "  安装前端依赖..."
    npm install --silent
fi
echo -e "${GREEN}  ✓ 前端依赖就绪${NC}"

# 4. 数据库初始化
echo -e "${BLUE}[4/7]${NC} 初始化数据库..."
cd ../backend
alembic upgrade head 2>/dev/null || echo -e "  ${YELLOW}迁移跳过（可能已是最新）${NC}"
python init_db.py 2>/dev/null || true
echo -e "${GREEN}  ✓ 数据库就绪${NC}"

# 5. 清理旧进程
echo -e "${BLUE}[5/7]${NC} 清理旧进程..."
# 检查 8000 端口
if check_port 8000; then
    echo "  停止旧后端进程..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi
if check_port 3000; then
    echo "  停止旧前端进程..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi
echo -e "${GREEN}  ✓ 端口已释放${NC}"

# 6. 启动后端
echo -e "${BLUE}[6/7]${NC} 启动后端服务..."
# 使用 nohup 启动，确保 conda 环境继承
PYTHON_BIN=$(which python)
# watchfiles 返回绝对路径，reload-exclude 必须用绝对路径才能匹配（uvicorn 0.27）
RELOAD_EXCLUDE_UPLOADS="$(pwd)/uploads"
nohup "$PYTHON_BIN" -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir app \
    --reload-exclude "$RELOAD_EXCLUDE_UPLOADS" \
    > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid

# 等待后端就绪
if wait_for_service "http://localhost:8000/health" "后端" 20; then
    echo -e "${GREEN}  ✓ 后端已启动 (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}  ✗ 后端启动失败，查看日志: tail -f logs/backend.log${NC}"
    exit 1
fi

# 7. 启动前端
echo -e "${BLUE}[7/7]${NC} 启动前端服务..."
cd ../frontend
nohup npm run dev \
    > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid

# 等待前端就绪
if wait_for_service "http://localhost:3000" "前端" 15; then
    echo -e "${GREEN}  ✓ 前端已启动 (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${YELLOW}  ⚠ 前端可能仍在编译中${NC}"
fi

# 完成
echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${GREEN}  启动完成！${NC}"
echo -e "${CYAN}=========================================${NC}"
echo ""
echo -e "${GREEN}访问地址:${NC}"
echo -e "  ${CYAN}前端界面:${NC} http://localhost:3000"
echo -e "  ${CYAN}API 文档:${NC} http://localhost:8000/docs"
echo -e "  ${CYAN}健康检查:${NC} http://localhost:8000/health"
echo ""
echo -e "${GREEN}日志:${NC}"
echo -e "  ${CYAN}tail -f logs/backend.log${NC}"
echo -e "  ${CYAN}tail -f logs/frontend.log${NC}"
echo ""
echo -e "${GREEN}停止服务:${NC}"
echo -e "  ${CYAN}./start-dev.sh --stop${NC}"
echo ""
