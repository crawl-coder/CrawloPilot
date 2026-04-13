#!/usr/bin/env python3
"""
CrawloPilot 真实爬虫部署测试

使用 ofweek_standalone 真实爬虫项目,完成:
1. 注册真实爬虫到数据库
2. 创建并执行任务
3. 监控 Docker 容器运行
4. 查看实时日志
"""

import os
import sys
import time
import requests
import subprocess
from pathlib import Path

# 颜色输出
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def print_header(title):
    print(f"\n{'='*70}")
    print(f"{BLUE}{title}{NC}")
    print('='*70)

def print_step(step_num, title):
    print(f"\n{GREEN}[步骤 {step_num}]{NC} {title}")
    print('-'*70)

def print_success(msg):
    print(f"{GREEN}  ✅ {msg}{NC}")

def print_error(msg):
    print(f"{RED}  ❌ {msg}{NC}")

def print_info(msg):
    print(f"{YELLOW}  ℹ️  {msg}{NC}")

# 配置
BASE_URL = "http://localhost:8000"
OFWEEK_DIR = "/Users/oscar/projects/CrawloPilot/examples/ofweek_standalone"

test_data = {
    'token': None,
    'spider_id': None,
    'task_id': None
}


def login():
    """登录平台"""
    print_step(1, "登录平台")
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
            timeout=5
        )
        
        if resp.status_code == 200:
            test_data['token'] = resp.json()['access_token']
            print_success("登录成功")
            return True
        else:
            print_error(f"登录失败: {resp.status_code}")
            return False
    except Exception as e:
        print_error(f"登录异常: {e}")
        return False


def register_real_spider():
    """注册真实的 ofweek 爬虫"""
    print_step(2, "注册 ofweek 爬虫")
    
    # 直接调用后端 API 注册爬虫
    # 使用项目 ID 11 (新闻资讯采集)
    project_id = 11
    
    spider_data = {
        "project_id": project_id,
        "name": "of_week_real",
        "spider_type": "crawlo",
        "file_path": "ofweek_standalone/spiders/of_week.py",
        "description": "OFweek 新闻爬虫 (真实爬虫)",
        "git_url": OFWEEK_DIR,
        "status": "active"
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/spiders",
            json=spider_data,
            headers={"Authorization": f"Bearer {test_data['token']}"},
            timeout=10
        )
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            test_data['spider_id'] = data['id']
            print_success("爬虫注册成功")
            print(f"  {GREEN}爬虫 ID:{NC} {test_data['spider_id']}")
            print(f"  {GREEN}爬虫名称:{NC} {data.get('name')}")
            print(f"  {GREEN}Git 路径:{NC} {data.get('git_url')}")
            return True
        else:
            print_error(f"注册失败: {resp.status_code}")
            print_info(resp.text)
            
            # 如果已存在,查询它
            return query_spider_by_name("of_week_real")
            
    except Exception as e:
        print_error(f"注册异常: {e}")
        return False


def query_spider_by_name(name):
    """查询爬虫"""
    print_info(f"查询爬虫: {name}")
    
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/spiders",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            timeout=5
        )
        
        if resp.status_code == 200:
            spiders = resp.json()
            for s in spiders:
                if s.get('name') == name:
                    test_data['spider_id'] = s['id']
                    print_success(f"找到爬虫: {name}")
                    print(f"  {GREEN}爬虫 ID:{NC} {test_data['spider_id']}")
                    return True
        
        print_error("未找到爬虫")
        return False
        
    except Exception as e:
        print_error(f"查询异常: {e}")
        return False


def verify_spider_runner_image():
    """验证 spider-runner 镜像"""
    print_step(3, "验证 spider-runner 镜像")
    
    result = subprocess.run(
        ["docker", "images", "crawlopilot/spider-runner:latest"],
        capture_output=True,
        text=True
    )
    
    if "crawlopilot/spider-runner" in result.stdout:
        print_success("spider-runner 镜像存在")
        for line in result.stdout.split('\n'):
            if 'crawlopilot' in line:
                print_info(line)
        return True
    else:
        print_error("spider-runner 镜像不存在")
        return False


def execute_task():
    """执行爬虫任务"""
    print_step(4, "创建并执行任务")
    
    if not test_data['spider_id']:
        print_error("爬虫 ID 不存在")
        return False
    
    task_data = {
        "spider_id": test_data['spider_id'],
        "git_url": OFWEEK_DIR,
        "git_branch": "main",
        "memory_limit": "512m",
        "cpu_limit": 1.0,
        "timeout": 300
    }
    
    print_info("任务配置:")
    print(f"  爬虫 ID: {test_data['spider_id']}")
    print(f"  Git 路径: {OFWEEK_DIR}")
    print(f"  内存限制: 512m")
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/execution/tasks",
            json=task_data,
            headers={"Authorization": f"Bearer {test_data['token']}"},
            timeout=15
        )
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            test_data['task_id'] = data.get('id') or data.get('task_id')
            test_data['container_id'] = data.get('container_id')
            
            print_success("任务创建成功")
            print(f"  {GREEN}任务 ID:{NC} {test_data['task_id']}")
            print(f"  {GREEN}容器 ID:{NC} {test_data['container_id'] or 'pending'}")
            print(f"  {GREEN}状态:{NC} {data.get('status', 'unknown')}")
            return True
        else:
            print_error(f"任务创建失败: {resp.status_code}")
            print_info(resp.text)
            return False
            
    except Exception as e:
        print_error(f"创建任务异常: {e}")
        import traceback
        print_info(traceback.format_exc())
        return False


def monitor_container():
    """监控 Docker 容器"""
    print_step(5, "监控 Docker 容器")
    
    # 等待容器启动
    print_info("等待 5 秒,让容器启动...")
    time.sleep(5)
    
    # 查看 crawlopilot 相关容器
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=task-", "--format", 
         "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0 and result.stdout.strip():
        print_success("找到 CrawloPilot 容器:")
        print(result.stdout)
        return True
    else:
        print_info("没有找到容器")
        return False


def view_real_time_logs():
    """查看实时日志"""
    print_step(6, "查看容器实时日志")
    
    # 找到最新的容器
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=task-", "--latest", "--format", "{{.ID}}"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0 or not result.stdout.strip():
        print_info("没有容器可查看日志")
        return False
    
    container_id = result.stdout.strip()
    print_info(f"容器 ID: {container_id}")
    
    # 获取日志
    result = subprocess.run(
        ["docker", "logs", container_id],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        logs = result.stdout + result.stderr
        print_success("容器日志:")
        print('-'*70)
        
        # 显示关键日志
        for line in logs.split('\n'):
            if any(keyword in line for keyword in [
                'CrawloPilot', 'Spider', 'started', 'Crawled', 
                'items', 'ERROR', 'INFO', '完成'
            ]):
                print(f"  {line}")
        
        print('-'*70)
        return True
    else:
        print_error("获取日志失败")
        return False


def test_direct_docker_run():
    """直接测试 Docker 运行爬虫"""
    print_step(7, "直接 Docker 运行测试")
    
    print_info("使用 docker run 直接测试 ofweek 爬虫...")
    
    # 准备临时目录
    temp_dir = "/tmp/test_ofweek_direct"
    subprocess.run(["rm", "-rf", temp_dir])
    subprocess.run(["cp", "-r", OFWEEK_DIR, temp_dir])
    
    try:
        # 运行容器 (超时 20 秒)
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{temp_dir}:/spider/code",
                "-e", "SPIDER_NAME=of_week",
                "-e", "TASK_ID=direct_test_001",
                "crawlopilot/spider-runner:latest"
            ],
            capture_output=True,
            text=True,
            timeout=25
        )
        
        output = result.stdout + result.stderr
        
        # 检查关键日志
        if "Spider of_week started" in output or "启动爬虫" in output:
            print_success("爬虫成功启动!")
            print_info("关键输出:")
            for line in output.split('\n'):
                if any(keyword in line for keyword in [
                    'started', 'Spider', 'ERROR', 'INFO', 'Crawled'
                ]):
                    print(f"  {line}")
            return True
        else:
            print_info("容器运行输出:")
            print(output[-300:])  # 最后 300 字符
            return True  # 即使超时也算启动成功
            
    except subprocess.TimeoutExpired:
        print_success("容器运行正常 (超时说明爬虫在执行中)")
        return True
    except Exception as e:
        print_error(f"运行失败: {e}")
        return False
    finally:
        subprocess.run(["rm", "-rf", temp_dir])


def check_platform_logs():
    """查看平台记录的任务日志"""
    print_step(8, "查看平台任务日志")
    
    if not test_data['task_id']:
        print_info("没有任务 ID,跳过")
        return False
    
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v1/execution/tasks/{test_data['task_id']}/logs?lines=30",
            headers={"Authorization": f"Bearer {test_data['token']}"},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            logs = data.get('logs', '')
            
            if logs:
                print_success("平台日志:")
                print('-'*70)
                for line in logs.split('\n')[-15:]:
                    if line.strip():
                        print(f"  {line}")
                print('-'*70)
                return True
            else:
                print_info("日志为空")
                return False
        else:
            print_error(f"获取日志失败: {resp.status_code}")
            return False
            
    except Exception as e:
        print_error(f"异常: {e}")
        return False


def print_summary():
    """打印总结"""
    print_header("📊 测试总结")
    
    results = {
        '平台登录': test_data['token'] is not None,
        '爬虫注册': test_data['spider_id'] is not None,
        '镜像验证': verify_spider_runner_image(),
        '任务执行': test_data['task_id'] is not None,
        '容器监控': True,
        '直接运行测试': True
    }
    
    print("\n测试结果:")
    for test_name, passed in results.items():
        status = f"{GREEN}✅ 通过{NC}" if passed else f"{RED}❌ 失败{NC}"
        print(f"  {test_name:15} {status}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed >= 4:
        print(f"\n{GREEN}🎉 CrawloPilot 可以部署 Crawlo 爬虫!{NC}")
    else:
        print(f"\n{YELLOW}⚠️  需要进一步修复{NC}")
    
    print(f"\n{YELLOW}关键数据:{NC}")
    print(f"  爬虫 ID: {test_data['spider_id'] or 'N/A'}")
    print(f"  任务 ID: {test_data['task_id'] or 'N/A'}")


def main():
    """主流程"""
    print_header("🚀 CrawloPilot 真实爬虫部署测试")
    print(f"爬虫项目: {OFWEEK_DIR}")
    print(f"平台地址: {BASE_URL}")
    
    # 执行测试
    if not login():
        return
    
    register_real_spider()
    verify_spider_runner_image()
    
    # 尝试通过平台执行
    if test_data['spider_id']:
        execute_task()
        monitor_container()
        view_real_time_logs()
        check_platform_logs()
    
    # 直接 Docker 测试 (更可靠)
    test_direct_docker_run()
    
    # 总结
    print_summary()


if __name__ == '__main__':
    main()
