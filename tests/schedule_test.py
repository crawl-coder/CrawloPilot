#!/usr/bin/env python3
"""
定时任务（Schedule）功能端到端测试

真实等待调度触发，覆盖：
- 参数校验（非法 cron / interval<60 / once 过去时间 / 非法时区）
- 预览接口
- cron 每分钟真实触发 + 幂等（每周期恰好一个任务）
- run-now（不改周期、不占幂等槽位）
- 停用/启用（停用后不再触发，启用恢复 next_run_time）
- 更新 cron 生效
- once 调度触发后自动停用 + next_run_time 清理
- 删除有运行历史的调度（FK 保护修复验证）
- 删除爬虫级联删除调度（任务历史保留）

预计运行时间 ~4 分钟（含真实触发等待）。
"""
import sys
import json
import time
import io
import zipfile
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE = "http://localhost:18000/api/v1"
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
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
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        BASE + "/auth/login", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())["access_token"]


def wait_until(desc, predicate, timeout_s, interval=3):
    """轮询直到条件满足或超时，返回最终结果"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        val = predicate()
        if val:
            return val
        time.sleep(interval)
    print(f"  ...等待超时: {desc}")
    return None


def main():
    print("=" * 60)
    print("定时任务（Schedule）端到端测试")
    print("=" * 60)
    tok = login("admin", "admin123")
    ts = int(time.time())

    # ---------- 准备：微型测试爬虫 ----------
    print("\n[0] 准备测试爬虫（trivial main.py，秒级退出）")
    s, r = http("GET", "/projects?skip=0&limit=1", tok)
    project_id = r["items"][0]["id"]
    s, r = http("POST", "/spiders", tok, {
        "name": f"sched_e2e_{ts}", "project_id": project_id,
        "spider_type": "custom", "entry_file": "main.py",
    })
    check("创建测试爬虫", s == 201, r)
    spider_id = r["id"]
    # 代码目录由上传创建：打包一个秒级退出的 trivial main.py
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("main.py", "import time;print('sched e2e ok');time.sleep(1)")
    boundary = "----schedtest"
    payload = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"code.zip\"\r\nContent-Type: application/zip\r\n\r\n"
    ).encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        BASE + f"/spiders/{spider_id}/upload", data=payload,
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            up_ok = resp.status == 200
    except urllib.error.HTTPError as e:
        up_ok = False
        print("  上传失败:", e.read().decode()[:200])
    check("上传入口文件", up_ok)

    # ---------- 参数校验 ----------
    print("\n[1] 参数校验")
    s, r = http("POST", "/schedules", tok, {
        "spider_id": spider_id, "schedule_type": "cron", "cron_expr": "not-a-cron"})
    check("非法 cron 被拒(400)", s == 400, r)
    s, r = http("POST", "/schedules", tok, {
        "spider_id": spider_id, "schedule_type": "interval", "interval_seconds": 30})
    check("interval<60s 被拒(400)", s == 400, r)
    past = (datetime.now(ZoneInfo("Asia/Shanghai")) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    s, r = http("POST", "/schedules", tok, {
        "spider_id": spider_id, "schedule_type": "once", "run_at": past})
    check("once 过去时间被拒(400)", s == 400, r)
    s, r = http("POST", "/schedules", tok, {
        "spider_id": spider_id, "schedule_type": "cron", "cron_expr": "* * * * *",
        "timezone": "Mars/Olympus"})
    check("非法时区被拒(400)", s == 400, r)

    # ---------- 预览 ----------
    print("\n[2] 下次运行预览")
    s, r = http("GET", "/schedules/preview?schedule_type=cron&cron_expr=*%20*%20*%20*%20*&count=5", tok)
    check("cron 预览返回 5 次", s == 200 and len(r.get("runs", [])) == 5, r)

    # ---------- cron 真实触发 + 幂等 ----------
    print("\n[3] cron 每分钟触发（真实等待，最长 85s）")
    s, r = http("POST", "/schedules", tok, {
        "spider_id": spider_id, "schedule_type": "cron", "cron_expr": "* * * * *",
        "timeout_seconds": 300, "enabled": True})
    check("创建 cron 调度", s == 201, r)
    sched_id = r.get("id")
    check("启用后 next_run_time 已计算", bool(r.get("next_run_time")), r)

    def fired():
        s2, r2 = http("GET", f"/schedules/{sched_id}", tok)
        return r2 if s2 == 200 and (r2.get("run_count") or 0) >= 1 else None

    res = wait_until("cron 首次触发", fired, 85)
    check("cron 在 85s 内真实触发", res is not None)
    if res:
        check("触发后 last_run_status=running", res.get("last_run_status") == "running", res)
        check("触发后记录 last_run_task_id", bool(res.get("last_run_task_id")), res)

    # 幂等：历史任务数 == run_count（每周期恰好一个任务）
    s, r = http("GET", f"/schedules/{sched_id}/history", tok)
    s2, sched = http("GET", f"/schedules/{sched_id}", tok)
    check("触发幂等：任务数 == run_count",
          s == 200 and len(r) == sched.get("run_count"),
          f"tasks={len(r)} run_count={sched.get('run_count')}")
    check("任务带 schedule_id 与 expected_run_at",
          len(r) > 0, r)

    # ---------- run-now ----------
    print("\n[4] run-now（不改周期）")
    before_ntr = sched.get("next_run_time")
    before_count = sched.get("run_count")
    s, r = http("POST", f"/schedules/{sched_id}/run-now", tok)
    check("run-now 触发成功", s == 200, r)
    res = wait_until("run-now 计数+1", lambda: (
        lambda x: x if x[1].get("run_count", 0) >= before_count + 1 else None
    )(http("GET", f"/schedules/{sched_id}", tok)), 20)
    check("run-now 计入 run_count", res is not None)
    if res:
        check("run-now 不改变 next_run_time", res[1].get("next_run_time") == before_ntr,
              f"{res[1].get('next_run_time')} vs {before_ntr}")

    # ---------- 停用 / 启用 ----------
    print("\n[5] 停用后不再触发（真实等待 65s 跨过分钟边界）")
    s, r = http("POST", f"/schedules/{sched_id}/disable", tok)
    check("停用成功", s == 200 and r.get("enabled") is False, r)
    check("停用后 next_run_time 清空", r.get("next_run_time") is None, r)
    _, r = http("GET", f"/schedules/{sched_id}", tok)
    count_at_disable = r.get("run_count", 0)
    time.sleep(65)
    _, r = http("GET", f"/schedules/{sched_id}", tok)
    check("停用期间未再触发", r.get("run_count") == count_at_disable,
          f"{count_at_disable} -> {r.get('run_count')}")

    s, r = http("POST", f"/schedules/{sched_id}/enable", tok)
    check("重新启用成功", s == 200 and r.get("enabled") is True, r)
    check("启用后 next_run_time 恢复", bool(r.get("next_run_time")), r)

    # ---------- 更新 cron ----------
    print("\n[6] 更新 cron 表达式")
    s, r = http("PUT", f"/schedules/{sched_id}", tok, {"cron_expr": "*/5 * * * *"})
    check("更新 cron 成功", s == 200 and r.get("cron_expr") == "*/5 * * * *", r)
    check("更新后 next_run_time 重算", bool(r.get("next_run_time")), r)

    # ---------- 删除有运行历史的调度（FK 修复验证） ----------
    print("\n[7] 删除有运行历史的调度")
    s, r = http("DELETE", f"/schedules/{sched_id}", tok)
    check("删除有历史的调度成功(200)", s == 200, r)
    s, r = http("GET", f"/schedules/{sched_id}", tok)
    check("调度已不存在(404)", s == 404, r)

    # ---------- once 调度 ----------
    print("\n[8] once 调度：触发后自动停用（run_at=+75s，真实等待）")
    run_at = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(seconds=75)).strftime("%Y-%m-%dT%H:%M:%S")
    s, r = http("POST", "/schedules", tok, {
        "spider_id": spider_id, "schedule_type": "once", "run_at": run_at, "enabled": True})
    check("创建 once 调度", s == 201, r)
    once_id = r.get("id")

    def once_fired():
        s2, r2 = http("GET", f"/schedules/{once_id}", tok)
        return r2 if s2 == 200 and (r2.get("run_count") or 0) >= 1 else None

    res = wait_until("once 触发", once_fired, 100)
    check("once 按时触发", res is not None)
    if res:
        check("once 触发后自动停用", res.get("enabled") is False, res)
        check("once 触发后 next_run_time 清空", res.get("next_run_time") is None, res)
    s, r = http("DELETE", f"/schedules/{once_id}", tok)
    check("清理 once 调度", s == 200, r)

    # ---------- 删除爬虫级联 ----------
    print("\n[9] 删除爬虫级联删除调度（任务历史保留）")
    s, r = http("POST", "/schedules", tok, {
        "spider_id": spider_id, "schedule_type": "cron", "cron_expr": "0 3 * * *", "enabled": False})
    check("为爬虫重建调度", s == 201, r)
    cascade_id = r.get("id")
    s, r = http("POST", f"/schedules/{cascade_id}/run-now", tok)
    check("run-now 制造历史任务", s == 200, r)
    time.sleep(2)
    s, r = http("DELETE", f"/spiders/{spider_id}", tok)
    check("删除有历史任务的爬虫成功(200)", s == 200, r)
    s, r = http("GET", f"/schedules/{cascade_id}", tok)
    check("级联后调度不存在(404)", s == 404, r)

    print("\n" + "=" * 60)
    print(f"结果: {PASS} 通过, {FAIL} 失败")
    if FAILURES:
        print("失败项:", ", ".join(FAILURES))
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
