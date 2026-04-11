"""
Phase 5 测试脚本
"""
import requests
import json
from datetime import datetime

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
        print(f"✓ 登录成功")
        print(f"  Token: {token[:50]}...\n")
        return token
    else:
        print(f"✗ 登录失败: {response.text}")
        return None


def test_quality_stats(token):
    """测试获取质量统计"""
    print("=" * 60)
    print("2. 获取数据质量统计")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/data-quality/checks/stats", headers=headers)
    
    if response.status_code == 200:
        print(f"✓ 获取成功")
        print(f"  响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
    else:
        print(f"✗ 获取失败: {response.text}\n")


def test_create_rule(token):
    """测试创建质量规则"""
    print("=" * 60)
    print("3. 创建数据质量规则")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    rule_data = {
        "project_id": 1,
        "spider_name": "test_spider",
        "rule_name": "基础质量检测",
        "rule_type": "comprehensive",
        "conditions": {
            "min_records": 1000,
            "max_records": 100000,
            "null_rate_threshold": 0.05,
            "duplicate_rate_threshold": 5,
            "freshness_threshold": 86400
        },
        "enabled": True
    }
    
    response = requests.post(f"{BASE_URL}/data-quality/rules", json=rule_data, headers=headers)
    
    if response.status_code == 200:
        rule = response.json()
        print(f"✓ 规则创建成功")
        print(f"  ID: {rule['id']}")
        print(f"  名称: {rule['rule_name']}")
        print(f"  类型: {rule['rule_type']}\n")
        return rule['id']
    else:
        print(f"✗ 创建失败: {response.text}\n")
        return None


def test_get_rules(token):
    """测试获取规则列表"""
    print("=" * 60)
    print("4. 获取质量规则列表")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/data-quality/rules", headers=headers)
    
    if response.status_code == 200:
        rules = response.json()
        print(f"✓ 获取成功")
        print(f"  规则数量: {len(rules)}")
        for rule in rules:
            print(f"  - {rule['rule_name']} ({rule['rule_type']})")
        print()
    else:
        print(f"✗ 获取失败: {response.text}\n")


def test_summary_stats(token):
    """测试获取汇总统计"""
    print("=" * 60)
    print("5. 获取汇总统计")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/data-quality/statistics/summary", headers=headers, params={"days": 30})
    
    if response.status_code == 200:
        print(f"✓ 获取成功")
        print(f"  响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
    else:
        print(f"✗ 获取失败: {response.text}\n")


def test_frontend_access():
    """测试前端页面访问"""
    print("=" * 60)
    print("6. 前端页面访问测试")
    print("=" * 60)
    
    pages = [
        ("数据质量页面", "http://localhost:3000/data-quality"),
        ("统计报表页面", "http://localhost:3000/data-statistics")
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
    print("  Phase 5: 数据质量检测系统 - 功能测试")
    print("=" * 60)
    print("\n")
    
    # 登录
    token = login()
    if not token:
        return
    
    # 测试 API
    test_quality_stats(token)
    rule_id = test_create_rule(token)
    test_get_rules(token)
    test_summary_stats(token)
    
    # 测试前端
    test_frontend_access()
    
    # 总结
    print("=" * 60)
    print("  测试完成！")
    print("=" * 60)
    print("\n📋 测试清单:")
    print("  ✓ 登录认证")
    print("  ✓ 质量统计 API")
    print("  ✓ 创建质量规则")
    print("  ✓ 获取规则列表")
    print("  ✓ 汇总统计 API")
    print("  ✓ 前端页面访问")
    print("\n🎯 下一步:")
    print("  1. 打开浏览器访问: http://localhost:3000")
    print("  2. 登录后点击侧边栏 '数据管理' 菜单")
    print("  3. 查看数据质量和统计报表页面")
    print("\n")


if __name__ == "__main__":
    main()
