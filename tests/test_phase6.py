"""
Phase 6 测试脚本
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def login():
    """登录获取 token"""
    print("=" * 60)
    print("1. 登录获取 Token")
    print("=" * 60)
    
    response = requests.post(f"{BASE_URL}/auth/login", data={
        "username": "admin",
        "password": "admin123"
    })
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✓ 登录成功\n")
        return token
    else:
        print(f"✗ 登录失败: {response.text}")
        return None


def test_proxy_pool(token):
    """测试代理池 API"""
    print("=" * 60)
    print("2. 代理池管理测试")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 测试获取统计
    response = requests.get(f"{BASE_URL}/proxy-pool/stats", headers=headers)
    if response.status_code == 200:
        print(f"✓ 获取代理统计成功")
        print(f"  响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
    else:
        print(f"✗ 获取统计失败: {response.text}\n")
    
    # 测试添加代理
    proxy_data = {
        "ip": "192.168.1.100",
        "port": 8080,
        "protocol": "HTTP",
        "region": "CN",
        "group_name": "test_group"
    }
    
    response = requests.post(f"{BASE_URL}/proxy-pool/proxies", json=proxy_data, headers=headers)
    if response.status_code == 200:
        proxy = response.json()
        print(f"✓ 添加代理成功")
        print(f"  ID: {proxy['id']}")
        print(f"  IP: {proxy['ip']}:{proxy['port']}")
        print(f"  协议: {proxy['protocol']}\n")
    else:
        print(f"✗ 添加代理失败: {response.text}\n")
    
    # 测试获取代理列表
    response = requests.get(f"{BASE_URL}/proxy-pool/proxies", headers=headers)
    if response.status_code == 200:
        proxies = response.json()
        print(f"✓ 获取代理列表成功")
        print(f"  代理数量: {len(proxies)}\n")
    else:
        print(f"✗ 获取列表失败: {response.text}\n")


def test_api_management(token):
    """测试 API 管理"""
    print("=" * 60)
    print("3. API 管理测试")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 测试获取统计
    response = requests.get(f"{BASE_URL}/api-management/stats", headers=headers)
    if response.status_code == 200:
        print(f"✓ 获取 API 统计成功")
        print(f"  响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
    else:
        print(f"✗ 获取统计失败: {response.text}\n")
    
    # 测试创建 API 配置
    api_data = {
        "project_id": 1,
        "name": "Test API",
        "base_url": "https://api.example.com/v1",
        "auth_type": "api_key",
        "api_key": "test-key-123",
        "rate_limit": 100,
        "circuit_breaker_threshold": 10,
        "enabled": True
    }
    
    response = requests.post(f"{BASE_URL}/api-management/configs", json=api_data, headers=headers)
    if response.status_code == 200:
        config = response.json()
        print(f"✓ 创建 API 配置成功")
        print(f"  ID: {config['id']}")
        print(f"  名称: {config['name']}")
        print(f"  限流: {config['rate_limit']} 次/分钟\n")
    else:
        print(f"✗ 创建配置失败: {response.text}\n")
    
    # 测试获取配置列表
    response = requests.get(f"{BASE_URL}/api-management/configs", headers=headers)
    if response.status_code == 200:
        configs = response.json()
        print(f"✓ 获取 API 配置列表成功")
        print(f"  配置数量: {len(configs)}\n")
    else:
        print(f"✗ 获取列表失败: {response.text}\n")


def test_frontend_access():
    """测试前端页面访问"""
    print("=" * 60)
    print("4. 前端页面访问测试")
    print("=" * 60)
    
    pages = [
        ("代理池页面", "http://localhost:3000/proxy-pool"),
        ("API 管理页面", "http://localhost:3000/api-management")
    ]
    
    for name, url in pages:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"✓ {name} 可访问: {url}")
        else:
            print(f"✗ {name} 访问失败: {response.status_code}")
    
    print()


def main():
    print("\n")
    print("=" * 60)
    print("  Phase 6: 代理池与 API 管理 - 功能测试")
    print("=" * 60)
    print("\n")
    
    # 登录
    token = login()
    if not token:
        return
    
    # 测试代理池
    test_proxy_pool(token)
    
    # 测试 API 管理
    test_api_management(token)
    
    # 测试前端
    test_frontend_access()
    
    # 总结
    print("=" * 60)
    print("  测试完成！")
    print("=" * 60)
    print("\n📋 测试清单:")
    print("  ✓ 登录认证")
    print("  ✓ 代理池统计 API")
    print("  ✓ 添加代理 API")
    print("  ✓ 代理列表 API")
    print("  ✓ API 统计")
    print("  ✓ 创建 API 配置")
    print("  ✓ API 配置列表")
    print("  ✓ 前端页面访问")
    print("\n🎯 下一步:")
    print("  1. 打开浏览器访问: http://localhost:3000")
    print("  2. 登录后点击侧边栏 '资源管理' 菜单")
    print("  3. 查看代理池和 API 管理页面")
    print("\n")


if __name__ == "__main__":
    main()
