#!/usr/bin/env python3
"""
Crawlo 爬虫启动脚本

由 CrawloPilot 平台在 Docker 容器中调用
支持从环境变量读取配置

环境变量:
    SPIDER_NAME: 爬虫名称 (必须)
    SPIDER_ARGS: 爬虫参数 (可选)
    API_URL: CrawloPilot API 地址 (可选)
    API_TOKEN: CrawloPilot API Token (可选)
    TASK_ID: 任务 ID (可选)
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_environment():
    """检查环境变量"""
    spider_name = os.environ.get('SPIDER_NAME')
    if not spider_name:
        logger.error("环境变量 SPIDER_NAME 未设置")
        sys.exit(1)
    
    logger.info(f"Spider Name: {spider_name}")
    logger.info(f"Spider Args: {os.environ.get('SPIDER_ARGS', '')}")
    logger.info(f"Task ID: {os.environ.get('TASK_ID', 'N/A')}")
    
    return spider_name


def load_spider_project():
    """
    加载爬虫项目
    
    CrawloPilot 会将爬虫代码挂载到 /spider/code 目录
    """
    code_dir = Path('/spider/code')
    
    if not code_dir.exists():
        logger.error(f"爬虫代码目录不存在: {code_dir}")
        sys.exit(1)
    
    # 添加到 Python 路径
    sys.path.insert(0, str(code_dir))
    
    logger.info(f"爬虫代码目录: {code_dir}")
    return code_dir


async def run_spider(spider_name: str):
    """
    运行爬虫
    
    支持两种方式:
    1. Crawlo 命令行: crawlo run spider_name (推荐)
    2. Python API: CrawlerProcess().crawl(spider_name)
    
    Args:
        spider_name: 爬虫名称
    """
    try:
        # 方式 1: 使用 crawlo 命令行 (推荐)
        logger.info(f"使用 crawlo 命令行启动: {spider_name}")
        
        import subprocess
        result = subprocess.run(
            ['crawlo', 'run', spider_name],
            cwd='/spider/code',  # 在爬虫项目目录运行
            capture_output=False,  # 不捕获,直接输出到 stdout
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"crawlo run 失败,退出码: {result.returncode}")
            sys.exit(result.returncode)
        
        logger.info(f"爬虫 {spider_name} 运行完成")
        
    except FileNotFoundError:
        # 方式 2: crawlo 命令行不存在,使用 Python API
        logger.warning("crawlo 命令行不可用,使用 Python API")
        
        from crawlo.crawler import CrawlerProcess
        
        logger.info(f"启动爬虫: {spider_name}")
        logger.info("=" * 60)
        
        # 创建爬虫进程
        process = CrawlerProcess()
        
        # 运行爬虫
        await process.crawl(spider_name)
        
        logger.info("=" * 60)
        logger.info(f"爬虫 {spider_name} 运行完成")
        
    except ImportError as e:
        logger.error(f"导入 Crawlo 框架失败: {e}")
        logger.error("请确保已安装 crawlo: pip install crawlo")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("爬虫被用户中断")
    except Exception as e:
        logger.error(f"爬虫运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    logger.info("CrawloPilot Spider Runner 启动")
    logger.info("=" * 60)
    
    # 检查环境
    spider_name = check_environment()
    
    # 加载项目
    load_spider_project()
    
    # 检查是否有指定的入口文件
    entry_file = os.environ.get('ENTRY_FILE')
    
    if entry_file:
        # 方式 1: 使用爬虫项目的入口文件 (优先级最高)
        logger.info(f"使用入口文件: {entry_file}")
        logger.info("=" * 60)
        
        entry_path = Path('/spider/code') / entry_file
        
        if not entry_path.exists():
            logger.error(f"入口文件不存在: {entry_path}")
            sys.exit(1)
        
        # 执行入口文件
        import subprocess
        
        if entry_file.endswith('.py'):
            # Python 文件: python run.py
            logger.info(f"执行: python {entry_file}")
            result = subprocess.run(
                ['python', entry_file],
                cwd='/spider/code',
                capture_output=False,
                text=True
            )
        elif entry_file.endswith('.sh'):
            # Shell 脚本: bash crawl.sh
            logger.info(f"执行: bash {entry_file}")
            result = subprocess.run(
                ['bash', entry_file],
                cwd='/spider/code',
                capture_output=False,
                text=True
            )
        else:
            logger.error(f"不支持的入口文件类型: {entry_file}")
            sys.exit(1)
        
        sys.exit(result.returncode)
    
    else:
        # 方式 2: 使用 crawlo 命令行 (默认)
        logger.info(f"使用 crawlo 命令行启动: {spider_name}")
        logger.info("=" * 60)
        
        asyncio.run(run_spider(spider_name))


if __name__ == '__main__':
    main()
