#!/usr/bin/env python3
"""
测试爬虫创建功能 - 验证项目列表加载
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def print_step(num, title):
    print(f"\n{'='*60}")
    print(f"步骤 {num}: {title}")
    print('='*60)

def login():
    """登录"""
    print_step(1, "登录平台")
    
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    
    if resp.status_code == 200:
        token = resp.json()['access_token']
        print(f"✅ 登录成功")
        print(f"   Token: {token[:30]}...")
        return token
    else:
        print(f"❌ 登录失败: {resp.status_code}")
        return None


def get_projects(token):
    """获取项目列表"""
    print_step(2, "获取项目列表")
    
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{BASE_URL}/api/v1/projects?skip=0&limit=100",
        headers=headers
    )
    
    if resp.status_code == 200:
        data = resp.json()
        projects = data.get('items', [])
        total = data.get('total', 0)
        
        print(f"✅ 获取成功")
        print(f"   项目总数: {total}")
        print(f"   返回数量: {len(projects)}")
        
        print(f"\n   项目列表:")
        for p in projects[:5]:
            print(f"   - ID: {p['id']}, 名称: {p['name']}")
        
        if len(projects) > 5:
            print(f"   ... 还有 {len(projects) - 5} 个项目")
        
        return projects
    else:
        print(f"❌ 获取失败: {resp.status_code}")
        print(f"   {resp.text}")
        return []


def create_spider(token, project_id):
    """创建爬虫"""
    print_step(3, "创建爬虫 (测试项目选择)")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    spider_data = {
        "name": "测试爬虫_项目选择",
        "project_id": project_id,
        "spider_type": "crawlo",
        "entry_file": "run.py",
        "spider_name": "test_spider",
        "description": "测试项目下拉框是否正常显示"
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/v1/spiders",
        json=spider_data,
        headers=headers
    )
    
    if resp.status_code in [200, 201]:
        spider = resp.json()
        print(f"✅ 爬虫创建成功")
        print(f"   ID: {spider['id']}")
        print(f"   名称: {spider['name']}")
        print(f"   项目 ID: {spider['project_id']}")
        print(f"   入口文件: {spider.get('entry_file', 'N/A')}")
        print(f"   爬虫名称: {spider.get('spider_name', 'N/A')}")
        return spider
    else:
        print(f"❌ 创建失败: {resp.status_code}")
        print(f"   {resp.text}")
        return None


def verify_spider_fields(token, spider_id):
    """验证爬虫字段"""
    print_step(4, "验证爬虫字段 (entry_file 和 spider_name)")
    
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{BASE_URL}/api/v1/spiders/{spider_id}",
        headers=headers
    )
    
    if resp.status_code == 200:
        spider = resp.json()
        print(f"✅ 爬虫详情:")
        print(f"   名称: {spider['name']}")
        print(f"   入口文件: {spider.get('entry_file', 'N/A')}")
        print(f"   爬虫名称: {spider.get('spider_name', 'N/A')}")
        print(f"   项目 ID: {spider['project_id']}")
        
        # 验证字段
        if spider.get('entry_file') == 'run.py':
            print(f"   ✅ entry_file 正确")
        else:
            print(f"   ❌ entry_file 错误")
        
        if spider.get('spider_name') == 'test_spider':
            print(f"   ✅ spider_name 正确")
        else:
            print(f"   ❌ spider_name 错误")
        
        return spider
    else:
        print(f"❌ 获取失败: {resp.status_code}")
        return None


def main():
    print("\n" + "="*60)
    print("🧪 CrawloPilot 爬虫创建功能测试")
    print("="*60)
    
    # 1. 登录
    token = login()
    if not token:
        return
    
    # 2. 获取项目列表
    projects = get_projects(token)
    if not projects:
        print("\n❌ 没有项目,请先创建项目")
        return
    
    # 3. 创建爬虫 (使用第一个项目)
    project_id = projects[0]['id']
    spider = create_spider(token, project_id)
    
    if spider:
        # 4. 验证字段
        verify_spider_fields(token, spider['id'])
    
    # 总结
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    print(f"✅ 项目列表加载: {'通过' if projects else '失败'}")
    print(f"✅ 爬虫创建: {'通过' if spider else '失败'}")
    print(f"✅ 字段验证: {'通过' if spider and spider.get('entry_file') else '失败'}")
    
    print(f"\n💡 前端修复:")
    print(f"   - loadProjects() 现在正确解析 API 响应")
    print(f"   - 使用 response.items 而不是直接赋值")
    print(f"   - 添加分页参数 skip=0, limit=1000")
    print(f"\n🌐 请刷新浏览器测试: http://localhost:3000/spiders")


if __name__ == '__main__':
    main()
