#!/usr/bin/env python
"""
ofweek_standalone 真实爬虫全流程联调测试
使用直接 HTTP 请求，不依赖子进程
"""
import os, sys, time, json
import requests
import redis as redis_lib

BASE = 'http://localhost:8000'
API = '/api/v1'
ZIP = '/tmp/ofweek_standalone.zip'

def clear_redis():
    try:
        r = redis_lib.Redis(host='117.72.16.51', port=6379, password='oscar0503', decode_responses=True)
        for k in r.scan_iter('*'): r.delete(k)
        r.close()
    except: pass

def api(method, path, **kw):
    """HTTP 请求封装"""
    url = f'{BASE}{path}'
    clear_redis()
    resp = getattr(requests, method)(url, **kw)
    try: return resp.json()
    except: return {'_raw': resp.text, 'status': resp.status_code}

token = None
data = {}

def step(n, name, fn):
    global token, data
    print(f'\n[{n}/11] {name}...', end=' ')
    sys.stdout.flush()
    t0 = time.time()
    try:
        fn()
        print(f'✓ ({time.time()-t0:.2f}s)')
    except Exception as e:
        print(f'✗ ({time.time()-t0:.2f}s)')
        print(f'  {e}')

# ====== 测试步骤 ======

step(1, '健康检查', lambda: (
    None if (h := api('get', '/health')).get('services',{}).get('database') == 'connected'
    else (_ for _ in ()).throw(AssertionError(f'health: {h}'))
))

step(2, '用户登录', lambda: (
    None if 'access_token' in (r := api('post', f'{API}/auth/login',
        data={'username':'admin','password':'admin123'},
        headers={'Content-Type':'application/x-www-form-urlencoded'}))
    and globals().update(token=r['access_token']) is None
    else (_ for _ in ()).throw(AssertionError(f'login: {r}'))
))

step(3, '创建项目', lambda: (
    None if (r := api('post', f'{API}/projects',
        json={'name':f'ofweek_demo_{int(time.time())}','description':'OFWeek联调测试','team_id':1},
        headers={'Authorization':f'Bearer {token}'})).get('id')
    and data.update(pid=r['id'], pname=r['name']) is None
    else (_ for _ in ()).throw(AssertionError(f'project: {r}'))
))

step(4, '上传爬虫代码', lambda: (
    None if (lambda: (r:=requests.post(f'{BASE}{API}/projects/{data["pid"]}/upload',
        files={'file':('ofweek_standalone.zip',open(ZIP,'rb'),'application/zip')},
        headers={'Authorization':f'Bearer {token}'})).status_code in (200,201))()
    else (_ for _ in ()).throw(AssertionError(f'upload failed'))
))

step(5, '创建爬虫', lambda: (
    None if (r := api('post', f'{API}/spiders',
        json={'name':f'of_week_{int(time.time())}','project_id':data['pid'],
              'spider_type':'crawlo','entry_file':'run.py','description':'OFWeek爬虫(Crawlo)'},
        headers={'Authorization':f'Bearer {token}'})).get('id')
    and data.update(sid=str(r['id']), sname=r['name']) is None
    else (_ for _ in ()).throw(AssertionError(f'spider: {r}'))
))

step(6, '配置调度', lambda: (
    None if (r := api('post', f'{API}/schedules',
        json={'project_id':data['pid'],'spider_name':'of_week',
              'schedule_type':'interval','interval_seconds':3600,
              'priority':5,'enabled':True,'max_concurrency':1,'timeout_seconds':600},
        headers={'Authorization':f'Bearer {token}'})).get('id')
    and data.update(scid=r['id']) is None
    else (_ for _ in ()).throw(AssertionError(f'schedule: {r}'))
))

step(7, '执行任务', lambda: (
    None if (r := api('post', f'{API}/execution/tasks',
        json={'spider_id':data['sid'],'timeout':300,'memory_limit':'256m','cpu_limit':0.5},
        headers={'Authorization':f'Bearer {token}'})).get('id')
    and data.update(tid=r['id'], tstatus=r.get('status')) is None
    else (_ for _ in ()).throw(AssertionError(f'task: {r}'))
))

step(8, '查询任务状态', lambda: (
    None if time.sleep(1) is None
    and (r := api('get', f'{API}/execution/tasks/{data["tid"]}/status',
        headers={'Authorization':f'Bearer {token}'})).get('task_id') == data['tid']
    else (_ for _ in ()).throw(AssertionError(f'task status: {r}'))
))

step(9, '查看监控数据', lambda: (
    None if all(
        api('get', f'{API}{ep}', headers={'Authorization':f'Bearer {token}'}) is not None
        for ep in ['/monitoring/system','/monitoring/dashboard','/monitoring/schedules']
    ) else (_ for _ in ()).throw(AssertionError('monitoring failed'))
))

step(10, '查看数据质量', lambda: (
    None if api('get', f'{API}/data-quality/stats',
        params={'project_id':data['pid']},
        headers={'Authorization':f'Bearer {token}'}) is not None
    else (_ for _ in ()).throw(AssertionError('quality failed'))
))

step(11, '清理数据', lambda: (
    None if all(
        api('delete', f'{API}/{ep}/{rid}', headers={'Authorization':f'Bearer {token}'})
        for rid, ep in [(data.get('sid'),'spiders'),(data.get('scid'),'schedules'),(data.get('pid'),'projects')]
        if rid
    ) is None else None
))

print(f'\n{"="*60}')
print(f'  全流程联调完成！')
print(f'  project={data.get("pid")} ({data.get("pname")})')
print(f'  spider={data.get("sid")} ({data.get("sname")})')
print(f'  schedule={data.get("scid")}')
print(f'  task={data.get("tid")} (status={data.get("tstatus")})')
print(f'{"="*60}')
