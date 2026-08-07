#!/usr/bin/env python3
"""
CrawloPilot 前后端全流程联调测试脚本
按前端真实业务链路，逐页面验证前端调用的后端接口是否畅通。

覆盖页面：Login/Layout/Dashboard/Projects/ProjectDetail/Spiders/SpiderDetail/
          Tasks/TaskDetail/Nodes/ServerDetail/Users
"""
import sys
import json
import time
import io
import zipfile
import urllib.request

BASE = "http://localhost:18000/api/v1"
PASS = 0
FAIL = 0
FAILURES = []


def http(method, path, token=None, data=None, json_body=None, files=None, raw=False):
    """通用 HTTP 请求"""
    url = BASE + path
    headers = {}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    elif data is not None:
        body = data.encode()
    elif files:
        boundary = "----crawlo" + str(int(time.time()))
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        parts = []
        for fname, fpath in files.items():
            with open(fpath, "rb") as f:
                content = f.read()
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"{fname}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + content + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.status
            content = resp.read().decode()
    except urllib.error.HTTPError as e:
        status = e.code
        content = e.read().decode()
    except Exception as e:
        return 0, {"error": str(e)}
    if raw:
        return status, content
    try:
        return status, json.loads(content)
    except Exception:
        return status, content


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✅ {name} {detail}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"  ❌ {name} {detail}")


def get_val(obj, *keys, default=None):
    """安全取值"""
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            return obj[k]
    return default


def main():
    global PASS, FAIL
    print("=" * 60)
    print(" CrawloPilot 前后端全流程联调")
    print("=" * 60)

    # ================= Login =================
    print("\n[1] Login 登录")
    status, d = http("POST", "/auth/login", data="username=admin&password=admin123")
    token = get_val(d, "access_token")
    check("POST /auth/login", status == 200 and token, f"({status})")

    # 错误密码
    status, d = http("POST", "/auth/login", data="username=admin&password=wrong")
    check("登录-错误密码返回401", status == 401, f"({status})")

    # ================= Layout (getCurrentUser) =================
    print("\n[2] Layout 用户信息")
    status, d = http("GET", "/auth/me", token=token)
    check("GET /auth/me", status == 200 and get_val(d, "username") == "admin", f"({status}) user={get_val(d,'username')}")
    roles = get_val(d, "roles", default=[])
    check("admin 含 admin 角色", any(r.get("name") == "admin" for r in roles), f"(isAdmin=期望true)")

    # ================= Dashboard =================
    print("\n[3] Dashboard 仪表盘")
    status, d = http("GET", "/monitoring/dashboard", token=token)
    check("GET /monitoring/dashboard", status == 200, f"({status}) keys={list(d.keys()) if isinstance(d,dict) else '?'}")
    status, d = http("GET", "/spiders?limit=1", token=token)
    check("GET /spiders?limit=1", status == 200, f"({status})")
    status, d = http("GET", "/nodes", token=token)
    check("GET /nodes", status == 200, f"({status})")

    # ================= Projects =================
    print("\n[4] Projects 项目管理")
    status, d = http("GET", "/teams", token=token)
    team_id = None
    if status == 200:
        teams = d if isinstance(d, list) else get_val(d, "items", default=[])
        team_id = teams[0]["id"] if teams else None
    check("GET /teams", status == 200 and team_id, f"({status}) team_id={team_id}")

    uniq = int(time.time())
    # 创建项目
    status, proj = http("POST", "/projects", token=token,
                        json_body={"name": f"联调项目_{uniq}", "description": "全流程联调", "team_id": team_id})
    pid = get_val(proj, "id")
    check("POST /projects 创建", status == 201 and pid, f"({status}) pid={pid}")

    # 项目列表
    status, d = http("GET", "/projects", token=token)
    check("GET /projects", status == 200, f"({status})")

    # 项目详情
    status, d = http("GET", f"/projects/{pid}", token=token)
    check("GET /projects/{id}", status == 200, f"({status})")

    # ================= ProjectDetail =================
    print("\n[5] ProjectDetail 项目详情")
    # 项目下爬虫列表
    status, d = http("GET", f"/spiders?project_id={pid}", token=token)
    check("GET /spiders?project_id={id}", status == 200, f"({status})")

    # ================= Spiders =================
    print("\n[6] Spiders 爬虫管理")
    status, spider = http("POST", "/spiders", token=token, json_body={
        "name": f"联调爬虫_{uniq}", "project_id": pid, "spider_type": "crawlo",
        "entry_file": "main.py", "spider_name": "main"
    })
    sid = get_val(spider, "id")
    check("POST /spiders 创建", status == 201 and sid, f"({status}) sid={sid}")

    # 爬虫列表
    status, d = http("GET", "/spiders", token=token)
    check("GET /spiders", status == 200, f"({status})")

    # 更新爬虫
    status, d = http("PUT", f"/spiders/{sid}", token=token, json_body={"description": "联调更新"})
    check("PUT /spiders/{id}", status == 200, f"({status})")

    # ================= SpiderDetail 上传代码 + 文件操作 =================
    print("\n[7] SpiderDetail 爬虫详情/代码管理")
    # 准备测试代码包
    code_zip = "/tmp/crawlo_it_spider.zip"
    with zipfile.ZipFile(code_zip, "w") as zf:
        zf.writestr("main.py", "import time\nfor i in range(3):\n    print(f'item_{i}')\n    time.sleep(0.3)\n")
    status, d = http("POST", f"/spiders/{sid}/upload", token=token, files={"code.zip": code_zip})
    check("POST /spiders/{id}/upload 上传代码", status == 200, f"({status}) {get_val(d,'message','')}")

    # 爬虫详情（含文件信息）
    status, d = http("GET", f"/spiders/{sid}", token=token)
    check("GET /spiders/{id}", status == 200, f"({status}) deploy_nodes={get_val(d,'deploy_nodes')}")

    # 文件树
    status, d = http("GET", f"/spiders/{sid}/files/tree", token=token)
    check("GET /spiders/{id}/files/tree", status == 200, f"({status})")

    # 文件内容
    status, d = http("GET", f"/spiders/{sid}/files/content?path=main.py", token=token)
    check("GET /spiders/{id}/files/content", status == 200, f"({status})")

    # 创建文件
    status, d = http("POST", f"/spiders/{sid}/files/create?path=extra.txt&is_directory=false", token=token)
    check("POST /spiders/{id}/files/create", status == 200, f"({status})")

    # 保存文件内容（前端 saveSpiderFileContent 用 query 传 content）
    status, d = http("POST", f"/spiders/{sid}/files/content?path=extra.txt&content=hello%3Dworld",
                     token=token)
    check("POST /spiders/{id}/files/content 保存", status == 200, f"({status})")

    # 删除文件
    status, d = http("DELETE", f"/spiders/{sid}/files?path=extra.txt", token=token)
    check("DELETE /spiders/{id}/files", status == 200, f"({status})")

    # ================= 运行爬虫 (核心链路) =================
    print("\n[8] 运行爬虫 (ProjectDetail/Spiders 的 runSpider)")
    status, d = http("POST", f"/spiders/{sid}/run", token=token, json_body={})
    task_id = get_val(d, "task_id")
    check("POST /spiders/{id}/run", status == 200 and task_id, f"({status}) task_id={task_id} mode={get_val(d,'mode')}")
    if not task_id:
        print("  ⚠️ 无法获取任务ID，跳过任务验证")
        return

    # ================= Tasks =================
    print("\n[9] Tasks 任务管理")
    status, d = http("GET", "/execution/tasks?limit=20&offset=0", token=token)
    check("GET /execution/tasks 列表", status == 200, f"({status}) total={get_val(d,'total')}")
    check("任务列表含刚创建任务", any(get_val(t, "id") == task_id for t in get_val(d, "items", default=[])),
          f"(task {task_id})")

    # 任务统计
    status, d = http("GET", "/execution/tasks/stats/summary", token=token)
    check("GET /execution/tasks/stats/summary", status == 200, f"({status})")

    # 运行中任务
    status, d = http("GET", "/execution/tasks/running", token=token)
    check("GET /execution/tasks/running", status == 200, f"({status})")

    # 最近任务
    status, d = http("GET", "/execution/tasks/recent", token=token)
    check("GET /execution/tasks/recent", status == 200, f"({status})")

    # ================= TaskDetail =================
    print("\n[10] TaskDetail 任务详情 (等待执行完成)")
    # 等待任务执行
    time.sleep(3)
    status, d = http("GET", f"/execution/tasks/{task_id}", token=token)
    check("GET /execution/tasks/{id} 详情", status == 200, f"({status}) status={get_val(d,'status')}")

    status, d = http("GET", f"/execution/tasks/{task_id}/status", token=token)
    check("GET /execution/tasks/{id}/status", status == 200, f"({status})")

    status, d = http("GET", f"/execution/tasks/{task_id}/logs?tail=100", token=token)
    logs = get_val(d, "logs", get_val(d, "content", default=""))
    check("GET /execution/tasks/{id}/logs", status == 200 and "item_" in str(logs),
          f"({status}) 含日志内容")

    # 暂停/恢复（对已结束任务应为安全处理）
    status, d = http("POST", f"/execution/tasks/{task_id}/pause", token=token)
    check("POST /execution/tasks/{id}/pause", status in (200, 400, 409), f"({status})")

    # 重试：仅允许重试失败/超时任务；对已成功任务返回 400 属合理业务规则
    status, d = http("POST", f"/execution/tasks/{task_id}/retry", token=token)
    if status == 200:
        check("POST /execution/tasks/{id}/retry", True, f"(成功重试，新任务 {get_val(d,'task_id')})")
    else:
        check("POST /execution/tasks/{id}/retry(成功任务)",
              status == 400 and "只能重试失败或超时" in str(d),
              f"({status}) {d if isinstance(d,str) else get_val(d,'detail',d)}")

    # ================= Nodes =================
    print("\n[11] Nodes 节点管理")
    status, d = http("GET", "/nodes", token=token)
    check("GET /nodes 列表", status == 200, f"({status})")
    nodes = d if isinstance(d, list) else get_val(d, "items", default=[])
    if nodes:
        nid = nodes[0]["id"]
        status, d = http("GET", f"/nodes/{nid}", token=token)
        check("GET /nodes/{id} 详情", status == 200, f"({status})")
    # 前端健康检查实际是批量 POST /nodes/health-check
    status, d = http("POST", "/nodes/health-check", token=token)
    check("POST /nodes/health-check", status == 200, f"({status})")

    # ================= ServerDetail =================
    print("\n[12] ServerDetail 服务器")
    status, d = http("GET", "/servers", token=token)
    check("GET /servers 列表", status == 200, f"({status})")

    # ================= Users =================
    print("\n[13] Users 用户管理 (admin)")
    status, d = http("GET", "/users?skip=0&limit=50", token=token)
    check("GET /users 列表(admin)", status == 200, f"({status})")
    status, d = http("GET", "/users/roles", token=token)
    check("GET /users/roles", status == 200, f"({status})")

    # ================= 清理 =================
    print("\n[14] 清理联调数据")
    status, d = http("DELETE", f"/spiders/{sid}", token=token)
    check("删除爬虫", status in (200, 204), f"({status})")
    status, d = http("DELETE", f"/projects/{pid}", token=token)
    check("删除项目", status in (200, 204), f"({status})")

    import os
    os.path.exists(code_zip) and os.remove(code_zip)

    # ================= 汇总 =================
    print("\n" + "=" * 60)
    print(f" 联调结果: {PASS} 通过, {FAIL} 失败")
    if FAILURES:
        print(" 失败项:")
        for f in FAILURES:
            print(f"   - {f}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
