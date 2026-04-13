#!/usr/bin/env python3
"""
添加缺失的数据库列
"""

import sys
sys.path.insert(0, '/Users/oscar/projects/CrawloPilot/backend')

from sqlalchemy import create_engine, text
from app.core.config import settings

# 创建数据库连接
engine = create_engine(settings.DATABASE_URL)

columns_to_add = [
    {
        'table': 'task_instance',
        'column': 'spider_id',
        'definition': 'BIGINT COMMENT "爬虫 ID"',
        'check_sql': """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'task_instance' 
            AND COLUMN_NAME = 'spider_id'
        """
    },
    {
        'table': 'task_instance',
        'column': 'pages_crawled',
        'definition': 'INT DEFAULT 0 COMMENT "已爬取页面数"',
        'check_sql': """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'task_instance' 
            AND COLUMN_NAME = 'pages_crawled'
        """
    },
    {
        'table': 'task_instance',
        'column': 'items_scraped',
        'definition': 'INT DEFAULT 0 COMMENT "已抓取数据数"',
        'check_sql': """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'task_instance' 
            AND COLUMN_NAME = 'items_scraped'
        """
    },
    {
        'table': 'task_instance',
        'column': 'errors_count',
        'definition': 'INT DEFAULT 0 COMMENT "错误数"',
        'check_sql': """
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'task_instance' 
            AND COLUMN_NAME = 'errors_count'
        """
    }
]

with engine.connect() as conn:
    for col_info in columns_to_add:
        # 检查列是否存在
        result = conn.execute(text(col_info['check_sql']))
        
        if result.fetchone():
            print(f"✅ {col_info['table']}.{col_info['column']} 已存在")
        else:
            print(f"➕ 添加 {col_info['table']}.{col_info['column']}...")
            conn.execute(text(f"""
                ALTER TABLE {col_info['table']} 
                ADD COLUMN {col_info['column']} {col_info['definition']}
            """))
            conn.commit()
            print(f"✅ {col_info['table']}.{col_info['column']} 添加成功")

print("\n✅ 所有列检查完成!")
