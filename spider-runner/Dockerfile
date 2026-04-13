FROM python:3.10-slim

LABEL maintainer="CrawloPilot Team"
LABEL description="CrawloPilot Spider Runner - Crawlo 爬虫运行环境"

# 设置工作目录
WORKDIR /spider

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 Crawlo 框架和常用依赖
RUN pip install --no-cache-dir \
    crawlo \
    aiomysql \
    asyncmy \
    PyMySQL

# 创建爬虫运行目录
RUN mkdir -p /spider/data /spider/logs /spider/output

# 复制爬虫启动脚本
COPY run_spider.py /spider/run_spider.py
RUN chmod +x /spider/run_spider.py

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SPIDER_NAME="" \
    SPIDER_ARGS="" \
    API_URL="" \
    API_TOKEN="" \
    TASK_ID=""

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import crawlo; print('Crawlo framework OK')" || exit 1

# 入口点
ENTRYPOINT ["python", "/spider/run_spider.py"]
