#!/usr/bin/env python3
"""
分页功能自动化测试脚本
测试已完成的5个页面: Spiders, Projects, Users, Schedules, Deploy
"""
import requests
import sys

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None

def login():
    """登录获取Token"""
    print("\n" + "="*70)
    print("步骤 1/6: 登录获取Token")
    print("="*70)
    
    try:
        # OAuth2PasswordRequestForm 使用表单数据
        form_data = {
            "username": "admin",
            "password": "admin123"
        }
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            data=form_data  # 使用 data 而不是 json
        )
        
        if resp.status_code == 200:
            global TOKEN
            TOKEN = resp.json().get("access_token")
            print("✓ 登录成功")
            return True
        else:
            print(f"✗ 登录失败: {resp.status_code}")
            print(f"  响应: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ 登录异常: {e}")
        return False


def test_api(name, endpoint, check_items=True):
    """测试API分页功能"""
    print(f"\n{'='*70}")
    print(f"测试: {name}")
    print(f"{'='*70}")
    
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    
    # 测试1: 请求第1页,每页2条
    try:
        print("\n[测试 1] 请求第1页,每页2条")
        resp = requests.get(
            f"{BASE_URL}/{endpoint}",
            params={"skip": 0, "limit": 2},
            headers=headers
        )
        
        print(f"  状态码: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"  ✗ 请求失败: {resp.text[:200]}")
            return False
        
        data = resp.json()
        
        # 检查返回格式
        if not isinstance(data, dict):
            print(f"  ✗ 返回格式错误: 期望dict, 实际{type(data)}")
            print(f"  数据: {str(data)[:200]}")
            return False
        
        print(f"  ✓ 返回格式正确 (dict)")
        
        # 检查必需字段
        required_fields = ['total', 'items', 'skip', 'limit']
        for field in required_fields:
            if field not in data:
                print(f"  ✗ 缺少字段: {field}")
                return False
            print(f"  ✓ 字段 {field}: {data[field] if field != 'items' else f'Array({len(data[field])})'}")
        
        # 检查数据
        if check_items and len(data.get('items', [])) > 0:
            print(f"  ✓ 返回数据正常 ({len(data['items'])} 条)")
        
        # 验证分页参数
        if data.get('skip') != 0:
            print(f"  ✗ skip 应为 0, 实际 {data['skip']}")
            return False
        print(f"  ✓ skip 参数正确")
        
        if data.get('limit') != 2:
            print(f"  ✗ limit 应为 2, 实际 {data['limit']}")
            return False
        print(f"  ✓ limit 参数正确")
        
        # 测试2: 请求第2页
        print("\n[测试 2] 请求第2页,每页2条")
        resp2 = requests.get(
            f"{BASE_URL}/{endpoint}",
            params={"skip": 2, "limit": 2},
            headers=headers
        )
        
        if resp2.status_code == 200:
            data2 = resp2.json()
            if isinstance(data2, dict):
                print(f"  ✓ 第2页请求成功")
                print(f"  - total: {data2.get('total')}")
                print(f"  - skip: {data2.get('skip')}")
                if data2.get('skip') == 2:
                    print(f"  ✓ skip 参数正确")
                else:
                    print(f"  ✗ skip 应为 2, 实际 {data2.get('skip')}")
                    return False
        
        print(f"\n✅ {name} 测试通过!")
        return True
        
    except Exception as e:
        print(f"  ✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*70)
    print("CrawloPilot 分页功能自动化测试")
    print("="*70)
    print(f"后端地址: {BASE_URL}")
    print(f"测试时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 登录
    if not login():
        print("\n⚠️ 登录失败,尝试无认证测试...")
    
    # 测试列表
    tests = [
        ("Spiders API (爬虫列表)", "spiders"),
        ("Projects API (项目列表)", "projects"),
        ("Users API (用户列表)", "users"),
        ("Schedules API (调度列表)", "schedules"),
        ("Deploy API (部署列表)", "deploys"),  # 注意是 deploys 不是 deploy
    ]
    
    results = []
    for name, endpoint in tests:
        result = test_api(name, endpoint)
        results.append((name, result))
    
    # 汇总结果
    print(f"\n{'='*70}")
    print("测试汇总")
    print(f"{'='*70}")
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n{'='*70}")
    print(f"总计: {passed}/{total} 通过, {failed} 失败")
    print(f"{'='*70}")
    
    if passed == total:
        print("\n🎉 所有测试通过! 分页功能正常工作!")
        print("\n📋 可以测试的前端页面:")
        print("  - http://localhost:3000/spiders")
        print("  - http://localhost:3000/projects")
        print("  - http://localhost:3000/users")
        print("  - http://localhost:3000/schedules")
        print("  - http://localhost:3000/deploy")
        return 0
    else:
        print(f"\n⚠️ {failed} 个测试失败,请检查:")
        print("  1. 后端服务是否正常运行")
        print("  2. 数据库是否有数据")
        print("  3. API 路由是否正确")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
