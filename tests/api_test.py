#!/usr/bin/env python3
"""CrawloPilot 后端 API 全功能测试脚本（修订版）"""

import requests
import sys
import uuid

BASE = "http://localhost:8000/api/v1"
RESULTS = {"pass": 0, "fail": 0, "skip": 0, "errors": []}

# 唯一标识，避免重复创建冲突
UNIQ = uuid.uuid4().hex[:6]


def assert_keys(d, keys):
    for k in keys:
        assert k in d, f"Missing key: {k}"


def assert_true(v, msg=""):
    assert v, msg


def get_token():
    r = requests.post(f"{BASE}/auth/login", data={"username": "admin", "password": "admin123"})
    return r.json()["access_token"]


TOKEN = get_token()
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def test(name, method, url, expected_status=200, json_data=None, params=None, check_fn=None):
    """通用测试函数"""
    full_url = f"{BASE}{url}"
    try:
        r = requests.request(method, full_url, headers=H, json=json_data, params=params, timeout=10)
        ok = r.status_code == expected_status
        detail = ""
        if check_fn and ok:
            try:
                check_fn(r.json())
            except AssertionError as e:
                ok = False
                detail = str(e)
        status = "✅" if ok else "❌"
        if ok:
            RESULTS["pass"] += 1
        else:
            RESULTS["fail"] += 1
            RESULTS["errors"].append(f"{name}: HTTP {r.status_code} (expected {expected_status}) {detail}")
        body_preview = ""
        try:
            body = r.json()
            if isinstance(body, dict):
                body_preview = f" | keys={list(body.keys())[:5]}"
            elif isinstance(body, list):
                body_preview = f" | count={len(body)}"
        except Exception:
            pass
        print(f"  {status} {method:6s} {url:50s} -> {r.status_code}{body_preview}")
        return r
    except Exception as e:
        RESULTS["fail"] += 1
        RESULTS["errors"].append(f"{name}: {e}")
        print(f"  ❌ {method:6s} {url:50s} -> ERROR: {e}")
        return None


# ============================================================
print("\n" + "=" * 60)
print("  1. AUTH 认证模块")
print("=" * 60)

r = requests.post(f"{BASE}/auth/login", data={"username": "admin", "password": "admin123"})
ok = r.status_code == 200 and "access_token" in r.json()
print(f"  {'✅' if ok else '❌'} POST   /auth/login                                     -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1

r = requests.post(f"{BASE}/auth/login", data={"username": "admin", "password": "wrong"})
ok = r.status_code == 401
print(f"  {'✅' if ok else '❌'} POST   /auth/login (wrong pwd)                           -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1

test("获取当前用户", "GET", "/auth/me", check_fn=lambda d: assert_keys(d, ["id", "username"]))

# 无 Token 访问（用不含授权头的请求）
r = requests.get(f"{BASE}/auth/me")
ok = r.status_code == 401
print(f"  {'✅' if ok else '❌'} GET    /auth/me (no token)                              -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1

r = requests.post(f"{BASE}/auth/register", headers=H, json={
    "username": f"testuser_{UNIQ}", "email": f"{UNIQ}@api.com", "password": "Test123!", "full_name": "Test User"})
ok = r.status_code == 200 and "id" in r.json()
print(f"  {'✅' if ok else '❌'} POST   /auth/register                                  -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1

r = requests.post(f"{BASE}/auth/register", headers=H, json={
    "username": f"testuser_{UNIQ}", "email": f"{UNIQ}@api.com", "password": "Test123!", "full_name": "Test User"})
ok = r.status_code == 400
print(f"  {'✅' if ok else '❌'} POST   /auth/register (dup)                             -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1


# ============================================================
print("\n" + "=" * 60)
print("  2. USERS 用户管理模块")
print("=" * 60)

test("角色列表", "GET", "/users/roles", check_fn=lambda d: assert_true(isinstance(d, list)))
test("用户列表", "GET", "/users", check_fn=lambda d: assert_keys(d, ["total", "items"]))
test("用户列表-过滤", "GET", "/users", params={"username": "admin"})
test("创建用户", "POST", "/users", expected_status=201,
     json_data={"username": f"api_user_{UNIQ}", "email": f"api_{UNIQ}@test.com", "password": "Test123!", "full_name": "API Test"},
     check_fn=lambda d: assert_keys(d, ["id", "username"]))

# Get the created user id
r = requests.get(f"{BASE}/users", headers=H, params={"username": f"api_user_{UNIQ}"})
test_uid = r.json()["items"][0]["id"] if r.json()["items"] else None

if test_uid:
    test("用户详情", "GET", f"/users/{test_uid}")
    test("更新用户", "PUT", f"/users/{test_uid}", json_data={"full_name": "Updated Name"})
    test("重置密码", "POST", f"/users/{test_uid}/reset-password", params={"new_password": "NewPass123!"})
    test("切换状态", "POST", f"/users/{test_uid}/toggle-status")
    test("再次切换", "POST", f"/users/{test_uid}/toggle-status")
    test("删除用户(软删)", "DELETE", f"/users/{test_uid}", expected_status=204)
else:
    print("  ⚠️  跳过用户CRUD测试（创建失败）")
    RESULTS["skip"] += 1

test("删除自己(应400)", "DELETE", "/users/1", expected_status=400)


# ============================================================
print("\n" + "=" * 60)
print("  3. TEAMS 团队模块")
print("=" * 60)

test("团队列表", "GET", "/teams", check_fn=lambda d: assert_true(isinstance(d, list)))
test("创建项目-无team(应422)", "POST", "/projects", expected_status=422,
     json_data={"name": f"noproj_{UNIQ}", "description": "test"})


# ============================================================
print("\n" + "=" * 60)
print("  4. PROJECTS 项目管理模块")
print("=" * 60)

test("项目列表", "GET", "/projects", check_fn=lambda d: assert_keys(d, ["total", "items"]))
test("创建项目", "POST", "/projects", expected_status=201,
     json_data={"name": f"API测试_{UNIQ}", "description": "自动化测试创建", "team_id": 1},
     check_fn=lambda d: assert_keys(d, ["id", "name"]))

# Get project id
r = requests.get(f"{BASE}/projects", headers=H)
projects = r.json()["items"]
test_pid = None
for p in projects:
    if p["name"] == f"API测试_{UNIQ}":
        test_pid = p["id"]
        break

if test_pid:
    test("项目详情", "GET", f"/projects/{test_pid}")
    test("更新项目", "PUT", f"/projects/{test_pid}", json_data={"description": "Updated desc"})
    test("创建版本", "POST", f"/projects/{test_pid}/versions", expected_status=201,
         json_data={"version": "v1.0.0", "config_snapshot": {"env": "test"}})
    test("版本列表", "GET", f"/projects/{test_pid}/versions",
         check_fn=lambda d: assert_true(isinstance(d, list)))

    print("\n  --- Project Files ---")
    test("文件树(无代码)", "GET", f"/projects/{test_pid}/files/tree")
    test("读文件(不存在)", "GET", f"/projects/{test_pid}/files/content",
         params={"path": "test.py"}, expected_status=400)
else:
    print("  ⚠️  跳过项目详情测试")
    RESULTS["skip"] += 1


# ============================================================
print("\n" + "=" * 60)
print("  5. SPIDERS 爬虫管理模块")
print("=" * 60)

test("爬虫列表", "GET", "/spiders", check_fn=lambda d: assert_keys(d, ["total", "items"]))

if test_pid:
    test("创建爬虫", "POST", "/spiders", expected_status=201,
         json_data={"name": f"spider_{UNIQ}", "project_id": test_pid, "spider_type": "crawlo",
                    "entry_file": "main.py", "spider_name": f"spider_{UNIQ}"},
         check_fn=lambda d: assert_keys(d, ["id", "name"]))

    r = requests.get(f"{BASE}/spiders", headers=H, params={"project_id": test_pid})
    spiders = r.json()["items"]
    test_sid = None
    for s in spiders:
        if s["name"] == f"spider_{UNIQ}":
            test_sid = s["id"]
            break

    if test_sid:
        test("爬虫详情", "GET", f"/spiders/{test_sid}")
        test("更新爬虫", "PUT", f"/spiders/{test_sid}", json_data={"description": "Updated spider"})
        test("爬虫文件树", "GET", f"/spiders/{test_sid}/files/tree")
        test("运行爬虫(无代码)", "POST", f"/spiders/{test_sid}/run", json_data={}, expected_status=400)
        test("停止爬虫", "POST", f"/spiders/{test_sid}/stop")
        test("重复名创建(应400)", "POST", "/spiders", expected_status=400,
             json_data={"name": f"spider_{UNIQ}", "project_id": test_pid})
    else:
        print("  ⚠️  跳过爬虫详情测试")
        RESULTS["skip"] += 1


# ============================================================
print("\n" + "=" * 60)
print("  6. TASKS 任务管理模块")
print("=" * 60)

test("任务列表", "GET", "/execution/tasks", check_fn=lambda d: assert_true(isinstance(d, dict) and isinstance(d.get('items'), list)))
test("任务统计", "GET", "/execution/tasks/stats/summary")
test("最近任务", "GET", "/execution/tasks/recent")
test("按状态查(running)", "GET", "/execution/tasks/running")
test("按状态过滤", "GET", "/execution/tasks", params={"status": "success"})


# ============================================================
print("\n" + "=" * 60)
print("  7. EXECUTION 执行模块")
print("=" * 60)

test("执行列表", "GET", "/execution/tasks", check_fn=lambda d: assert_keys(d, ["total", "items"]))

# Get an existing task for detail test
r = requests.get(f"{BASE}/execution/tasks", headers=H)
tasks = r.json()["items"]
if tasks:
    tid = tasks[0]["id"]
    test("任务详情", "GET", f"/execution/tasks/{tid}")
    test("任务状态", "GET", f"/execution/tasks/{tid}/status")
    test("任务日志", "GET", f"/execution/tasks/{tid}/logs")
else:
    print("  ⚠️  没有任务记录，跳过执行详情测试")
    RESULTS["skip"] += 1

test("任务不存在", "GET", "/execution/tasks/99999", expected_status=404)


# ============================================================
print("\n" + "=" * 60)
print("  8. DEPLOYS 部署模块")
print("=" * 60)

test("部署列表", "GET", "/deploys", check_fn=lambda d: assert_keys(d, ["total", "items"]))
test("部署不存在", "GET", "/deploys/99999", expected_status=404)


# ============================================================
print("\n" + "=" * 60)
print("  9. NODES 节点管理模块")
print("=" * 60)

test("节点列表", "GET", "/nodes", check_fn=lambda d: assert_true(isinstance(d, list)))
test("创建节点(agent)", "POST", "/nodes", expected_status=200,
     json_data={"name": f"agent-{UNIQ}", "host": "127.0.0.1", "connect_type": "agent"})

# Get node id
r = requests.get(f"{BASE}/nodes", headers=H)
nodes = r.json()
test_nid = None
for n in nodes:
    if n["name"] == f"agent-{UNIQ}":
        test_nid = n["id"]
        break

if test_nid:
    test("节点详情", "GET", f"/nodes/{test_nid}")
    test("更新节点", "PUT", f"/nodes/{test_nid}", json_data={"name": f"agent-upd-{UNIQ}"})
    test("健康检查", "POST", "/nodes/health-check")
    test("节点容器", "GET", f"/nodes/{test_nid}/containers")
    test("删除节点", "DELETE", f"/nodes/{test_nid}")
else:
    print("  ⚠️  跳过节点详情测试")
    RESULTS["skip"] += 1


# ============================================================
print("\n" + "=" * 60)
print("  10. SERVERS 服务器模块")
print("=" * 60)

test("服务器列表", "GET", "/servers", check_fn=lambda d: assert_keys(d, ["total", "items"]))
test("创建服务器", "POST", "/servers",
     json_data={"name": f"srv-{UNIQ}", "host": "127.0.0.1", "description": "Test"},
     check_fn=lambda d: assert_keys(d, ["id"]))

r = requests.get(f"{BASE}/servers", headers=H)
servers = r.json()["items"]
test_svid = None
for s in servers:
    if s["name"] == f"srv-{UNIQ}":
        test_svid = s["id"]
        break

if test_svid:
    test("服务器详情", "GET", f"/servers/{test_svid}")
    test("更新服务器", "PUT", f"/servers/{test_svid}", json_data={"description": "Updated"})
    test("服务器节点", "GET", f"/servers/{test_svid}/nodes")
    test("创建通道(agent)", "POST", f"/servers/{test_svid}/nodes",
         json_data={"name": f"ch-{UNIQ}", "connect_type": "agent"})
    test("服务器维护", "POST", f"/servers/{test_svid}/maintenance")
    test("删除服务器", "DELETE", f"/servers/{test_svid}")
else:
    print("  ⚠️  跳过服务器测试")
    RESULTS["skip"] += 1


# ============================================================
print("\n" + "=" * 60)
print("  11. MONITORING 监控模块")
print("=" * 60)

test("监控健康", "GET", "/monitoring/health", check_fn=lambda d: assert_keys(d, ["status", "components"]))
test("仪表盘", "GET", "/monitoring/dashboard", check_fn=lambda d: assert_keys(d, ["projects", "tasks", "nodes"]))


# ============================================================
print("\n" + "=" * 60)
print("  12. 基础端点")
print("=" * 60)

r = requests.get("http://localhost:8000/health")
ok = r.status_code == 200 and r.json()["status"] == "healthy"
print(f"  {'✅' if ok else '❌'} GET    /health                                         -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1

r = requests.get("http://localhost:8000/")
ok = r.status_code == 200
print(f"  {'✅' if ok else '❌'} GET    /                                               -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1

r = requests.get("http://localhost:8000/metrics")
ok = r.status_code == 200
print(f"  {'✅' if ok else '❌'} GET    /metrics                                        -> {r.status_code}")
RESULTS["pass" if ok else "fail"] += 1


# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("  测试结果汇总")
print("=" * 60)
total = RESULTS["pass"] + RESULTS["fail"]
print(f"  ✅ 通过: {RESULTS['pass']}")
print(f"  ❌ 失败: {RESULTS['fail']}")
print(f"  ⏭️  跳过: {RESULTS['skip']}")
print(f"  📊 总计: {total}")
print(f"  通过率: {RESULTS['pass']/total*100:.1f}%" if total > 0 else "  N/A")

if RESULTS["errors"]:
    print(f"\n  失败详情:")
    for e in RESULTS["errors"]:
        print(f"    - {e}")

# Cleanup: delete test project
if test_pid:
    requests.delete(f"{BASE}/projects/{test_pid}", headers=H)
    print(f"\n  🧹 已清理测试项目 (id={test_pid})")

sys.exit(0 if RESULTS["fail"] == 0 else 1)
