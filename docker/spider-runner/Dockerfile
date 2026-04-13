# CrawloPilot Spider Runner Docker Image
# 标准爬虫运行环境

FROM python:3.10-slim

LABEL maintainer="CrawloPilot Team <dev@crawlopilot.com>"
LABEL description="CrawloPilot Spider Runner - Standard execution environment"
LABEL version="1.0.0"

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # SDK 配置
    API_URL="" \
    API_TOKEN="" \
    TASK_ID="" \
    SPIDER_NAME="" \
    GIT_URL="" \
    GIT_BRANCH="main" \
    # 爬虫配置
    OUTPUT_FORMAT="json" \
    OUTPUT_PATH="/output" \
    LOG_LEVEL="INFO"

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    build-essential \
    # 清理缓存
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 SDK
COPY sdk/ /tmp/sdk/

# 安装 SDK 和基础依赖
RUN pip install /tmp/sdk/ && \
    pip install scrapy crawlo && \
    rm -rf /tmp/sdk

# 创建必要目录
RUN mkdir -p /output /logs /app

# 复制启动脚本
COPY docker/spider-runner/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; assert os.environ.get('TASK_ID')" || exit 1

# 非 root 用户运行
RUN groupadd -r crawlopilot && useradd -r -g crawlopilot -d /app -s /bin/bash crawlopilot && \
    chown -R crawlopilot:crawlopilot /app /output /logs
USER crawlopilot

# 暴露端口 (可选,用于调试)
EXPOSE 8080

# 启动入口
ENTRYPOINT ["/entrypoint.sh"]
