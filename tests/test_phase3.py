#!/usr/bin/env python3
"""
Phase 3 调度系统测试脚本
"""
import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")

def print_section(title):
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.END}")
    print(f"{Colors.YELLOW}{title}{Colors.END}")
    print(f"{Colors.YELLOW}{'='*60}{Colors.END}")

# 1. 登录获取 Token
print_section("1. 登录认证")
try:
    response = requests.post(f"{BASE_URL}{API_PREFIX}/auth/login", data={
        "username": "admin",
        "password": "admin123"
    })
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print_success("登录成功")
    else:
        print_error(f"登录失败: {response.status_code}")
        exit(1)
except Exception as e:
    print_error(f"登录异常: {e}")
    exit(1)

# 2. 创建调度配置
print_section("2. 创建调度配置")

# 2.1 创建 Cron 调度
print_info("创建 Cron 调度...")
cron_schedule = {
    "project_id": 1,
    "spider_name": "test_cron_spider",
    "schedule_type": "cron",
    "cron_expr": "*/5 * * * *",
    "priority": 5,
    "max_concurrency": 1,
    "timeout_seconds": 3600,
    "enabled": True
}

response = requests.post(f"{BASE_URL}{API_PREFIX}/schedules/", 
                        json=cron_schedule, headers=headers)
if response.status_code == 200:
    cron_schedule_id = response.json()["id"]
    print_success(f"Cron 调度创建成功 (ID: {cron_schedule_id})")
else:
    print_error(f"Cron 调度创建失败: {response.status_code} - {response.text}")
    cron_schedule_id = None

time.sleep(1)

# 2.2 创建 Interval 调度
print_info("创建 Interval 调度...")
interval_schedule = {
    "project_id": 1,
    "spider_name": "test_interval_spider",
    "schedule_type": "interval",
    "interval_seconds": 300,
    "priority": 5,
    "max_concurrency": 1,
    "timeout_seconds": 3600,
    "enabled": True
}

response = requests.post(f"{BASE_URL}{API_PREFIX}/schedules/", 
                        json=interval_schedule, headers=headers)
if response.status_code == 200:
    interval_schedule_id = response.json()["id"]
    print_success(f"Interval 调度创建成功 (ID: {interval_schedule_id})")
else:
    print_error(f"Interval 调度创建失败: {response.status_code} - {response.text}")
    interval_schedule_id = None

# 3. 查询调度列表
print_section("3. 查询调度列表")
response = requests.get(f"{BASE_URL}{API_PREFIX}/schedules/", headers=headers)
if response.status_code == 200:
    schedules = response.json()
    print_success(f"查询成功，共 {len(schedules)} 个调度")
    for s in schedules:
        print(f"  - ID: {s['id']}, 类型: {s['schedule_type']}, 爬虫: {s['spider_name']}")
else:
    print_error(f"查询失败: {response.status_code}")

# 4. 测试调度操作
if cron_schedule_id:
    print_section("4. 调度操作测试")
    
    # 4.1 禁用调度
    print_info("禁用调度...")
    response = requests.post(f"{BASE_URL}{API_PREFIX}/schedules/{cron_schedule_id}/disable", 
                            headers=headers)
    if response.status_code == 200:
        print_success("调度禁用成功")
    else:
        print_error(f"禁用失败: {response.status_code}")
    
    time.sleep(0.5)
    
    # 4.2 启用调度
    print_info("启用调度...")
    response = requests.post(f"{BASE_URL}{API_PREFIX}/schedules/{cron_schedule_id}/enable", 
                            headers=headers)
    if response.status_code == 200:
        print_success("调度启用成功")
    else:
        print_error(f"启用失败: {response.status_code}")
    
    time.sleep(0.5)
    
    # 4.3 手动触发
    print_info("手动触发调度...")
    response = requests.post(f"{BASE_URL}{API_PREFIX}/schedules/{cron_schedule_id}/trigger", 
                            headers=headers)
    if response.status_code == 200:
        print_success("调度触发成功")
    else:
        print_error(f"触发失败: {response.status_code}")

# 5. 查询任务实例
print_section("5. 查询任务实例")
time.sleep(2)  # 等待任务创建

response = requests.get(f"{BASE_URL}{API_PREFIX}/task-instances/", 
                       headers=headers, params={"limit": 10})
if response.status_code == 200:
    tasks = response.json()
    print_success(f"查询成功，共 {len(tasks)} 个任务实例")
    for t in tasks:
        print(f"  - ID: {t['id']}, 状态: {t['status']}, 爬虫: {t['spider_name']}")
else:
    print_error(f"查询失败: {response.status_code}")

# 6. 查询任务统计
print_section("6. 查询任务统计")
response = requests.get(f"{BASE_URL}{API_PREFIX}/task-instances/stats/summary", 
                       headers=headers)
if response.status_code == 200:
    stats = response.json()
    print_success("统计查询成功")
    print(f"  - 总数: {stats.get('total', 0)}")
    print(f"  - 成功: {stats.get('success', 0)}")
    print(f"  - 失败: {stats.get('failed', 0)}")
    print(f"  - 运行中: {stats.get('running', 0)}")
    print(f"  - 成功率: {stats.get('success_rate', 0):.2f}%")
else:
    print_error(f"查询失败: {response.status_code}")

# 7. 测试任务操作
if tasks:
    print_section("7. 任务操作测试")
    task_id = tasks[0]['id']
    
    # 7.1 查看任务详情
    print_info(f"查看任务 {task_id} 详情...")
    response = requests.get(f"{BASE_URL}{API_PREFIX}/task-instances/{task_id}", 
                           headers=headers)
    if response.status_code == 200:
        task = response.json()
        print_success("详情查询成功")
        print(f"  - 状态: {task['status']}")
        print(f"  - 爬虫: {task['spider_name']}")
    else:
        print_error(f"查询失败: {response.status_code}")
    
    time.sleep(0.5)
    
    # 7.2 重试任务（如果失败）
    if task['status'] in ['failed', 'timeout']:
        print_info("重试任务...")
        response = requests.post(f"{BASE_URL}{API_PREFIX}/task-instances/{task_id}/retry", 
                                headers=headers)
        if response.status_code == 200:
            print_success("任务重试成功")
        else:
            print_error(f"重试失败: {response.status_code}")

# 8. 测试 API 文档
print_section("8. API 文档检查")
response = requests.get(f"{BASE_URL}/docs")
if response.status_code == 200:
    print_success("API 文档可访问")
else:
    print_error(f"API 文档不可访问: {response.status_code}")

# 9. 健康检查
print_section("9. 健康检查")
response = requests.get(f"{BASE_URL}/health")
if response.status_code == 200:
    health = response.json()
    print_success(f"服务健康: {health['status']}")
else:
    print_error(f"健康检查失败: {response.status_code}")

# 总结
print_section("测试总结")
print_info("Phase 3 调度系统测试完成！")
print_info("请访问以下地址查看结果：")
print(f"  - 调度管理: http://localhost:3000/schedules")
print(f"  - 任务实例: http://localhost:3000/tasks")
print(f"  - API 文档: {BASE_URL}/docs")
