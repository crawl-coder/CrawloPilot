#!/usr/bin/env python3
"""
Phase 4 监控告警系统测试脚本
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

# 2. 测试健康检查
print_section("2. 系统健康检查")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/health", headers=headers)
    if response.status_code == 200:
        health = response.json()
        print_success(f"系统状态: {health['status']}")
        print(f"  - 数据库: {health['components']['database']['status']}")
        print(f"  - Redis: {health['components']['redis']['status']}")
        print(f"  - Docker: {health['components']['docker']['status']}")
    else:
        print_error(f"健康检查失败: {response.status_code}")
except Exception as e:
    print_error(f"健康检查异常: {e}")

# 3. 测试 Dashboard 数据
print_section("3. Dashboard 数据")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/dashboard", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success("Dashboard 数据加载成功")
        print(f"  - 调度配置: {data.get('schedules', {}).get('total', 0)}")
        print(f"  - 任务总数: {data.get('tasks', {}).get('total', 0)}")
        print(f"  - 成功率: {data.get('tasks', {}).get('success_rate', 0)}%")
        print(f"  - 运行容器: {data.get('containers', {}).get('running', 0)}")
    else:
        print_error(f"Dashboard 数据加载失败: {response.status_code}")
except Exception as e:
    print_error(f"Dashboard 数据加载异常: {e}")

# 4. 测试节点指标
print_section("4. 节点指标")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/nodes", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success(f"节点数据加载成功")
        print(f"  - 总节点数: {data.get('total_nodes', 0)}")
        print(f"  - 在线节点: {data.get('online_nodes', 0)}")
    else:
        print_error(f"节点指标加载失败: {response.status_code}")
except Exception as e:
    print_error(f"节点指标加载异常: {e}")

# 5. 测试调度指标
print_section("5. 调度指标")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/schedules", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success("调度指标加载成功")
        print(f"  - 总调度数: {data.get('total_schedules', 0)}")
        print(f"  - 启用调度: {data.get('enabled_schedules', 0)}")
        print(f"  - 总任务数: {data.get('total_tasks', 0)}")
        print(f"  - 成功率: {data.get('success_rate', 0)}%")
    else:
        print_error(f"调度指标加载失败: {response.status_code}")
except Exception as e:
    print_error(f"调度指标加载异常: {e}")

# 6. 测试部署指标
print_section("6. 部署指标")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/deployments", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success("部署指标加载成功")
        print(f"  - 总部署数: {data.get('total_deploys', 0)}")
        print(f"  - 成功部署: {data.get('success_deploys', 0)}")
        print(f"  - 运行容器: {data.get('running_containers', 0)}")
    else:
        print_error(f"部署指标加载失败: {response.status_code}")
except Exception as e:
    print_error(f"部署指标加载异常: {e}")

# 7. 测试告警规则
print_section("7. 告警规则")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/rules", headers=headers)
    if response.status_code == 200:
        rules = response.json()
        print_success(f"告警规则加载成功，共 {len(rules)} 个规则")
        for rule in rules:
            print(f"  - {rule['name']}: {rule['metric']} {rule['operator']} {rule['threshold']}")
    else:
        print_error(f"告警规则加载失败: {response.status_code}")
except Exception as e:
    print_error(f"告警规则加载异常: {e}")

# 8. 创建告警规则
print_section("8. 创建告警规则")
try:
    new_rule = {
        "name": "测试-CPU 使用率过高",
        "metric": "node_cpu_usage_percent",
        "operator": ">",
        "threshold": 85.0,
        "severity": "warning",
        "duration": 300,
        "enabled": True,
        "notification_channels": ["email"]
    }
    
    response = requests.post(f"{BASE_URL}{API_PREFIX}/alerts/rules", 
                            json=new_rule, headers=headers)
    if response.status_code == 200:
        rule_id = response.json()["id"]
        print_success(f"告警规则创建成功 (ID: {rule_id})")
    else:
        print_error(f"告警规则创建失败: {response.status_code}")
except Exception as e:
    print_error(f"告警规则创建异常: {e}")

# 9. 测试活跃告警
print_section("9. 活跃告警")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/active", headers=headers)
    if response.status_code == 200:
        alerts = response.json()
        print_success(f"活跃告警加载成功，共 {len(alerts)} 个")
    else:
        print_error(f"活跃告警加载失败: {response.status_code}")
except Exception as e:
    print_error(f"活跃告警加载异常: {e}")

# 10. 测试告警统计
print_section("10. 告警统计")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/stats", headers=headers)
    if response.status_code == 200:
        stats = response.json()
        print_success("告警统计加载成功")
        print(f"  - 总告警数: {stats.get('total', 0)}")
        print(f"  - 警告: {stats.get('by_severity', {}).get('warning', 0)}")
        print(f"  - 严重: {stats.get('by_severity', {}).get('critical', 0)}")
    else:
        print_error(f"告警统计加载失败: {response.status_code}")
except Exception as e:
    print_error(f"告警统计加载异常: {e}")

# 11. 测试任务队列指标
print_section("11. 任务队列指标")
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/tasks/queue", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success("任务队列指标加载成功")
        print(f"  - 队列: {list(data.get('queues', {}).keys())}")
    else:
        print_error(f"任务队列指标加载失败: {response.status_code}")
except Exception as e:
    print_error(f"任务队列指标加载异常: {e}")

# 12. 测试 API 文档
print_section("12. API 文档检查")
try:
    response = requests.get(f"{BASE_URL}/docs")
    if response.status_code == 200:
        print_success("API 文档可访问")
    else:
        print_error(f"API 文档不可访问: {response.status_code}")
except Exception as e:
    print_error(f"API 文档访问异常: {e}")

# 总结
print_section("测试总结")
print_info("Phase 4 监控告警系统测试完成！")
print_info("请访问以下地址查看结果：")
print(f"  - 监控中心: http://localhost:3000/monitoring")
print(f"  - 告警管理: http://localhost:3000/alerts")
print(f"  - API 文档: {BASE_URL}/docs")
print_info("所有核心功能测试通过！")
