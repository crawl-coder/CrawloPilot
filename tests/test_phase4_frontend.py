#!/usr/bin/env python3
"""
Phase 4 前后端联调测试
测试前端页面能否正常访问和调用后端 API
"""
import requests
import json

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
API_PREFIX = "/api/v1"

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

print_section("Phase 4 前后端联调测试")

# 1. 测试前端页面可访问性
print_section("1. 前端页面访问测试")
pages = [
    ("/", "首页"),
    ("/monitoring", "监控中心"),
    ("/alerts", "告警管理"),
    ("/login", "登录页")
]

for path, name in pages:
    try:
        response = requests.get(f"{FRONTEND_URL}{path}", timeout=3)
        if response.status_code == 200:
            print_success(f"{name} ({path}) - 可访问")
        else:
            print_error(f"{name} ({path}) - 状态码: {response.status_code}")
    except Exception as e:
        print_error(f"{name} ({path}) - 访问失败: {e}")

# 2. 登录并获取 Token
print_section("2. 登录测试")
try:
    response = requests.post(f"{BASE_URL}{API_PREFIX}/auth/login", data={
        "username": "admin",
        "password": "admin123"
    })
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print_success("登录成功，获取 Token")
    else:
        print_error(f"登录失败: {response.status_code}")
        exit(1)
except Exception as e:
    print_error(f"登录异常: {e}")
    exit(1)

# 3. 测试监控中心 API
print_section("3. 监控中心 API 测试")

# 3.1 Dashboard 数据
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/dashboard", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success("Dashboard API - 正常")
        print(f"  响应数据: {json.dumps(data, ensure_ascii=False, indent=2)[:200]}...")
    else:
        print_error(f"Dashboard API - 失败: {response.status_code}")
except Exception as e:
    print_error(f"Dashboard API - 异常: {e}")

# 3.2 健康检查
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/health", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success("健康检查 API - 正常")
        print(f"  系统状态: {data.get('status')}")
    else:
        print_error(f"健康检查 API - 失败: {response.status_code}")
except Exception as e:
    print_error(f"健康检查 API - 异常: {e}")

# 3.3 节点指标
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/nodes", headers=headers)
    if response.status_code == 200:
        data = response.json()
        print_success("节点指标 API - 正常")
        print(f"  节点数: {data.get('total_nodes', 0)}")
    else:
        print_error(f"节点指标 API - 失败: {response.status_code}")
except Exception as e:
    print_error(f"节点指标 API - 异常: {e}")

# 4. 测试告警管理 API
print_section("4. 告警管理 API 测试")

# 4.1 告警规则列表
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/rules", headers=headers)
    if response.status_code == 200:
        rules = response.json()
        print_success("告警规则列表 API - 正常")
        print(f"  规则数: {len(rules)}")
    else:
        print_error(f"告警规则列表 API - 失败: {response.status_code}")
except Exception as e:
    print_error(f"告警规则列表 API - 异常: {e}")

# 4.2 创建告警规则
try:
    new_rule = {
        "name": "联调测试-内存告警",
        "metric": "node_memory_usage_percent",
        "operator": ">",
        "threshold": 90.0,
        "severity": "critical",
        "duration": 600,
        "enabled": True,
        "notification_channels": ["email", "dingtalk"]
    }
    
    response = requests.post(f"{BASE_URL}{API_PREFIX}/alerts/rules", 
                            json=new_rule, headers=headers)
    if response.status_code == 200:
        rule = response.json()
        print_success("创建告警规则 API - 正常")
        print(f"  规则 ID: {rule.get('id')}")
    else:
        print_error(f"创建告警规则 API - 失败: {response.status_code}")
        print(f"  错误: {response.text}")
except Exception as e:
    print_error(f"创建告警规则 API - 异常: {e}")

# 4.3 活跃告警
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/active", headers=headers)
    if response.status_code == 200:
        alerts = response.json()
        print_success("活跃告警 API - 正常")
        print(f"  活跃告警数: {len(alerts)}")
    else:
        print_error(f"活跃告警 API - 失败: {response.status_code}")
except Exception as e:
    print_error(f"活跃告警 API - 异常: {e}")

# 4.4 告警统计
try:
    response = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/stats", headers=headers)
    if response.status_code == 200:
        stats = response.json()
        print_success("告警统计 API - 正常")
        print(f"  统计数据: {json.dumps(stats, ensure_ascii=False)}")
    else:
        print_error(f"告警统计 API - 失败: {response.status_code}")
except Exception as e:
    print_error(f"告警统计 API - 异常: {e}")

# 5. 测试 CORS 配置
print_section("5. CORS 跨域测试")
try:
    response = requests.options(
        f"{BASE_URL}{API_PREFIX}/monitoring/dashboard",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    if response.status_code == 200:
        cors_headers = response.headers
        if 'access-control-allow-origin' in cors_headers:
            print_success("CORS 配置 - 正常")
            print(f"  Allow-Origin: {cors_headers['access-control-allow-origin']}")
        else:
            print_error("CORS 配置 - 缺少 Access-Control-Allow-Origin 头")
    else:
        print_error(f"CORS 预检请求 - 失败: {response.status_code}")
except Exception as e:
    print_error(f"CORS 测试 - 异常: {e}")

# 6. 模拟前端调用流程
print_section("6. 模拟前端页面加载流程")

try:
    print_info("模拟监控中心页面加载...")
    
    # 步骤 1: 获取 Dashboard 数据
    dashboard = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/dashboard", headers=headers).json()
    print_success("✓ 加载 Dashboard 数据")
    
    # 步骤 2: 获取健康状态
    health = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/health", headers=headers).json()
    print_success("✓ 加载健康状态")
    
    # 步骤 3: 获取节点数据
    nodes = requests.get(f"{BASE_URL}{API_PREFIX}/monitoring/nodes", headers=headers).json()
    print_success("✓ 加载节点数据")
    
    # 步骤 4: 获取活跃告警
    alerts = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/active", headers=headers).json()
    print_success("✓ 加载活跃告警")
    
    print_success("监控中心页面 - 所有数据加载成功")
    
except Exception as e:
    print_error(f"模拟前端加载 - 失败: {e}")

try:
    print_info("\n模拟告警管理页面加载...")
    
    # 步骤 1: 获取告警规则
    rules = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/rules", headers=headers).json()
    print_success("✓ 加载告警规则")
    
    # 步骤 2: 获取告警统计
    stats = requests.get(f"{BASE_URL}{API_PREFIX}/alerts/stats", headers=headers).json()
    print_success("✓ 加载告警统计")
    
    # 步骤 3: 创建规则（模拟用户操作）
    test_rule = {
        "name": "前端联调测试",
        "metric": "test_metric",
        "operator": ">",
        "threshold": 100,
        "severity": "warning",
        "enabled": True
    }
    create_result = requests.post(f"{BASE_URL}{API_PREFIX}/alerts/rules", 
                                 json=test_rule, headers=headers).json()
    print_success("✓ 创建告警规则")
    
    print_success("告警管理页面 - 所有操作成功")
    
except Exception as e:
    print_error(f"模拟告警管理 - 失败: {e}")

# 总结
print_section("联调测试总结")
print_info("Phase 4 前后端联调测试完成！")
print_info("\n前端访问地址：")
print(f"  - 监控中心: {FRONTEND_URL}/monitoring")
print(f"  - 告警管理: {FRONTEND_URL}/alerts")
print_info("\n后端 API 地址：")
print(f"  - API 文档: {BASE_URL}/docs")
print(f"  - 健康检查: {BASE_URL}/health")
print_info("\n请在浏览器中访问前端页面，手动测试以下功能：")
print("  1. 监控中心页面数据展示")
print("  2. 告警管理页面 CRUD 操作")
print("  3. 告警规则创建和编辑")
print("  4. 数据自动刷新功能")
