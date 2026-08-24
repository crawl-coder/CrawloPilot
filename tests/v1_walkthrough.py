#!/usr/bin/env python3
"""CrawloPilot V1 核心流程走查脚本（API 级端到端）。

走查链路：登录 → 仪表盘 → 项目 → 爬虫 → 在线编辑代码 → 本地运行任务
→ 日志与指标 → 停止 → 重试 → 定时调度（预览/run-now/历史/启停）
→ 节点/服务器/用户只读验证。结束后清理本次创建的数据。
"""
import json
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

BASE = "http://localhost:18000/api/v1"
TOKEN = open("/tmp/cp_token").read().strip() if len(sys.argv) < 2 else sys.argv[1]

results = []


def call(method, path, data=None, form=False, raw=None, timeout=30):
    url = BASE + path if path.startswith("/") else path
    headers = {"Authorization": f"Bearer {TOKEN}"}
    body = None
    if raw is not None:
        body = raw.encode() if isinstance(raw, str) else raw
    elif data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text.strip().startswith(("{", "[")) else text)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text


def step(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    mark = "✅" if ok else "❌"
    print(f"{mark} {name} {('- ' + str(detail)[:160]) if detail and not ok else ''}")
    return ok


RUN_PY = '''import time, datetime
print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] [INFO] v1 walkthrough spider starting")
for i in range(1, 4):
    time.sleep(1)
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] [INFO] Crawled {i*4} pages, {i*2} items")
print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] [ERROR] simulated recoverable error for metric test")
time.sleep(1)
print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] [INFO] Crawled 12 pages, 6 items, finished")
'''

P_NAME = "V1走查-演示项目"
S_NAME = "v1_walkthrough_spider"


def multipart_upload(path, field, filename, content, extra=None):
    boundary = "----crawlowalkthrough"
    parts = []
    if extra:
        for k, v in extra.items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
                 f"Content-Type: application/zip\r\n\r\n".encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    url = BASE + path
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text.strip().startswith(("{", "[")) else text)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text


def make_code_zip():
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("run.py", RUN_PY)
        zf.writestr("requirements.txt", "")
        zf.writestr("README.md", "# v1 walkthrough spider\n")
    return buf.getvalue()


def wait_task(task_id, want_states=("success",), timeout_s=60):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        code, st = call("GET", f"/execution/tasks/{task_id}/status")
        last = st.get("db_status") if isinstance(st, dict) else st
        if last in ("success", "failed", "timeout", "cancelled", "stopped"):
            return last
        time.sleep(2)
    return f"TIMEOUT(last={last})"


# ---------- 0. 健康检查 ----------
code, health = call("GET", "http://localhost:18000/health".replace("/api/v1", ""), )
step("健康检查 /health", code == 200 and health.get("status") == "healthy", health)

# ---------- 1. 仪表盘 ----------
code, dash = call("GET", "/monitoring/dashboard")
step("仪表盘概览统计", code == 200 and isinstance(dash, dict), dash)

# ---------- 2. 项目 ----------
code, teams = call("GET", "/teams")
team_id = (teams[0]["id"] if isinstance(teams, list) and teams else 1)
code, projects = call("GET", "/projects?skip=0&limit=100")
items = projects if isinstance(projects, list) else projects.get("items", [])
existing = [p for p in items if p.get("name") == P_NAME]
if existing:
    proj = existing[0]
    step("项目列表（复用已存在走查项目）", True, proj["id"])
else:
    code, proj = call("POST", "/projects",
                      {"name": P_NAME, "description": "V1 流程重新走查用项目", "team_id": team_id})
    step("创建项目", code == 201, proj)
pid = proj["id"]

code, ver = call("POST", f"/projects/{pid}/versions", {"version": "v1.0-walkthrough", "changelog": "walkthrough"})
step("项目版本管理（新增版本）", code in (200, 201), ver)

# ---------- 3. 爬虫 ----------
code, spiders = call("GET", f"/spiders?project_id={pid}")
slist = spiders if isinstance(spiders, list) else spiders.get("items", [])
existing = [s for s in slist if s.get("name") == S_NAME]
if existing:
    sp = existing[0]
    step("爬虫列表（复用已存在走查爬虫）", True, sp["id"])
else:
    code, sp = call("POST", "/spiders", {
        "name": S_NAME, "project_id": pid,
        "description": "V1 走查：本地模式演示爬虫",
        "spider_type": "custom", "entry_file": "run.py",
    })
    step("创建爬虫", code == 201, sp)
sid = sp["id"]

# ---------- 4. 代码来源：ZIP 上传 + 在线编辑 ----------
code, up = multipart_upload(f"/spiders/{sid}/upload", "file", "v1_walkthrough.zip",
                            make_code_zip())
step("上传 ZIP 代码包并解压", code == 200, up)
code, tree = call("GET", f"/spiders/{sid}/files/tree")
tree_ok = code == 200 and "run.py" in json.dumps(tree)
step("读取爬虫代码文件树（含 run.py）", tree_ok, tree)
code, w = call("POST", f"/spiders/{sid}/files/content",
               {"path": "run.py", "content": RUN_PY})
step("在线编辑器保存 run.py", code == 200 and w.get("success", True), w)
code, r = call("GET", f"/spiders/{sid}/files/content?path=run.py")
got = r.get("content") if isinstance(r, dict) else ""
step("回读文件内容一致", code == 200 and "Crawled" in got)

# ---------- 5. 运行任务（本地执行器）----------
code, task = call("POST", "/execution/tasks", {"spider_id": str(sid)})
step("运行爬虫 → 创建任务", code == 200 and task.get("id"), task)
tid = task["id"] if isinstance(task, dict) else None
final = wait_task(tid)
step(f"任务执行至终态（status={final}）", final == "success")

code, tdet = call("GET", f"/execution/tasks/{tid}")
det = tdet if isinstance(tdet, dict) else {}
metrics_ok = det.get("pages_crawled", det.get("pages")) or det.get("metrics")
step("任务详情可查询", code == 200, det.get("status"))

code, logs = call("GET", f"/execution/tasks/{tid}/logs")
log_text = logs.get("logs") if isinstance(logs, dict) else str(logs)
has_log = log_text and "Crawled" in log_text
step("任务日志落盘且可读（含指标行）", code == 200 and has_log,
     str(log_text)[:120] if not has_log else "")

# 指标解析验证：日志里有 Crawled 12 pages, 6 items + 1 ERROR
m = det.get("metrics") or {}
pages = m.get("pages_crawled") or det.get("pages_crawled") or 0
it = m.get("items_scraped") or det.get("items_scraped") or 0
er = m.get("errors_count") or det.get("errors_count") or 0
step("指标解析 pages/items/errors 回写", (pages, it, er) == (12, 6, 1),
     f"pages={pages}, items={it}, errors={er}")

# ---------- 6. 任务控制：停止 & 重试 ----------
code, task2 = call("POST", "/execution/tasks", {"spider_id": str(sid)})
tid2 = task2["id"]
time.sleep(2)  # 让它进入 running
code, stop_res = call("POST", f"/execution/tasks/{tid2}/stop")
st2 = wait_task(tid2)
step("停止运行中任务", code == 200 and st2 in ("cancelled", "stopped"), st2)

code, retry = call("POST", f"/execution/tasks/{tid2}/retry")
rtid = retry.get("task_id") or retry.get("id") if isinstance(retry, dict) else None
rfinal = wait_task(rtid) if rtid else "no-retry-task"
step("失败任务重试 → 新任务成功", rfinal == "success", f"new_task={rtid}, status={rfinal}")

# ---------- 7. 定时调度 ----------
code, sch = call("POST", "/schedules", {
    "spider_id": sid, "name": "V1走查-每分钟调度",
    "trigger_type": "interval", "interval_seconds": 3600,
    "enabled": True, "max_concurrent": 1,
})
if code >= 400:  # 兼容字段名差异
    code, sch = call("POST", "/schedules", {
        "spider_id": sid, "name": "V1走查-每小时cron",
        "trigger_type": "cron", "cron_expr": "0 * * * *", "enabled": True,
    })
step("创建定时调度", code in (200, 201), sch)
scid = sch.get("id") if isinstance(sch, dict) else None

q = urllib.parse.urlencode({"schedule_type": sch.get("trigger_type", sch.get("schedule_type", "interval")),
                            "interval_seconds": sch.get("interval_seconds") or 3600,
                            "cron_expr": sch.get("cron_expr") or ""})
code, prev = call("GET", f"/schedules/preview?{q}")
step("下次运行时间预览", code == 200, prev)

# run-now 触发后，通过调度历史确认新任务产生
code, hist_before = call("GET", f"/schedules/{scid}/history")
n_before = len(hist_before) if isinstance(hist_before, list) else 0
code, rn = call("POST", f"/schedules/{scid}/run-now")
time.sleep(6)
code, hist_after = call("GET", f"/schedules/{scid}/history")
n_after = len(hist_after) if isinstance(hist_after, list) else 0
rn_task = (hist_after[0].get("id") if isinstance(hist_after, list) and hist_after else None)
rnf = wait_task(rn_task, timeout_s=40) if rn_task else "none"
step("调度 run-now 立即触发任务并执行",
     isinstance(rn, dict) and n_after >= n_before and rnf in ("success",),
     f"resp={rn}, history {n_before}→{n_after}, task={rn_task}, status={rnf}")

code, hist = call("GET", f"/schedules/{scid}/history")
step("调度运行历史可查", code == 200, hist if not isinstance(hist, list) else f"{len(hist)} 条记录")

code, dis = call("POST", f"/schedules/{scid}/disable")
step("调度停用（保留配置）", code == 200 and (dis.get("enabled") is False if isinstance(dis, dict) else True), dis)

# ---------- 8. 节点 / 服务器 / 用户（只读验证）----------
code, servers = call("GET", "/servers")
step("Server 实体列表接口", code == 200, servers)
code, nodes = call("GET", "/nodes")
step("节点列表接口", code == 200, nodes)
code, users = call("GET", "/users")
step("用户管理接口（admin 鉴权）", code == 200, users)
code, tasks_list = call("GET", "/execution/tasks?page=1&page_size=5")
step("任务分页列表接口", code == 200, tasks_list)

# ---------- 9. 清理 ----------
print("\n----- 清理走查数据 -----")
if scid:
    call("DELETE", f"/schedules/{scid}")
    print(f"  已删除调度 #{scid}")
for t in (tid, tid2, rtid):
    if t:
        c, _ = call("DELETE", f"/execution/tasks/{t}")
        print(f"  删除任务 #{t}: {'ok' if c == 200 else c}")
call("DELETE", f"/spiders/{sid}")
print(f"  已删除爬虫 #{sid}")
c, _ = call("DELETE", f"/projects/{pid}")
print(f"  删除项目 #{pid}: {'ok' if c == 200 else c}")

# ---------- 汇总 ----------
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print("\n========== V1 流程走查汇总 ==========")
for name, ok, _detail in results:
    print(("✅" if ok else "❌"), name)
print(f"\n结果: {passed}/{total} 通过")
sys.exit(0 if passed == total else 1)
