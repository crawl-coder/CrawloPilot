#!/usr/bin/env python3
"""
CrawloPilot 爬虫部署完整流程测试 (本地非Docker模式)

测试覆盖:
  逐节点测试:
    节点1: 用户认证 (登录/Token刷新)
    节点2: 项目管理 (创建/查询/更新/删除)
    节点3: 爬虫管理 (创建/查询/更新)
    节点4: 代码准备 (本地上传示例爬虫)
    节点5: 爬虫执行 (本地进程模式, 非Docker)
    节点6: 任务状态查询和日志查看
    节点7: 停止爬虫

  端到端串联测试:
    完整流程: 登录 → 创建项目 → 创建爬虫 → 准备代码 → 执行 → 
              监控状态 → 查看日志 → 停止 → 验证结果

运行方式:
    python tests/test_deployment_flow.py
"""

import os
import sys
import time
import json
import shutil
import subprocess
import traceback
from pathlib import Path
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
EXAMPLE_DIR = PROJECT_ROOT / "examples" / "ofweek_standalone"

# 添加 backend 到 sys.path
sys.path.insert(0, str(BACKEND_DIR))

import requests

# 颜色输出 (Windows 兼容)
IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    os.system('color')  # 启用 Windows 控制台颜色

GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'


# ============================================================
# 配置
# ============================================================
BASE_URL = os.environ.get('TEST_BASE_URL', 'http://localhost:18000')
API_PREFIX = '/api/v1'
TEST_PROJECT_NAME = f"test_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TEST_SPIDER_NAME = f"test_spider_{datetime.now().strftime('%H%M%S')}"

# 全局测试数据
ctx = {
    'token': None,
    'user': None,
    'project_id': None,
    'project_name': TEST_PROJECT_NAME,
    'spider_id': None,
    'spider_name': TEST_SPIDER_NAME,
    'task_id': None,
    'test_results': [],
}


# ============================================================
# 工具函数
# ============================================================

def header(title):
    print(f"\n{'='*70}")
    print(f"{BLUE}{title}{NC}")
    print('='*70)


def step(num, title):
    print(f"\n{GREEN}[节点 {num}]{NC} {title}")
    print('-'*70)


def ok(msg):
    print(f"{GREEN}  ✅ {msg}{NC}")


def fail(msg):
    print(f"{RED}  ❌ {msg}{NC}")


def info(msg):
    print(f"{YELLOW}  ℹ️  {msg}{NC}")


def data(label, d):
    print(f"{CYAN}  📋 {label}:{NC}")
    if isinstance(d, dict):
        for k, v in d.items():
            val = str(v)[:80] + ('...' if len(str(v)) > 80 else '')
            print(f"     {k}: {val}")
    elif isinstance(d, list):
        print(f"     共 {len(d)} 项")
    else:
        print(f"     {d}")


def auth_headers():
    if ctx['token']:
        return {"Authorization": f"Bearer {ctx['token']}"}
    return {}


def api_get(path, **kwargs):
    """GET 请求"""
    kwargs.setdefault('timeout', 10)
    kwargs.setdefault('headers', auth_headers())
    return requests.get(f"{BASE_URL}{API_PREFIX}{path}", **kwargs)


def api_post(path, json_data=None, **kwargs):
    """POST 请求"""
    kwargs.setdefault('timeout', 10)
    kwargs.setdefault('headers', auth_headers())
    if json_data:
        return requests.post(f"{BASE_URL}{API_PREFIX}{path}", json=json_data, **kwargs)
    return requests.post(f"{BASE_URL}{API_PREFIX}{path}", **kwargs)


def api_put(path, json_data=None, **kwargs):
    """PUT 请求"""
    kwargs.setdefault('timeout', 10)
    kwargs.setdefault('headers', auth_headers())
    return requests.put(f"{BASE_URL}{API_PREFIX}{path}", json=json_data, **kwargs)


def api_delete(path, **kwargs):
    """DELETE 请求"""
    kwargs.setdefault('timeout', 10)
    kwargs.setdefault('headers', auth_headers())
    return requests.delete(f"{BASE_URL}{API_PREFIX}{path}", **kwargs)


def record(name, passed, msg=''):
    """记录测试结果"""
    status = 'PASS' if passed else 'FAIL'
    ctx['test_results'].append({'name': name, 'status': status, 'message': msg})
    if passed:
        ok(f"{name} - PASS")
    else:
        fail(f"{name} - FAIL: {msg}")
    return passed


def check_api(desc, resp, expected_status=(200, 201), key=None):
    """检查 API 响应"""
    try:
        body = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
    except:
        body = {'raw': resp.text[:200]}

    if resp.status_code in (expected_status if isinstance(expected_status, tuple) else (expected_status,)):
        if key is not None:
            val = body if isinstance(body, (str, type(None))) else body.get(key)
            return record(desc, val is not None, f"缺少字段: {key}"), body
        return record(desc, True, f"status={resp.status_code}"), body
    else:
        return record(desc, False, f"status={resp.status_code}, body={str(body)[:200]}"), body


# ============================================================
# 逐节点测试
# ============================================================

def test_node1_auth():
    """节点1: 用户认证"""
    header("节点1: 用户认证测试")
    
    # 1.1 登录
    step(1.1, "用户登录")
    resp = api_post("/auth/login", data={"username": "admin", "password": "admin123"})
    passed, body = check_api("登录获取Token", resp, key='access_token')
    if passed:
        ctx['token'] = body.get('access_token')
        data("Token", ctx['token'][:30] + '...')
    else:
        info("尝试注册新用户...")
        resp = api_post("/auth/register", json_data={
            "username": "admin",
            "email": "admin@test.com",
            "password": "admin123",
            "full_name": "Admin"
        })
        if resp.status_code in (200, 201, 400):
            resp = api_post("/auth/login", data={"username": "admin", "password": "admin123"})
            p2, body2 = check_api("重新登录", resp, key='access_token')
            if p2:
                ctx['token'] = body2.get('access_token')
    
    # 1.2 获取当前用户
    step(1.2, "获取当前用户信息")
    resp = api_get("/auth/me")
    passed, body = check_api("获取用户信息", resp, key='username')
    if passed:
        ctx['user'] = body
        data("用户", {'username': body.get('username'), 'email': body.get('email')})
    
    return ctx['token'] is not None


def test_node2_projects():
    """节点2: 项目管理"""
    header("节点2: 项目管理测试")
    
    # 2.1 创建项目
    step(2.1, "创建项目")
    # 获取用户的团队
    from app.core.database import SessionLocal
    from app.models import TeamMember
    db = SessionLocal()
    try:
        membership = db.query(TeamMember).filter(TeamMember.user_id == ctx['user']['id']).first()
        team_id = membership.team_id if membership else 1
    finally:
        db.close()
    
    resp = api_post("/projects", json_data={
        "name": TEST_PROJECT_NAME,
        "description": "本地部署完整流程测试项目",
        "framework": "crawlo",
        "team_id": team_id
    })
    passed, body = check_api("创建项目", resp, key='id')
    if passed:
        ctx['project_id'] = body.get('id')
        data("项目", {'id': ctx['project_id'], 'name': body.get('name')})
    else:
        # 尝试查询已有项目
        info("创建失败, 尝试查询已有项目...")
        resp = api_get("/projects")
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            if items:
                ctx['project_id'] = items[0].get('id')
                ctx['project_name'] = items[0].get('name')
                ok(f"使用已有项目: {ctx['project_name']} (id={ctx['project_id']})")
            else:
                fail("无可用项目")
                return False
    
    # 2.2 查询项目列表
    step(2.2, "查询项目列表")
    resp = api_get("/projects")
    passed, body = check_api("查询项目列表", resp)
    if passed:
        items = body.get('items', [])
        data("项目列表", f"共 {body.get('total', len(items))} 个项目")
    
    # 2.3 查询项目详情
    if ctx['project_id']:
        step(2.3, "查询项目详情")
        resp = api_get(f"/projects/{ctx['project_id']}")
        check_api("查询项目详情", resp, key='name')
    
    return ctx['project_id'] is not None


def test_node3_spiders():
    """节点3: 爬虫管理"""
    header("节点3: 爬虫管理测试")
    
    if not ctx['project_id']:
        fail("缺少项目ID")
        return False
    
    # 3.1 创建爬虫
    step(3.1, "创建爬虫")
    resp = api_post("/spiders", json_data={
        "name": TEST_SPIDER_NAME,
        "project_id": ctx['project_id'],
        "description": "测试爬虫 - 本地部署流程",
        "spider_type": "crawlo",
        "entry_file": "run.py",
        "spider_name": "of_week"
    })
    passed, body = check_api("创建爬虫", resp, key='id')
    if passed:
        ctx['spider_id'] = body.get('id')
        data("爬虫", {'id': ctx['spider_id'], 'name': body.get('name'), 'type': body.get('spider_type')})
    else:
        info("尝试查询已有爬虫...")
        resp = api_get("/spiders", params={"project_id": ctx['project_id']})
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            if items:
                ctx['spider_id'] = items[0].get('id')
                ctx['spider_name'] = items[0].get('name')
                ok(f"使用已有爬虫: {ctx['spider_name']} (id={ctx['spider_id']})")
            else:
                fail("无可用爬虫")
                return False
    
    # 3.2 查询爬虫列表
    step(3.2, "查询爬虫列表")
    resp = api_get("/spiders")
    passed, body = check_api("查询爬虫列表", resp)
    if passed:
        items = body.get('items', [])
        data("爬虫列表", f"共 {body.get('total', len(items))} 个爬虫")
    
    # 3.3 查询爬虫详情
    if ctx['spider_id']:
        step(3.3, "查询爬虫详情")
        resp = api_get(f"/spiders/{ctx['spider_id']}")
        check_api("查询爬虫详情", resp, key='name')
    
    # 3.4 更新爬虫
    if ctx['spider_id']:
        step(3.4, "更新爬虫信息")
        resp = api_put(f"/spiders/{ctx['spider_id']}", json_data={
            "status": "active",
            "description": "已更新 - 本地部署测试爬虫"
        })
        check_api("更新爬虫状态为active", resp)
    
    return ctx['spider_id'] is not None


def test_node4_code_setup():
    """节点4: 代码准备 (本地上传示例爬虫)"""
    header("节点4: 代码准备测试")
    
    if not ctx['project_id'] or not ctx['spider_id']:
        fail("缺少项目ID或爬虫ID")
        return False
    
    # 4.1 复制示例爬虫代码到 uploads 目录
    step(4.1, "复制示例爬虫到上传目录")
    
    # 目标目录: backend/uploads/project_{pid}/spider_{sid}/
    upload_base = os.path.join(str(BACKEND_DIR), 'uploads')
    target_dir = os.path.join(
        upload_base,
        f"project_{ctx['project_id']}",
        f"spider_{ctx['spider_id']}"
    )
    os.makedirs(target_dir, exist_ok=True)
    
    if EXAMPLE_DIR.exists():
        try:
            # 复制整个示例目录
            for item in EXAMPLE_DIR.iterdir():
                src = str(item)
                dst = os.path.join(target_dir, item.name)
                if item.is_dir():
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            
            ok(f"示例爬虫已复制到: {target_dir}")
            
            # 列出文件
            files = list(Path(target_dir).rglob('*.py'))
            for f in files:
                info(f"  {f.relative_to(target_dir)}")
            
            # 4.2 创建简单测试爬虫 (不依赖 crawlo 包, 用于演示)
            step(4.2, "创建简化测试爬虫 (mock)")
            create_mock_spider(target_dir)
            
            return True
        except Exception as e:
            fail(f"复制失败: {e}")
            return False
    else:
        info(f"示例目录不存在: {EXAMPLE_DIR}")
        # 创建简单的 mock 爬虫
        step(4.1, "创建简化测试爬虫")
        os.makedirs(target_dir, exist_ok=True)
        create_mock_spider(target_dir)
        return True


def create_mock_spider(target_dir):
    """创建一个不依赖 crawlo 的简单模拟爬虫，输出符合 CrawloPilot 日志格式的内容"""
    run_py = os.path.join(target_dir, 'run.py')
    
    code = '''#!/usr/bin/env python3
"""简化测试爬虫 - 用于 CrawloPilot 本地执行测试"""

import time
import sys
from datetime import datetime

def log(level, msg):
    """输出 Crawlo 格式的日志"""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{ts} [{level}] {msg}", flush=True)

def main():
    spider_name = "test_spider"
    
    log("INFO", f"Spider {spider_name} started")
    log("INFO", "=" * 60)
    log("INFO", f"任务 ID: {__import__('os').environ.get('TASK_ID', 'N/A')}")
    log("INFO", f"爬虫名称: {spider_name}")
    
    total_pages = 5
    total_items = 20
    
    for i in range(1, total_pages + 1):
        items_this_page = i * 4
        log("INFO", f"Crawled {i} pages, {items_this_page} items")
        
        # 模拟爬取延迟
        time.sleep(1)
        
        if i == 3:
            log("WARNING", "模拟一次重试...")
    
    log("INFO", "=" * 60)
    log("INFO", f"Spider {spider_name} finished")
    log("INFO", f"总计: {total_pages} pages, {total_items} items")

if __name__ == '__main__':
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        log("WARNING", "Spider interrupted by user")
        sys.exit(130)
    except Exception as e:
        log("ERROR", f"Spider failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
'''
    
    with open(run_py, 'w', encoding='utf-8') as f:
        f.write(code)
    
    ok(f"创建测试爬虫: {run_py}")
    
    # 如果示例爬虫存在且有正确的入口，也拷贝 spiders
    spider_dir = os.path.join(target_dir, 'spiders')
    os.makedirs(spider_dir, exist_ok=True)
    init_file = os.path.join(spider_dir, '__init__.py')
    if not os.path.exists(init_file):
        Path(init_file).touch()
    
    # 同时创建一个 crawlo.cfg
    cfg_file = os.path.join(target_dir, 'crawlo.cfg')
    if not os.path.exists(cfg_file):
        with open(cfg_file, 'w') as f:
            f.write('[settings]\ndefault = settings\n')


def test_node5_execute_spider():
    """节点5: 爬虫执行 (本地进程模式)"""
    header("节点5: 爬虫执行测试 (本地进程模式)")
    
    if not ctx['spider_id']:
        fail("缺少爬虫ID")
        return False
    
    step(5.1, "触发爬虫执行")
    resp = api_post(f"/spiders/{ctx['spider_id']}/run")
    passed, body = check_api("执行爬虫", resp, key='task_id')
    
    if passed:
        ctx['task_id'] = body.get('task_id')
        data("执行结果", {
            'task_id': ctx['task_id'],
            'mode': body.get('mode', 'unknown'),
            'message': body.get('message')
        })
        
        step(5.2, "等待爬虫启动并查询状态")
        time.sleep(3)  # 给进程一点启动时间
        
        # 通过 API 查询状态
        resp = api_get(f"/execution/tasks/{ctx['task_id']}/status")
        passed2, body2 = check_api("查询任务状态(API)", resp)
        if passed2:
            data("进程状态(API)", {
                'db_status': body2.get('db_status'),
                'container_status': body2.get('container_status'),
                'started_at': body2.get('started_at'),
                'duration': body2.get('duration'),
            })
            return True
        else:
            info("API查询失败, 尝试直接查询 LocalExecutor")
            from app.services.local_executor import get_local_executor
            local_executor = get_local_executor()
            status = local_executor.get_task_status(str(ctx['task_id']))
            if status:
                data("进程状态(直接)", status)
                return True
            else:
                info("进程可能已完成或未找到（将在节点6中验证）")
                return True
    
    return False


def test_node6_task_status_and_logs():
    """节点6: 任务状态查询和日志"""
    header("节点6: 任务状态和日志测试")
    
    if not ctx['task_id']:
        fail("缺少任务ID")
        return False
    
    # 6.1 通过 API 查询任务状态
    step(6.1, "查询任务状态 (API)")
    resp = api_get(f"/execution/tasks/{ctx['task_id']}/status")
    passed, body = check_api("查询任务状态", resp)
    if passed:
        data("任务状态", {
            'db_status': body.get('db_status'),
            'container_status': body.get('container_status'),
            'started_at': body.get('started_at'),
            'duration': body.get('duration'),
            'error_message': body.get('error_message', '')[:80] if body.get('error_message') else None,
        })
    
    # 6.2 通过直接查询等待任务完成
    step(6.2, "等待任务执行完成...")
    max_wait = 35
    completed = False
    
    from app.services.local_executor import get_local_executor
    local_executor = get_local_executor()
    
    for i in range(max_wait):
        status = local_executor.get_task_status(str(ctx['task_id']))
        
        if status:
            current_status = status.get('status', 'unknown')
            exit_code = status.get('exit_code')
            
            if exit_code is not None:
                # 进程已结束
                completed = True
                info(f"任务完成! status={current_status}, exit_code={exit_code}")
                data("完成指标", {
                    'pages_crawled': status.get('pages_crawled', 0),
                    'items_scraped': status.get('items_scraped', 0),
                    'errors_count': status.get('errors_count', 0),
                })
                break
            elif current_status in ('success', 'failed', 'cancelled', 'timeout'):
                # DB状态已更新为终态
                completed = True
                info(f"任务终态: status={current_status}")
                data("完成指标", {
                    'pages_crawled': status.get('pages_crawled', 0),
                    'items_scraped': status.get('items_scraped', 0),
                    'errors_count': status.get('errors_count', 0),
                })
                break
            elif i % 5 == 0:
                info(f"等待中... 当前状态: {current_status}")
        else:
            if i % 5 == 0:
                info(f"等待中... 状态查询返回 None (可能进程尚未启动)")
        
        time.sleep(1)
    
    if not completed:
        info("任务仍在运行或已超时等待")
    
    # 6.3 查看日志
    step(6.3, "查看任务日志")
    resp = api_get(f"/execution/tasks/{ctx['task_id']}/logs", params={"tail": 50})
    passed, body = check_api("获取任务日志(API)", resp)
    if passed:
        logs = body.get('logs', '')
        if logs:
            info("任务日志 (最后 20 行):")
            print('-'*60)
            log_lines = logs.split('\n')
            for line in log_lines[-20:]:
                if line.strip():
                    print(f"  {line}")
            print('-'*60)
            
            # 验证日志包含关键信息
            checks = [
                ('started' in logs.lower() or 'INFO' in logs, "包含日志内容"),
                ('pages' in logs.lower() or 'items' in logs.lower(), "包含 pages/items 统计"),
                (len(logs.strip()) > 0, "日志非空"),
            ]
            for check_passed, desc in checks:
                record(f"日志-{desc}", check_passed)
        else:
            # 尝试直接查询
            info("API返回空日志, 尝试直接查询...")
            logs_direct = local_executor.get_task_logs(str(ctx['task_id']), tail=50)
            if logs_direct and logs_direct.strip():
                info("直接查询日志 (最后 20 行):")
                print('-'*60)
                for line in logs_direct.split('\n')[-20:]:
                    if line.strip():
                        print(f"  {line}")
                print('-'*60)
                record("日志-直接查询成功", True)
            else:
                info("无日志内容")
                record("日志-无内容", False)
    
    return True


def test_node7_stop_spider():
    """节点7: 停止爬虫"""
    header("节点7: 停止爬虫测试")
    
    if not ctx['spider_id']:
        fail("缺少爬虫ID")
        return False
    
    step(7.1, "停止爬虫")
    # 先创建一个新任务再用 stop 终止
    resp = api_post(f"/spiders/{ctx['spider_id']}/run")
    passed, body = check_api("创建测试任务", resp, key='task_id')
    
    if passed:
        test_task_id = body.get('task_id')
        time.sleep(1)
        
        # 停止
        resp = api_post(f"/spiders/{ctx['spider_id']}/stop", params={"task_id": test_task_id})
        passed, body = check_api("停止任务", resp)
        if passed:
            data("停止结果", body)
    
    return True


# ============================================================
# 端到端串联测试
# ============================================================

def test_e2e_full_flow():
    """端到端串联测试: 完整部署流程"""
    header("端到端串联测试: 完整爬虫部署流程")
    info("本地非Docker模式")
    print(f"\n  流程: 登录 → 创建项目 → 创建爬虫 → 上传代码 → 执行 → 监控 → 停止")
    print(f"  模式: 本地进程 (非Docker)")
    
    e2e_ctx = {
        'token': None,
        'project_id': None,
        'spider_id': None,
        'task_id': None,
    }
    
    errors = []
    
    try:
        # 1. 登录
        step("E2E-1", "登录平台")
        resp = api_post("/auth/login", data={"username": "admin", "password": "admin123"})
        if resp.status_code != 200:
            errors.append("登录失败")
            raise Exception("登录失败")
        e2e_ctx['token'] = resp.json()['access_token']
        ctx['token'] = e2e_ctx['token']  # 更新全局 token
        ok("登录成功")
        
        # 2. 创建项目
        step("E2E-2", "创建项目")
        e2e_project_name = f"e2e_test_{datetime.now().strftime('%H%M%S')}"
        resp = api_post("/projects", json_data={
            "name": e2e_project_name,
            "description": "端到端测试项目",
            "framework": "crawlo",
            "team_id": 1
        })
        if resp.status_code not in (200, 201):
            errors.append(f"创建项目失败: {resp.status_code}")
            raise Exception("创建项目失败")
        e2e_ctx['project_id'] = resp.json().get('id')
        ok(f"项目创建成功: id={e2e_ctx['project_id']}")
        
        # 3. 创建爬虫
        step("E2E-3", "创建爬虫")
        e2e_spider_name = f"e2e_spider_{datetime.now().strftime('%H%M%S')}"
        resp = api_post("/spiders", json_data={
            "name": e2e_spider_name,
            "project_id": e2e_ctx['project_id'],
            "description": "端到端测试爬虫",
            "spider_type": "crawlo",
            "entry_file": "run.py",
            "spider_name": "test_spider"
        })
        if resp.status_code not in (200, 201):
            errors.append(f"创建爬虫失败: {resp.status_code}")
            raise Exception("创建爬虫失败")
        e2e_ctx['spider_id'] = resp.json().get('id')
        ok(f"爬虫创建成功: id={e2e_ctx['spider_id']}")
        
        # 4. 上传代码
        step("E2E-4", "准备爬虫代码")
        upload_base = os.path.join(str(BACKEND_DIR), 'uploads')
        target_dir = os.path.join(
            upload_base,
            f"project_{e2e_ctx['project_id']}",
            f"spider_{e2e_ctx['spider_id']}"
        )
        os.makedirs(target_dir, exist_ok=True)
        create_mock_spider(target_dir)
        ok(f"代码已准备: {target_dir}")
        
        # 5. 执行爬虫
        step("E2E-5", "执行爬虫 (本地模式)")
        resp = api_post(f"/spiders/{e2e_ctx['spider_id']}/run")
        if resp.status_code not in (200, 201):
            errors.append(f"执行爬虫失败: {resp.status_code}")
            raise Exception("执行失败")
        e2e_ctx['task_id'] = resp.json().get('task_id')
        mode = resp.json().get('mode', 'unknown')
        ok(f"爬虫已启动: task_id={e2e_ctx['task_id']}, mode={mode}")
        
        # 6. 监控任务状态
        step("E2E-6", "监控任务状态")
        from app.services.local_executor import get_local_executor
        local_executor = get_local_executor()
        
        completed = False
        for i in range(35):
            status = local_executor.get_task_status(str(e2e_ctx['task_id']))
            if status:
                exit_code = status.get('exit_code')
                current_status = status.get('status', 'unknown')
                
                if exit_code is not None:
                    completed = True
                    ok(f"任务完成: exit_code={exit_code}, status={current_status}")
                    data("E2E指标", {
                        'pages_crawled': status.get('pages_crawled', 0),
                        'items_scraped': status.get('items_scraped', 0),
                        'errors_count': status.get('errors_count', 0),
                    })
                    break
                elif current_status in ('success', 'failed', 'cancelled', 'timeout'):
                    completed = True
                    ok(f"任务终态: status={current_status}")
                    break
                elif i % 5 == 0:
                    info(f"等待中... 状态: {current_status}")
            time.sleep(1)
        
        if not completed:
            info("任务仍在运行 (可能超时)")
        
        # 7. 查看日志
        step("E2E-7", "查看任务日志")
        time.sleep(1)
        
        # 先尝试通过 API 获取
        resp = api_get(f"/execution/tasks/{e2e_ctx['task_id']}/logs", params={"tail": 30})
        api_logs = ''
        if resp.status_code == 200:
            api_logs = resp.json().get('logs', '')
        
        # 同时尝试直接获取
        logs = local_executor.get_task_logs(str(e2e_ctx['task_id']), tail=30)
        
        # 优先使用非空日志
        display_logs = logs if (logs and logs.strip() and '无日志' not in logs) else api_logs
        
        if display_logs and display_logs.strip():
            info("任务日志:")
            print('-'*60)
            for line in display_logs.split('\n')[-15:]:
                if line.strip():
                    print(f"  {line}")
            print('-'*60)
            ok("日志获取成功")
        else:
            info("日志暂不可用（进程可能仍在写入或已清理）")
        
        # 8. 验证数据库记录
        step("E2E-8", "验证数据库任务记录")
        from app.core.database import SessionLocal
        from app.models import TaskInstance
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(
                TaskInstance.id == e2e_ctx['task_id']
            ).first()
            if task:
                ok(f"数据库记录: status={task.status}, "
                   f"started_at={task.started_at}, "
                   f"finished_at={task.finished_at}, "
                   f"duration={task.duration}, "
                   f"pages={task.pages_crawled}, items={task.items_scraped}, "
                   f"errors={task.errors_count}")
            else:
                info("任务记录未找到 (可能ID类型不匹配)")
        finally:
            db.close()
        
        # 打印端到端结果
        print(f"\n{GREEN}{'='*60}{NC}")
        print(f"{GREEN}  端到端测试完成!{NC}")
        print(f"{GREEN}{'='*60}{NC}")
        data("E2E数据", {
            '项目ID': e2e_ctx['project_id'],
            '爬虫ID': e2e_ctx['spider_id'],
            '任务ID': e2e_ctx['task_id'],
            '执行模式': mode if 'mode' in dir() else 'unknown',
            '任务完成': completed,
            '错误数': len(errors)
        })
        
    except Exception as e:
        fail(f"端到端测试中断: {e}")
        traceback.print_exc()
    
    return len(errors) == 0


# ============================================================
# 主测试入口
# ============================================================

def check_backend_health():
    """检查后端服务是否运行"""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            ok(f"后端服务运行中: {BASE_URL}")
            return True
    except Exception:
        pass
    
    fail(f"后端服务未运行: {BASE_URL}")
    info("请先启动后端: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 18000")
    return False


def print_test_summary():
    """打印测试总结"""
    header("测试总结")
    
    results = ctx['test_results']
    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    
    print(f"\n  总计: {total} 个测试项")
    print(f"  {GREEN}通过: {passed}{NC}")
    print(f"  {RED}失败: {failed}{NC}")
    print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "  通过率: N/A")
    
    if failed > 0:
        print(f"\n{YELLOW} 失败项详情:{NC}")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"    {RED}✗{NC} {r['name']}: {r['message']}")
    
    print(f"\n{'='*70}")
    if failed == 0:
        print(f"{GREEN}  🎉 所有测试通过!{NC}")
    else:
        print(f"{YELLOW}  ⚠️  有 {failed} 个测试失败，请检查日志{NC}")
    print('='*70)


def main():
    """主函数"""
    print(f"\n{GREEN}{'='*70}{NC}")
    print(f"{GREEN}  CrawloPilot 爬虫部署完整流程测试{NC}")
    print(f"{GREEN}  模式: 本地进程 (非Docker){NC}")
    print(f"{GREEN}{'='*70}{NC}")
    print(f"\n  API 地址: {BASE_URL}")
    print(f"  示例爬虫: {EXAMPLE_DIR}")
    print(f"  时间:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查后端
    if not check_backend_health():
        sys.exit(1)
    
    # ============ 逐节点测试 ============
    header("第一部分: 逐节点独立测试")
    info("每个节点独立测试，验证单个功能模块")
    
    test_node1_auth()
    test_node2_projects()
    test_node3_spiders()
    test_node4_code_setup()
    test_node5_execute_spider()
    test_node6_task_status_and_logs()
    test_node7_stop_spider()
    
    # ============ 端到端串联测试 ============
    header("第二部分: 端到端串联测试")
    info("完整流程串联测试，验证各环节数据流转")
    
    test_e2e_full_flow()
    
    # ============ 打印总结 ============
    print_test_summary()


if __name__ == '__main__':
    main()
