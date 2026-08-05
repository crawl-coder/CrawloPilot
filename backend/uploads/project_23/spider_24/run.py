#!/usr/bin/env python3
"""简化测试爬虫 - 用于 CrawloPilot 本地执行测试"""

import time
import sys
from datetime import datetime

def log(level, msg):
    """输出 Crawlo 格式的日志"""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{ts} [{level}] {msg}", flush=True)

def main():
    spider_name = "test_spider"
    
    log("INFO", f"Spider {spider_name} started")
    log("INFO", "=" * 60)
    log("INFO", f"任务 ID: {__import__('os').environ.get('TASK_ID', 'N/A')}")
    log("INFO", f"爬虫名称: {spider_name}")
    
    total_pages = 5
    total_items = 20
    
    for i in range(1, total_pages + 1):
        items_this_page = i * 4
        log("INFO", f"Crawled {i} pages, {items_this_page} items")
        
        # 模拟爬取延迟
        time.sleep(1)
        
        if i == 3:
            log("WARNING", "模拟一次重试...")
    
    log("INFO", "=" * 60)
    log("INFO", f"Spider {spider_name} finished")
    log("INFO", f"总计: {total_pages} pages, {total_items} items")

if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        log("WARNING", "Spider interrupted by user")
        sys.exit(130)
    except Exception as e:
        log("ERROR", f"Spider failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
