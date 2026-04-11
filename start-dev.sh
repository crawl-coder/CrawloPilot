#!/bin/bash

# CrawloPilot 快速启动脚本（简化版）
# 一键启动前后端服务

set -e

# 颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}  CrawloPilot 快速启动${NC}"
echo -e "${CYAN}=========================================${NC}"
echo ""

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 创建日志目录
mkdir -p logs

# 1. 检查环境
echo -e "${BLUE}[1/5]${NC} 检查环境..."
if [ ! -f .env ]; then
    echo "  创建 .env 文件..."
    cp .env.example .env
fi
echo -e "${GREEN}  ✓ 环境检查完成${NC}"

# 2. 安装后端依赖
echo -e "${BLUE}[2/5]${NC} 检查后端依赖..."
cd backend
pip3 install -r requirements.txt -q 2>/dev/null || true
echo -e "${GREEN}  ✓ 后端依赖就绪${NC}"

# 3. 安装前端依赖
echo -e "${BLUE}[3/5]${NC} 检查前端依赖..."
cd ../frontend
if [ ! -d "node_modules" ]; then
    echo "  安装前端依赖..."
    npm install --silent
fi
echo -e "${GREEN}  ✓ 前端依赖就绪${NC}"

# 4. 启动后端
echo -e "${BLUE}[4/6]${NC} 初始化数据库..."
cd ../backend

# 运行数据库迁移
alembic upgrade head 2>/dev/null || true

# 运行数据库初始化（创建默认管理员账号）
python init_db.py 2>/dev/null || true

echo -e "${BLUE}[5/6]${NC} 启动后端服务..."

# 启动 uvicorn
nohup uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > ../logs/backend.log 2>&1 &

BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid
echo -e "${GREEN}  ✓ 后端已启动 (PID: $BACKEND_PID)${NC}"

# 5. 启动前端
echo -e "${BLUE}[6/6]${NC} 启动前端服务..."
cd ../frontend

nohup npm run dev \
    > ../logs/frontend.log 2>&1 &

FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid
echo -e "${GREEN}  ✓ 前端已启动 (PID: $FRONTEND_PID)${NC}"

# 完成
echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${GREEN}  启动完成！${NC}"
echo -e "${CYAN}=========================================${NC}"
echo ""
echo -e "${GREEN}访问地址:${NC}"
echo -e "  ${CYAN}前端界面:${NC} http://localhost:3000"
echo -e "  ${CYAN}API 文档:${NC} http://localhost:8000/docs"
echo ""
echo -e "${GREEN}查看日志:${NC}"
echo -e "  ${CYAN}后端日志:${NC} tail -f logs/backend.log"
echo -e "  ${CYAN}前端日志:${NC} tail -f logs/frontend.log"
echo ""
echo -e "${GREEN}停止服务:${NC}"
echo -e "  ${CYAN}./dev.sh --stop${NC}"
echo ""
