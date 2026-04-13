#!/bin/bash
# CrawloPilot Spider Runner Entrypoint
# 容器启动脚本

set -e

echo "========================================="
echo "  CrawloPilot Spider Runner v1.0.0"
echo "========================================="
echo ""

# ========== 环境变量验证 ==========
echo "[1/6] 验证环境变量..."

if [ -z "$TASK_ID" ]; then
    echo "❌ 错误: TASK_ID 环境变量未设置"
    exit 1
fi

if [ -z "$API_URL" ]; then
    echo "❌ 错误: API_URL 环境变量未设置"
    exit 1
fi

if [ -z "$SPIDER_NAME" ]; then
    echo "❌ 错误: SPIDER_NAME 环境变量未设置"
    exit 1
fi

echo "✓ Task ID: $TASK_ID"
echo "✓ API URL: $API_URL"
echo "✓ Spider: $SPIDER_NAME"
echo "✓ Git URL: ${GIT_URL:-'未设置'}"
echo ""

# ========== 准备工作目录 ==========
echo "[2/6] 准备工作目录..."

mkdir -p ${OUTPUT_PATH:-/output}
mkdir -p /logs
mkdir -p /app

echo "✓ 输出目录: ${OUTPUT_PATH:-/output}"
echo "✓ 日志目录: /logs"
echo ""

# ========== 拉取爬虫代码 ==========
echo "[3/6] 拉取爬虫代码..."

if [ -n "$GIT_URL" ]; then
    echo "从 Git 仓库拉取代码..."
    echo "仓库: $GIT_URL"
    echo "分支: ${GIT_BRANCH:-main}"
    
    # 克隆代码
    if [ -d "/app/.git" ]; then
        cd /app
        git pull origin ${GIT_BRANCH:-main}
    else
        git clone --depth 1 --branch ${GIT_BRANCH:-main} "$GIT_URL" /app
    fi
    
    echo "✓ 代码拉取成功"
else
    echo "⚠ 未设置 GIT_URL,使用已有代码"
fi
echo ""

# ========== 安装依赖 ==========
echo "[4/6] 安装项目依赖..."

if [ -f "/app/requirements.txt" ]; then
    echo "安装 requirements.txt..."
    pip install -r /app/requirements.txt --quiet
    echo "✓ 依赖安装完成"
else
    echo "⚠ 未找到 requirements.txt,跳过"
fi
echo ""

# ========== 注入 SDK 配置 ==========
echo "[5/6] 注入 CrawloPilot SDK 配置..."

# 创建 CrawloPilot 配置文件
cat > /app/crawlopilot_config.py << EOF
"""
CrawloPilot SDK 自动配置
此文件由 entrypoint.sh 自动生成
"""

from crawlopilot.core.config import Config
from crawlopilot.core.client import CrawloPilotClient
from crawlopilot.core.context import TaskContext, TaskStatus

# 初始化配置
config = Config(
    api_url="$API_URL",
    api_token="$API_TOKEN",
    task_id="$TASK_ID"
)

# 初始化客户端
client = CrawloPilotClient(config)

# 初始化任务上下文
context = TaskContext(
    task_id="$TASK_ID",
    spider_name="$SPIDER_NAME",
    node_id="${NODE_ID:-}",
    container_id="${CONTAINER_ID:-}"
)

# Scrapy 配置
CRAWLOPILOT_CLIENT = client
CRAWLOPILOT_CONTEXT = context

# 自动注入中间件和管道
DOWNLOADER_MIDDLEWARES = {
    'crawlopilot.middleware.scrapy.ScrapyMiddleware': 543,
}

ITEM_PIPELINES = {
    'crawlopilot.pipeline.item.ItemPipeline': 300,
}

EXTENSIONS = {
    'crawlopilot.extensions.heartbeat.HeartbeatExtension': 500,
    'crawlopilot.extensions.monitor.MonitorExtension': 501,
}

# 日志配置
LOG_LEVEL = "${LOG_LEVEL:-INFO}"
EOF

echo "✓ SDK 配置已注入到 /app/crawlopilot_config.py"
echo ""

# ========== 启动爬虫 ==========
echo "[6/6] 启动爬虫: $SPIDER_NAME"
echo "========================================="

cd /app

# 上报任务开始
python -c "
import os, sys
sys.path.insert(0, '/app')
from crawlopilot_config import client, context, TaskStatus
import asyncio

async def report_start():
    await client.initialize()
    await client.report_status(TaskStatus.RUNNING, {
        'container_id': os.environ.get('CONTAINER_ID', ''),
        'node_id': os.environ.get('NODE_ID', '')
    })
    await client.close()

asyncio.run(report_start())
" 2>/dev/null || echo "⚠ 状态上报失败,继续执行"

# 启动爬虫 (使用 SDK 配置)
echo ""
echo "执行命令: scrapy crawl $SPIDER_NAME -s LOG_FILE=/logs/spider.log"
echo ""

EXIT_CODE=0
scrapy crawl "$SPIDER_NAME" \
    -s LOG_FILE=/logs/spider.log \
    -s FEED_URI=${OUTPUT_PATH:-/output}/items.json \
    -s FEED_FORMAT=json \
    -s LOG_LEVEL=${LOG_LEVEL:-INFO} \
    || EXIT_CODE=$?

echo ""
echo "========================================="
echo "爬虫执行完成,退出码: $EXIT_CODE"
echo "========================================="

# ========== 收尾工作 ==========
echo ""
echo "[清理] 打包日志文件..."

# 打包日志
if [ -f "/logs/spider.log" ]; then
    tar -czf ${OUTPUT_PATH:-/output}/logs.tar.gz -C /logs spider.log
    echo "✓ 日志已打包: ${OUTPUT_PATH:-/output}/logs.tar.gz"
fi

# 保存配置
cp /app/crawlopilot_config.py ${OUTPUT_PATH:-/output}/config.py 2>/dev/null || true

# 上报任务完成
echo ""
echo "[上报] 发送完成状态..."

python -c "
import os, sys, json
sys.path.insert(0, '/app')
from crawlopilot_config import client, context, TaskStatus
from datetime import datetime
import asyncio

async def report_complete():
    await client.initialize()
    
    exit_code = $EXIT_CODE
    status = TaskStatus.SUCCESS if exit_code == 0 else TaskStatus.FAILED
    
    context.complete(status)
    
    await client.complete_task(status, context)
    await client.close()

asyncio.run(report_complete())
" 2>/dev/null || echo "⚠ 完成状态上报失败"

echo ""
echo "========================================="
echo "✓ CrawloPilot Spider Runner 执行完毕"
echo "========================================="

exit $EXIT_CODE
