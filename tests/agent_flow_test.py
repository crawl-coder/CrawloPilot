#!/usr/bin/env python3
"""
CrawloPilot Agent 模式端到端回归测试 (V2 计划 A5)

真实拉起 agent/crawlo_agent.py 子进程，直连本地控制面，覆盖 Agent 全部 6 个端点：
  register → heartbeat → 领任务(long poll) → 下载代码 → 执行 → 日志上报/终态回报
外加两条关键回归线（2026-08-24 生产实测发现的 F5/F6）：
  - 回报协议一致性：agent(Bearer) 与后端 schema 必须匹配，日志/终态不得 422
  - 节点离线检测：Agent 死后节点必须在心跳窗口外翻 OFFLINE，且健康检查
    不得回写 last_heartbeat（"自我续命"回归）

前置：后端已在本地运行（./start-dev.sh），MySQL 可用。
运行：python3 tests/agent_flow_test.py   （约 2-3 分钟）
"""

import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BASE = os.environ.get("CRAWLOPILOT_BASE", "http://localhost:18000") + "/api/v1"
AGENT_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent", "crawlo_agent.py"))

PASS = 0
FAIL = 0
FAILURES = []
CLEANUP = {"tasks": [], "spiders": [], "project": None, "node": None, "agent_proc": None, "token": None}


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name} {('- ' + str(detail)[:200]) if detail else ''}")
        print(f"  ❌ {name} {str(detail)[:200]}")


def http(method, path, token=None, data=None, form=False, timeout=30):
    url = BASE + path if path.startswith("/") else path
    headers = {}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
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


def multipart_upload(path, filename, content, token):
    boundary = "----agentflowtest"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/zip\r\n\r\n".encode() + content + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    req = urllib.request.Request(
        BASE + path, data=b"".join(parts), method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def make_zip(py_source):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("run.py", py_source)
    return buf.getvalue()


def wait_task_status(token, task_id, want, timeout_s=120):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        _, st = http("GET", f"/execution/tasks/{task_id}/status", token)
        last = st.get("db_status") if isinstance(st, dict) else None
        if last in want:
            return last
        time.sleep(2)
    return f"TIMEOUT(last={last})"


SHORT_SPIDER = '''import time, datetime
print("agent-e2e short spider start", flush=True)
time.sleep(1)
print("[2026-01-01 00:00:00] [INFO] Crawled 12 pages, 6 items", flush=True)
print("[2026-01-01 00:00:00] [ERROR] simulated error for metrics", flush=True)
time.sleep(1)
print("[2026-01-01 00:00:01] [INFO] Crawled 12 pages, 6 items final", flush=True)
'''

LONG_SPIDER = '''import time
print("agent-e2e long spider start", flush=True)
for i in range(30):
    print(f"[INFO] Crawled {i} pages, 0 items tick{i}", flush=True)
    time.sleep(2)
print("[INFO] never reached", flush=True)
'''

MEDIUM_SPIDER = '''import time
print("agent-e2e medium spider start", flush=True)
for i in range(8):
    print(f"[INFO] Crawled {i} pages, 0 items tick{i}", flush=True)
    time.sleep(2)
print("[INFO] Crawled 16 pages, 8 items final", flush=True)
'''


def main():
    # ---------- [1] 前置 ----------
    print("\n[1] 前置检查")
    code, health = http("GET", os.environ.get("CRAWLOPILOT_BASE", "http://localhost:18000") + "/health")
    check("后端 /health 可用", code == 200 and isinstance(health, dict) and health.get("status") == "healthy", health)
    if code != 200:
        print("请先启动后端：./start-dev.sh")
        return 2
    check("agent/crawlo_agent.py 存在", os.path.exists(AGENT_SCRIPT), AGENT_SCRIPT)

    # ---------- [2] 登录与测试数据 ----------
    print("\n[2] 登录并准备项目/爬虫/代码")
    code, tok = http("POST", "/auth/login", data={"username": "admin", "password": "admin123"}, form=True)
    token = tok.get("access_token") if isinstance(tok, dict) else None
    check("admin 登录", code == 200 and token, tok)
    CLEANUP["token"] = token

    code, proj = http("POST", "/projects", token, {"name": "AgentE2E-回归项目", "team_id": 1})
    check("创建项目", code == 201 and proj.get("id"), proj)
    CLEANUP["project"] = proj.get("id")

    def make_spider(name):
        c, s = http("POST", "/spiders", token, {
            "name": name, "project_id": proj["id"], "spider_type": "custom",
            "entry_file": "run.py"})
        check(f"创建爬虫 {name}", c == 201 and s.get("id"), s)
        CLEANUP["spiders"].append(s.get("id"))
        c2, up = multipart_upload(f"/spiders/{s['id']}/upload", "code.zip", make_zip(src), token)
        check(f"上传代码 {name}", c2 == 200, up)
        return s["id"]

    src = SHORT_SPIDER
    sid_short = make_spider("agent_e2e_short")
    src = LONG_SPIDER
    sid_long = make_spider("agent_e2e_long")
    src = MEDIUM_SPIDER
    sid_medium = make_spider("agent_e2e_medium")

    # ---------- [3] 创建 Agent 节点并启动真实 agent 进程 ----------
    print("\n[3] 创建 Agent 节点，拉起 crawlo_agent.py")
    code, node = http("POST", "/nodes", token, {
        "name": f"agent-e2e-{int(time.time())}", "host": "127.0.0.1",
        "connect_type": "agent"})
    check("创建 agent 节点", code in (200, 201) and node.get("id"), node)
    nid = node["id"]
    CLEANUP["node"] = nid

    code, detail = http("GET", f"/nodes/{nid}", token)
    agent_token = detail.get("agent_token") if isinstance(detail, dict) else None
    check("节点详情返回令牌（列表脱敏不适用详情）", bool(agent_token), detail)

    log_file = tempfile.mkstemp(prefix="agent_e2e_", suffix=".log")[1]
    env = dict(os.environ, CRAWLO_AGENT_SKIP_CRAWLO_INSTALL="1")
    proc = subprocess.Popen(
        [sys.executable, AGENT_SCRIPT, "--server", "http://127.0.0.1:18000",
         "--token", agent_token, "--poll-interval", "1"],
        stdout=open(log_file, "wb"), stderr=subprocess.STDOUT, env=env)
    CLEANUP["agent_proc"] = proc
    print(f"  agent pid={proc.pid}, 日志: {log_file}")

    def agent_log():
        try:
            return open(log_file, encoding="utf-8", errors="replace").read()
        except OSError:
            return ""

    t0 = time.time()
    online = False
    while time.time() - t0 < 20:
        code, d = http("GET", f"/nodes/{nid}", token)
        if d.get("status") == "online":
            online = True
            break
        time.sleep(2)
    check("Agent 注册且节点 ONLINE（register+heartbeat 端点）", online,
          agent_log()[-300:])
    check("注册成功出现在 agent 日志", "注册成功" in agent_log())

    # ---------- [4] 成功链路：领任务→下载代码→执行→日志→终态回报 ----------
    print("\n[4] 成功链路（claim/code/logs/report 端点）")
    code, t1 = http("POST", "/execution/tasks", token,
                    {"spider_id": str(sid_short), "node_id": str(nid)})
    check("派发短任务到 agent 节点", code == 200 and t1.get("id"), t1)
    tid1 = t1["id"]
    CLEANUP["tasks"].append(tid1)

    final = wait_task_status(token, tid1, {"success", "failed", "timeout"}, 90)
    check("任务终态 success（含 venv 创建，跳过 crawlo 安装）", final == "success", final)

    code, logs = http("GET", f"/execution/tasks/{tid1}/logs", token)
    log_text = logs.get("logs", "") if isinstance(logs, dict) else ""
    check("日志已回流平台（logs 上报端点正常）", code == 200 and "short spider start" in log_text,
          log_text[:150])
    check("日志包含指标行", "Crawled 12 pages, 6 items" in log_text)

    code, det = http("GET", f"/execution/tasks/{tid1}", token)
    d = det if isinstance(det, dict) else {}
    check("指标回写 pages/items/errors = 12/6/1",
          (d.get("pages_crawled"), d.get("items_scraped"), d.get("errors_count")) == (12, 6, 1),
          {k: d.get(k) for k in ("pages_crawled", "items_scraped", "errors_count")})
    check("deploy_mode = agent", d.get("deploy_mode") == "agent", d.get("deploy_mode"))
    check("回报无 422（F5 回归：agent 与 schema 协议一致）",
          "HTTP 422" not in agent_log(), agent_log()[-300:])

    # ---------- [5] 停止链路 ----------
    print("\n[5] 停止链路")
    code, t2 = http("POST", "/execution/tasks", token,
                    {"spider_id": str(sid_long), "node_id": str(nid)})
    tid2 = t2.get("id")
    CLEANUP["tasks"].append(tid2)
    check("派发长任务", code == 200 and tid2, t2)
    st = wait_task_status(token, tid2, {"running"}, 40)
    check("长任务进入 running", st == "running", st)

    code, _ = http("POST", f"/execution/tasks/{tid2}/stop", token)
    check("发送停止指令", code == 200)
    st = wait_task_status(token, tid2, {"cancelled", "stopped", "failed"}, 25)
    check("任务收敛 cancelled（stop_requested 下发+回报）", st in ("cancelled", "stopped"),
          f"{st}\n{agent_log()[-300:]}")
    check("agent 日志确认收到停止指令",
          f"任务 {tid2} 收到停止指令" in agent_log() or
          f"任务 {tid2} 在准备阶段收到停止指令" in agent_log())

    # ---------- [5b] 并发执行（A8）：两个中等任务同时派发到同一节点 ----------
    print("\n[5b] 并发执行（A8：单 agent 多任务并行）")
    code, tc1 = http("POST", "/execution/tasks", token,
                     {"spider_id": str(sid_medium), "node_id": str(nid)})
    code2, tc2 = http("POST", "/execution/tasks", token,
                      {"spider_id": str(sid_medium), "node_id": str(nid)})
    tid_c1 = tc1.get("id") if isinstance(tc1, dict) else None
    tid_c2 = tc2.get("id") if isinstance(tc2, dict) else None
    CLEANUP["tasks"].extend(filter(None, [tid_c1, tid_c2]))
    check("并发派发两个任务均成功", code == 200 and code2 == 200 and tid_c1 and tid_c2,
          f"task1={tid_c1}, task2={tid_c2}")

    # 等两个任务都进入 running（并发执行）
    for _ in range(15):
        _, s1 = http("GET", f"/execution/tasks/{tid_c1}/status", token)
        _, s2 = http("GET", f"/execution/tasks/{tid_c2}/status", token)
        if s1.get("db_status") == "running" and s2.get("db_status") == "running":
            break
        time.sleep(2)
    both_running = (s1.get("db_status") == "running" and s2.get("db_status") == "running")
    check("两个任务同时处于 running（并发验证）", both_running,
          f"task1={s1.get('db_status')}, task2={s2.get('db_status')}")
    check("agent 日志显示并发提交",
          "已提交（当前并发" in agent_log(),
          agent_log()[-200:])

    # 等两个任务都结束
    f1 = wait_task_status(token, tid_c1, {"success", "failed"}, 40)
    f2 = wait_task_status(token, tid_c2, {"success", "failed"}, 40)
    check("两个并发任务均 success", f1 == "success" and f2 == "success",
          f"task1={f1}, task2={f2}")

    # ---------- [6] 离线检测（F6 回归：无自我续命）----------
    print("\n[6] 离线检测（杀掉 Agent，约需 70 秒观察窗口）")
    _, before = http("GET", f"/nodes/{nid}", token)
    hb_before = before.get("last_heartbeat")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    CLEANUP["agent_proc"] = None

    deadline = time.time() + 100
    offline = False
    while time.time() < deadline:
        code, hc = http("POST", "/nodes/health-check", token, timeout=60)
        results = hc.get("results", []) if isinstance(hc, dict) else []
        mine = [r for r in results if r.get("node_id") == nid]
        if mine and mine[0].get("status") == "offline":
            offline = True
            break
        time.sleep(10)
    check("Agent 死亡后节点翻 OFFLINE（60s 心跳窗口判定）", offline)

    _, after = http("GET", f"/nodes/{nid}", token)
    hb_after = after.get("last_heartbeat")
    check("last_heartbeat 未被回写（自我续命回归）",
          hb_after is not None and hb_before is not None and hb_after <= hb_before,
          f"before={hb_before} after={hb_after}")

    # ---------- 汇总 ----------
    print("\n" + "=" * 50)
    print(f"Agent E2E 结果: {PASS} 通过, {FAIL} 失败")
    if FAILURES:
        print("失败项:")
        for f in FAILURES:
            print("  -", f)
    return 0 if FAIL == 0 else 1


def cleanup():
    print("\n----- 清理 -----")
    p = CLEANUP.get("agent_proc")
    if p and p.poll() is None:
        p.kill()
        print("  已终止 agent 进程")
    token = CLEANUP.get("token")
    if not token:
        return
    for t in CLEANUP["tasks"]:
        if t:
            http("DELETE", f"/execution/tasks/{t}", token)
            print(f"  删除任务 #{t}")
    for s in CLEANUP["spiders"]:
        if s:
            http("DELETE", f"/spiders/{s}", token)
            print(f"  删除爬虫 #{s}")
    if CLEANUP.get("project"):
        http("DELETE", f"/projects/{CLEANUP['project']}", token)
        print(f"  删除项目 #{CLEANUP['project']}")
    if CLEANUP.get("node"):
        http("DELETE", f"/nodes/{CLEANUP['node']}", token)
        print(f"  删除节点 #{CLEANUP['node']}")


if __name__ == "__main__":
    try:
        code = main()
    finally:
        cleanup()
    sys.exit(code)
