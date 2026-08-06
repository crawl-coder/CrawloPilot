#!/usr/bin/env python3
"""
验证 WebSocket 任务实时推送链路：
1. 登录 -> 建团队项目 -> 建爬虫 -> 上传代码
2. 连接 /ws/tasks/{task_id}
3. 运行爬虫
4. 验证 WebSocket 收到状态与日志推送
"""
import sys
import json
import time
import io
import zipfile
import threading
import urllib.request

import websocket

BASE = "http://localhost:8000"
WS = "ws://localhost:8000"
PASS = 0
FAIL = 0


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
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✅ {name} {detail}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")


def main():
    global PASS, FAIL
    print("=" * 60)
    print(" WebSocket 任务实时推送联调")
    print("=" * 60)

    # 1. 登录
    status, d = http("POST", "/api/v1/auth/login", data=None) if False else _login()
    token = d["access_token"]

    # 2. 建团队项目
    status, d = http("GET", "/api/v1/teams", token=token)
    team_id = (d if isinstance(d, list) else d["items"])[0]["id"]
    uniq = int(time.time())
    status, proj = http("POST", "/api/v1/projects", token=token,
                        json_body={"name": f"ws_proj_{uniq}", "team_id": team_id})
    pid = proj["id"]
    status, spider = http("POST", "/api/v1/spiders", token=token, json_body={
        "name": f"ws_spider_{uniq}", "project_id": pid, "spider_type": "crawlo",
        "entry_file": "main.py", "spider_name": "main"
    })
    sid = spider["id"]

    # 3. 上传代码（用 urllib multipart）
    code_zip = "/tmp/ws_spider.zip"
    with zipfile.ZipFile(code_zip, "w") as zf:
        zf.writestr("main.py",
                    "import time\n"
                    "print('WS_START')\n"
                    "for i in range(3):\n"
                    "    print(f'ws_item_{i}')\n"
                    "    time.sleep(0.5)\n"
                    "print('WS_DONE')\n")
    with open(code_zip, "rb") as f:
        content = f.read()
    boundary = "----ws" + str(uniq)
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"code.zip\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + content + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    req = urllib.request.Request(f"{BASE}/api/v1/spiders/{sid}/upload", data=b"".join(parts),
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        up_status = resp.status
    check("上传代码", up_status == 200, f"({up_status})")

    # 4. 连接 WebSocket（先连接，再运行任务）
    print("\n[WS] 连接 /ws/tasks/{task_id} ...")
    received = []

    def on_message(ws, message):
        received.append(message)
        try:
            msg = json.loads(message)
            print(f"     收到推送: {json.dumps(msg, ensure_ascii=False)[:150]}")
        except Exception:
            print(f"     收到原始: {message[:150]}")

    def on_open(ws):
        print("     ✅ WebSocket 已连接")

    ws = websocket.WebSocketApp(f"{WS}/ws/tasks/pending_ws_test",
                                on_message=on_message, on_open=on_open)
    wst = threading.Thread(target=ws.run_forever, daemon=True)
    wst.start()
    time.sleep(1)

    # 5. 运行爬虫，获得真实 task_id
    status, run = http("POST", f"/api/v1/spiders/{sid}/run", token=token, json_body={})
    task_id = run["task_id"]
    print(f"\n[RUN] 任务已启动 task_id={task_id}")

    # 重新用真实 task_id 连接
    ws.close()
    time.sleep(0.5)
    received.clear()
    ws2 = websocket.WebSocketApp(f"{WS}/ws/tasks/{task_id}",
                                 on_message=on_message, on_open=on_open)
    threading.Thread(target=ws2.run_forever, daemon=True).start()
    time.sleep(1)

    # 等待任务执行完成
    print("\n[WAIT] 等待任务执行(3秒)...")
    time.sleep(4)
    ws2.close()

    # 6. 验证收到的推送内容
    print("\n[VERIFY] 验证 WebSocket 推送")
    got_status = any("status" in m for m in received)
    got_log = any("log" in m or "output" in m or "item_" in m for m in received)
    check("收到状态推送", got_status, f"(共 {len(received)} 条)")
    check("收到日志推送(含爬取数据)", got_log, f"")
    if received:
        print(f"     推送样本: {received[0][:200]}" if received else "")

    # 7. 清理
    http("DELETE", f"/api/v1/spiders/{sid}", token=token)
    http("DELETE", f"/api/v1/projects/{pid}", token=token)
    import os
    os.path.exists(code_zip) and os.remove(code_zip)

    print("\n" + "=" * 60)
    print(f" WebSocket 联调: {PASS} 通过, {FAIL} 失败")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


def _login():
    """登录，返回 (status, dict)"""
    data = "username=admin&password=admin123"
    req = urllib.request.Request(f"{BASE}/api/v1/auth/login", data=data.encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read().decode())


if __name__ == "__main__":
    sys.exit(main())
