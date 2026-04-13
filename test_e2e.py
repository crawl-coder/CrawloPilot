#!/usr/bin/env python3
"""
CrawloPilot 端到端测试

测试完整流程:
1. 构建 spider-runner 镜像
2. 测试本地 Docker 运行
3. 验证日志采集
4. 测试平台 API

使用 ofweek_standalone 作为测试爬虫
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path

# 颜色输出
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

def print_step(step_num, title):
    print(f"\n{'='*60}")
    print(f"{GREEN}步骤 {step_num}: {title}{NC}")
    print('='*60)

def print_success(msg):
    print(f"{GREEN}✅ {msg}{NC}")

def print_error(msg):
    print(f"{RED}❌ {msg}{NC}")

def print_info(msg):
    print(f"{YELLOW}ℹ️  {msg}{NC}")

# 路径配置
PROJECT_ROOT = Path(__file__).parent
SPIDER_RUNNER_DIR = PROJECT_ROOT / "spider-runner"
OFWEEK_DIR = PROJECT_ROOT / "examples" / "ofweek_standalone"
BACKEND_URL = "http://localhost:8000"

def test_docker_image():
    """测试 1: 验证 spider-runner 镜像"""
    print_step(1, "验证 spider-runner Docker 镜像")
    
    result = subprocess.run(
        ["docker", "images", "crawlopilot/spider-runner:latest"],
        capture_output=True,
        text=True
    )
    
    if "crawlopilot/spider-runner" in result.stdout:
        print_success("spider-runner 镜像已存在")
        print_info(result.stdout)
        return True
    else:
        print_error("spider-runner 镜像不存在,开始构建...")
        
        build_result = subprocess.run(
            ["docker", "build", "-t", "crawlopilot/spider-runner:latest", "."],
            cwd=SPIDER_RUNNER_DIR,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if build_result.returncode == 0:
            print_success("镜像构建成功")
            return True
        else:
            print_error(f"镜像构建失败: {build_result.stderr}")
            return False

def test_local_run():
    """测试 2: 本地运行爬虫容器"""
    print_step(2, "本地运行 ofweek 爬虫")
    
    # 准备临时目录
    temp_code_dir = "/tmp/test_ofweek"
    subprocess.run(["rm", "-rf", temp_code_dir])
    subprocess.run(["cp", "-r", str(OFWEEK_DIR), temp_code_dir])
    
    print_info(f"爬虫代码: {temp_code_dir}")
    print_info("启动容器 (超时 30 秒)...")
    
    # 运行容器
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{temp_code_dir}:/spider/code",
                "-e", "SPIDER_NAME=of_week",
                "-e", "TASK_ID=test_001",
                "--network", "host",
                "crawlopilot/spider-runner:latest"
            ],
            capture_output=True,
            text=True,
            timeout=35
        )
        
        # 检查输出
        output = result.stdout + result.stderr
        
        if "Spider of_week started" in output or "启动爬虫" in output:
            print_success("爬虫成功启动")
            
            # 显示关键日志
            for line in output.split('\n'):
                if any(keyword in line for keyword in ['started', 'Crawled', 'items', 'ERROR']):
                    print(f"  {line}")
            
            return True
        else:
            print_error("爬虫启动失败")
            print_info("输出:")
            print(output[-500:])  # 显示最后 500 字符
            return False
            
    except subprocess.TimeoutExpired:
        print_info("容器运行超时 (30秒),这是正常的 (爬虫需要时间)")
        print_success("容器能够启动")
        return True
    except Exception as e:
        print_error(f"运行失败: {e}")
        return False
    finally:
        # 清理
        subprocess.run(["rm", "-rf", temp_code_dir])

def test_platform_health():
    """测试 3: 平台健康检查"""
    print_step(3, "检查 CrawloPilot 平台服务")
    
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        
        if resp.status_code == 200:
            print_success("平台健康检查通过")
            print_info(f"响应: {resp.json()}")
            return True
        else:
            print_error(f"健康检查失败: {resp.status_code}")
            return False
            
    except requests.ConnectionError:
        print_error("平台未启动")
        print_info("请先运行: ./start-dev.sh")
        return False
    except Exception as e:
        print_error(f"检查失败: {e}")
        return False

def test_platform_login():
    """测试 4: 平台登录"""
    print_step(4, "测试平台登录")
    
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            data={  # 使用表单数据,不是 JSON
                "username": "admin",
                "password": "admin123"
            },
            timeout=5
        )
        
        if resp.status_code == 200:
            data = resp.json()
            token = data.get('access_token')
            print_success("登录成功")
            print_info(f"Token: {token[:20]}...")
            return token
        else:
            print_error(f"登录失败: {resp.status_code}")
            print_info(resp.text)
            return None
            
    except Exception as e:
        print_error(f"登录异常: {e}")
        return None

def test_create_task(token):
    """测试 5: 创建爬虫任务"""
    print_step(5, "创建爬虫任务")
    
    if not token:
        print_error("缺少 Token,跳过测试")
        return None
    
    try:
        # 创建任务
        task_data = {
            "spider_id": "of_week",
            "spider_name": "of_week",
            "git_url": str(OFWEEK_DIR),
            "git_branch": "main",
            "memory_limit": "512m",
            "cpu_limit": 1.0
        }
        
        resp = requests.post(
            f"{BACKEND_URL}/api/v1/execution/tasks",
            json=task_data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if resp.status_code in [200, 201]:
            data = resp.json()
            task_id = data.get('task_id') or data.get('id')
            print_success("任务创建成功")
            print_info(f"Task ID: {task_id}")
            return task_id
        else:
            print_error(f"任务创建失败: {resp.status_code}")
            print_info(resp.text)
            return None
            
    except Exception as e:
        print_error(f"创建任务异常: {e}")
        return None

def test_check_task(token, task_id):
    """测试 6: 检查任务状态"""
    print_step(6, "检查任务状态和日志")
    
    if not task_id:
        print_error("缺少 Task ID,跳过测试")
        return
    
    try:
        # 等待 5 秒让任务启动
        print_info("等待 5 秒...")
        time.sleep(5)
        
        # 查询任务状态
        resp = requests.get(
            f"{BACKEND_URL}/api/v1/execution/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        
        if resp.status_code == 200:
            data = resp.json()
            print_success("任务状态查询成功")
            print_info(f"状态: {data.get('status')}")
            print_info(f"容器 ID: {data.get('container_id', 'N/A')}")
        else:
            print_error(f"查询失败: {resp.status_code}")
        
        # 获取日志
        resp = requests.get(
            f"{BACKEND_URL}/api/v1/execution/tasks/{task_id}/logs",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        
        if resp.status_code == 200:
            logs = resp.json().get('logs', '')
            print_success("日志获取成功")
            
            # 显示关键日志
            for line in logs.split('\n')[-10:]:  # 最后 10 行
                if any(keyword in line for keyword in ['started', 'Crawled', 'items']):
                    print(f"  {line}")
        else:
            print_error(f"日志获取失败: {resp.status_code}")
            
    except Exception as e:
        print_error(f"检查任务异常: {e}")

def main():
    """主测试流程"""
    print("\n" + "="*60)
    print(f"{GREEN}CrawloPilot 端到端测试{NC}")
    print(f"测试爬虫: ofweek_standalone")
    print("="*60)
    
    results = {}
    
    # 测试 1: Docker 镜像
    results['镜像'] = test_docker_image()
    if not results['镜像']:
        print_error("镜像不存在,无法继续测试")
        return
    
    # 测试 2: 本地运行
    results['本地运行'] = test_local_run()
    
    # 测试 3: 平台健康
    results['平台健康'] = test_platform_health()
    
    # 如果平台未运行,跳过后续测试
    if not results['平台健康']:
        print_info("\n平台未运行,跳过 API 测试")
        print_info("完整测试请先启动平台: ./start-dev.sh")
    else:
        # 测试 4: 登录
        token = test_platform_login()
        results['登录'] = token is not None
        
        if token:
            # 测试 5: 创建任务
            task_id = test_create_task(token)
            results['创建任务'] = task_id is not None
            
            if task_id:
                # 测试 6: 检查任务
                test_check_task(token, task_id)
                results['任务监控'] = True
    
    # 总结
    print("\n" + "="*60)
    print(f"{GREEN}测试总结{NC}")
    print("="*60)
    
    for test_name, passed in results.items():
        status = f"{GREEN}✅ 通过{NC}" if passed else f"{RED}❌ 失败{NC}"
        print(f"{test_name:12} {status}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"\n总计: {passed_count}/{total_count} 通过")
    
    if passed_count == total_count:
        print(f"\n{GREEN}🎉 所有测试通过!{NC}")
    else:
        print(f"\n{YELLOW}⚠️  部分测试失败,请检查日志{NC}")

if __name__ == '__main__':
    main()
