#!/usr/bin/env python3
"""
Git 凭据功能端到端测试

覆盖：
1. 个人 Git 凭据（方案一）：保存/脱敏查询/留空保留/清除
2. 共享 Git 凭据（方案二）：admin CRUD、非 admin 拒绝、引用保护
3. 爬虫创建时的凭据解析：use_my_git_credential / git_credential_id
4. 爬虫详情秘密字段脱敏
"""
import sys
import json
import time
import urllib.request

BASE = "http://localhost:8000/api/v1"
PASS = 0
FAIL = 0
FAILURES = []


def http(method, path, token=None, json_body=None):
    url = BASE + path
    headers = {}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except json.JSONDecodeError:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"  FAIL  {name}  {extra}")


def login(username, password):
    import urllib.parse
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        BASE + "/auth/login", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())["access_token"]


def main():
    print("=" * 60)
    print("Git 凭据功能端到端测试")
    print("=" * 60)

    admin = login("admin", "admin123")

    # ---------- 方案一：个人 Git 凭据 ----------
    print("\n[1] 个人 Git 凭据")
    s, r = http("GET", "/auth/me/git-credentials", admin)
    check("初始状态查询成功", s == 200, r)

    s, r = http("PUT", "/auth/me/git-credentials", admin, {
        "auth_type": "password",
        "username": "oscar-git",
        "password": "token-secret-123",
        "default_branch": "develop",
    })
    check("保存个人凭据", s == 200 and r.get("configured") is True, r)
    check("保存后返回脱敏信息", r.get("has_password") is True and "token-secret-123" not in json.dumps(r), r)

    s, r = http("GET", "/auth/me/git-credentials", admin)
    check("查询脱敏凭据", s == 200 and r.get("username") == "oscar-git" and r.get("default_branch") == "develop", r)
    check("秘密本体不回传", "token-secret-123" not in json.dumps(r), r)

    # 留空保留原值
    s, r = http("PUT", "/auth/me/git-credentials", admin, {
        "auth_type": "password", "username": "oscar-git2", "password": "", "default_branch": "main",
    })
    check("留空密码保留原值", s == 200 and r.get("has_password") is True and r.get("username") == "oscar-git2", r)

    # ---------- 方案二：共享 Git 凭据 ----------
    print("\n[2] 共享 Git 凭据（团队机器人）")
    cred_name = f"robot-ci-{int(time.time())}"
    s, r = http("POST", "/git-credentials", admin, {
        "name": cred_name,
        "description": "CI 机器人只读凭据",
        "auth_type": "password",
        "username": "robot-ci",
        "password": "robot-token-xyz",
        "default_branch": "main",
    })
    check("admin 创建共享凭据", s == 201 and r.get("id"), r)
    cred_id = r.get("id")
    check("创建返回脱敏", r.get("has_password") is True and "robot-token-xyz" not in json.dumps(r), r)

    s, r = http("GET", "/git-credentials", admin)
    check("凭据列表可读", s == 200 and any(c["id"] == cred_id for c in r), r)
    check("列表不含秘密", "robot-token-xyz" not in json.dumps(r), r)

    # 非 admin 写操作拒绝
    uname = f"tester{int(time.time())}"
    s, r = http("POST", "/auth/register", None, {
        "username": uname, "email": f"{uname}@test.com", "password": "test123456",
    })
    check("注册普通用户", s in (200, 201), r)
    tester = login(uname, "test123456")
    s, r = http("POST", "/git-credentials", tester, {
        "name": "hack-cred", "auth_type": "password", "password": "x",
    })
    check("非 admin 创建被拒(403)", s == 403, r)
    s, r = http("GET", "/git-credentials", tester)
    check("普通用户可读列表（用于选择）", s == 200, r)

    # ---------- 爬虫创建时的凭据解析 ----------
    print("\n[3] 爬虫创建凭据解析")
    # 取一个项目
    s, r = http("GET", "/projects?skip=0&limit=1", admin)
    project_id = r["items"][0]["id"] if r.get("items") else None
    check("存在可用项目", project_id is not None, r)

    ts = int(time.time())
    # 3a. 使用我的凭据
    s, r = http("POST", "/spiders", admin, {
        "name": f"cred_mine_{ts}", "project_id": project_id, "spider_type": "crawlo",
        "git_url": "https://example.com/repo.git",
        "use_my_git_credential": True,
    })
    check("创建爬虫(我的凭据)", s == 201, r)
    spider_mine = r.get("id")
    check("我的凭据已内联填充", r.get("git_username") == "oscar-git2" and r.get("git_branch") == "main", r)

    # 3b. 使用团队凭据
    s, r = http("POST", "/spiders", admin, {
        "name": f"cred_shared_{ts}", "project_id": project_id, "spider_type": "crawlo",
        "git_url": "https://example.com/repo2.git",
        "git_credential_id": cred_id,
        "git_username": "should-be-cleared",
        "git_password": "should-be-cleared",
    })
    check("创建爬虫(团队凭据)", s == 201, r)
    spider_shared = r.get("id")
    check("内联凭据已清空", r.get("git_username") is None and r.get("git_password") is None, r)
    check("已关联共享凭据", r.get("git_credential_id") == cred_id, r)

    # 3c. 无效的共享凭据
    s, r = http("POST", "/spiders", admin, {
        "name": f"cred_bad_{ts}", "project_id": project_id, "spider_type": "crawlo",
        "git_url": "https://example.com/repo3.git", "git_credential_id": 999999,
    })
    check("无效共享凭据被拒(400)", s == 400, r)

    # 3d. 未配置个人凭据时使用我的凭据
    s, r = http("POST", "/spiders", tester, {
        "name": f"cred_none_{ts}", "project_id": project_id, "spider_type": "crawlo",
        "git_url": "https://example.com/repo4.git", "use_my_git_credential": True,
    })
    check("未配置个人凭据时报错(400)", s == 400, r)

    # ---------- 详情脱敏 ----------
    print("\n[4] 爬虫详情秘密字段脱敏")
    s, r = http("GET", f"/spiders/{spider_mine}", admin)
    check("详情不回传 git_password", s == 200 and r.get("git_password") is None, r)
    check("详情不回传 git_ssh_key", r.get("git_ssh_key") is None, r)
    check("详情保留 git_credential_id", "git_credential_id" in r, r)

    # ---------- 更新引用 / 引用保护 ----------
    print("\n[5] 引用更新与删除保护")
    s, r = http("DELETE", f"/git-credentials/{cred_id}", admin)
    check("被引用凭据删除被拒(400)", s == 400, r)

    s, r = http("PUT", f"/spiders/{spider_shared}", admin, {"git_credential_id": None})
    check("清除共享凭据引用", s == 200 and r.get("git_credential_id") is None, r)

    s, r = http("PUT", f"/spiders/{spider_shared}", admin, {"git_credential_id": cred_id})
    check("重新关联共享凭据", s == 200 and r.get("git_credential_id") == cred_id, r)

    # 停用后不可再被引用
    s, r = http("PUT", f"/git-credentials/{cred_id}", admin, {"is_active": False})
    check("停用共享凭据", s == 200 and r.get("is_active") is False, r)
    s, r = http("PUT", f"/spiders/{spider_mine}", admin, {"git_credential_id": cred_id})
    check("停用凭据不可被引用(400)", s == 400, r)
    s, r = http("GET", "/git-credentials", admin)
    check("默认列表不含停用凭据", all(c["id"] != cred_id for c in r), r)
    s, r = http("GET", "/git-credentials?include_inactive=true", admin)
    check("include_inactive 可见停用凭据", any(c["id"] == cred_id for c in r), r)

    # ---------- 清理 ----------
    print("\n[6] 清理测试数据")
    for sid in (spider_mine, spider_shared):
        if sid:
            http("DELETE", f"/spiders/{sid}", admin)
    s, r = http("DELETE", f"/git-credentials/{cred_id}", admin)
    check("解除引用后可删除", s == 200, r)
    s, r = http("DELETE", "/auth/me/git-credentials", admin)
    check("清除个人凭据", s == 200, r)
    s, r = http("GET", "/auth/me/git-credentials", admin)
    check("清除后 configured=false", r.get("configured") is False, r)

    print("\n" + "=" * 60)
    print(f"结果: {PASS} 通过, {FAIL} 失败")
    if FAILURES:
        print("失败项:", ", ".join(FAILURES))
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
