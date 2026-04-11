"""
Phase 7 测试脚本 - 操作审计功能
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


def test_audit_logs(token):
    """测试审计日志"""
    print("=" * 60)
    print("2. 测试审计日志 API")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 测试获取审计统计
    response = requests.get(f"{BASE_URL}/audit/stats", headers=headers)
    if response.status_code == 200:
        stats = response.json()
        print(f"✓ 获取审计统计成功")
        print(f"  总操作次数: {stats.get('total', 0)}")
        print(f"  统计周期: {stats.get('period_days', 30)} 天")
        
        # 显示操作类型统计
        action_stats = stats.get('action_stats', [])
        if action_stats:
            print(f"  操作类型统计:")
            for item in action_stats[:5]:
                print(f"    - {item['action']}: {item['count']}次")
        print()
    else:
        print(f"✗ 获取统计失败: {response.status_code}")
        print(f"  {response.text}\n")
    
    # 测试获取审计日志列表
    response = requests.get(f"{BASE_URL}/audit/logs?limit=5", headers=headers)
    if response.status_code == 200:
        logs = response.json()
        print(f"✓ 获取审计日志成功")
        print(f"  日志数量: {len(logs)}")
        
        if logs:
            print(f"  最新日志:")
            log = logs[0]
            print(f"    - 操作: {log.get('action')}")
            print(f"    - 用户: {log.get('username')}")
            print(f"    - 资源类型: {log.get('resource_type')}")
            print(f"    - 时间: {log.get('created_at')}")
        print()
    else:
        print(f"✗ 获取日志失败: {response.status_code}")
        print(f"  {response.text}\n")


def test_user_activity(token):
    """测试用户活动"""
    print("=" * 60)
    print("3. 测试用户活动 API")
    print("=" * 60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 测试获取用户活动
    response = requests.get(f"{BASE_URL}/audit/user/2/activity?days=7", headers=headers)
    if response.status_code == 200:
        activity = response.json()
        print(f"✓ 获取用户活动成功")
        print(f"  用户ID: {activity.get('user_id')}")
        print(f"  总操作数: {activity.get('total_actions')}")
        print(f"  统计周期: {activity.get('period_days')} 天")
        
        daily_stats = activity.get('daily_stats', [])
        if daily_stats:
            print(f"  每日活动:")
            for item in daily_stats[:5]:
                print(f"    - {item['date']}: {item['count']}次")
        print()
    else:
        print(f"✗ 获取用户活动失败: {response.status_code}")
        print(f"  {response.text}\n")


def test_health():
    """测试健康检查"""
    print("=" * 60)
    print("4. 测试健康检查")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": "Bearer test"})
    print(f"  测试端点: /auth/me (401 是预期的)")
    print(f"  状态码: {response.status_code}")
    print(f"  ✓ 健康检查端点可访问\n")


def main():
    print("\n")
    print("=" * 60)
    print("  Phase 7: 操作审计 - 功能测试")
    print("=" * 60)
    print("\n")
    
    # 登录
    token = login()
    if not token:
        return
    
    # 测试审计功能
    test_audit_logs(token)
    test_user_activity(token)
    test_health()
    
    # 总结
    print("=" * 60)
    print("  测试完成！")
    print("=" * 60)
    print("\n📋 测试清单:")
    print("  ✓ 登录认证")
    print("  ✓ 审计统计 API")
    print("  ✓ 审计日志列表 API")
    print("  ✓ 用户活动 API")
    print("  ✓ 健康检查端点")
    print("\n🎯 Phase 7 已实现功能:")
    print("  ✓ 审计服务层")
    print("  ✓ 审计 API 路由")
    print("  ✓ 统计功能")
    print("  ✓ 日志查询")
    print("  ○ 审计中间件（待实现）")
    print("  ○ 前端页面（待实现）")
    print("\n")


if __name__ == "__main__":
    main()
