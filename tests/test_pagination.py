#!/usr/bin/env python3
"""
分页功能测试脚本
"""
import requests

BASE_URL = "http://localhost:18000/api/v1"

def test_api(name, endpoint, token=None):
    """测试API分页"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    # 测试1: 请求第1页,每页2条
    try:
        resp = requests.get(
            f"{BASE_URL}/{endpoint}",
            params={"skip": 0, "limit": 2},
            headers=headers
        )
        
        print(f"✓ 状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            
            if isinstance(data, dict):
                print(f"✓ 返回格式: 字典")
                print(f"  - total: {data.get('total', 'N/A')}")
                print(f"  - items数量: {len(data.get('items', []))}")
                print(f"  - skip: {data.get('skip', 'N/A')}")
                print(f"  - limit: {data.get('limit', 'N/A')}")
                
                if data.get('total', 0) > 0:
                    print(f"✓ 测试通过!")
                    return True
                else:
                    print(f"⚠ 数据为空,但格式正确")
                    return True
            else:
                print(f"✗ 错误: 返回格式不是字典")
                print(f"  实际类型: {type(data)}")
                return False
        else:
            print(f"✗ 请求失败: {resp.text}")
            return False
            
    except Exception as e:
        print(f"✗ 异常: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("CrawloPilot 分页功能测试")
    print("="*60)
    
    # 先登录获取token
    print("\n[1/4] 登录获取Token...")
    try:
        login_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            print(f"✓ 登录成功")
        else:
            print(f"✗ 登录失败: {login_resp.text}")
            print("继续测试(不使用token)...")
            token = None
    except Exception as e:
        print(f"✗ 登录异常: {e}")
        token = None
    
    # 测试各个API
    tests = [
        ("Spiders API (爬虫列表)", "spiders"),
        ("Projects API (项目列表)", "projects"),
        ("Users API (用户列表)", "users"),
    ]
    
    results = []
    for name, endpoint in tests:
        result = test_api(name, endpoint, token)
        results.append((name, result))
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
    else:
        print(f"\n⚠ {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
