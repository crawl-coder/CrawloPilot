#!/usr/bin/env python
"""
CrawloPilot 主测试运行器
运行所有测试并生成综合报告
"""
import os
import sys
import time
import json
import subprocess
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import TestReporter, TEST_CONFIG


class TestRunner:
    """主测试运行器"""
    
    def __init__(self):
        self.reporter = TestReporter()
        self.start_time = None
        self.results = {}
    
    def run_unit_tests(self):
        """运行单元测试"""
        print("\n" + "="*70)
        print("  单元测试 - 单模块前后端联调测试")
        print("="*70)
        
        unit_tests = [
            ('Phase 1: 用户认证', 'tests/unit/test_01_auth.py'),
            ('Phase 2: 项目管理', 'tests/unit/test_02_projects.py'),
            ('边界条件测试', 'tests/unit/test_edge_cases.py'),
            ('性能测试', 'tests/unit/test_performance.py'),
        ]
        
        for name, test_file in unit_tests:
            print(f"\n>>> 运行 {name} 测试...")
            start = time.time()
            
            # 从 .env 加载环境变量注入子进程
            env = os.environ.copy()
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, val = line.split('=', 1)
                            env[key.strip()] = val.strip()
            
            try:
                result = subprocess.run(
                    [sys.executable, test_file],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env=env
                )
                
                duration = time.time() - start
                
                if result.returncode == 0:
                    print(f"    ✓ {name} 测试完成 ({duration:.2f}s)")
                    self.results[name] = {'status': 'PASS', 'duration': duration}
                else:
                    print(f"    ✗ {name} 测试失败")
                    print(f"    错误: {result.stderr[:200]}")
                    self.results[name] = {'status': 'FAIL', 'duration': duration, 'error': result.stderr}
            
            except subprocess.TimeoutExpired:
                print(f"    ✗ {name} 测试超时")
                self.results[name] = {'status': 'TIMEOUT', 'duration': 120}
            except Exception as e:
                print(f"    ✗ {name} 测试异常: {str(e)}")
                self.results[name] = {'status': 'ERROR', 'error': str(e)}
    
    def run_integration_tests(self):
        """运行集成测试"""
        print("\n" + "="*70)
        print("  集成测试 - 模块间协作测试")
        print("="*70)
        
        print("\n>>> 运行集成测试...")
        start = time.time()
        
        try:
            result = subprocess.run(
                [sys.executable, 'tests/integration/test_integration.py'],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            duration = time.time() - start
            
            if result.returncode == 0:
                print(f"    ✓ 集成测试完成 ({duration:.2f}s)")
                self.results['集成测试'] = {'status': 'PASS', 'duration': duration}
            else:
                print(f"    ✗ 集成测试失败")
                self.results['集成测试'] = {'status': 'FAIL', 'duration': duration}
        
        except Exception as e:
            print(f"    ✗ 集成测试异常: {str(e)}")
            self.results['集成测试'] = {'status': 'ERROR', 'error': str(e)}
    
    def run_scenario_tests(self):
        """运行场景测试"""
        print("\n" + "="*70)
        print("  场景测试 - 真实使用场景模拟")
        print("="*70)
        
        print("\n>>> 运行场景测试...")
        start = time.time()
        
        try:
            result = subprocess.run(
                [sys.executable, 'tests/scenarios/test_scenarios.py'],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            duration = time.time() - start
            
            if result.returncode == 0:
                print(f"    ✓ 场景测试完成 ({duration:.2f}s)")
                self.results['场景测试'] = {'status': 'PASS', 'duration': duration}
            else:
                print(f"    ✗ 场景测试失败")
                self.results['场景测试'] = {'status': 'FAIL', 'duration': duration}
        
        except Exception as e:
            print(f"    ✗ 场景测试异常: {str(e)}")
            self.results['场景测试'] = {'status': 'ERROR', 'error': str(e)}
    
    def check_services(self):
        """检查服务状态"""
        print("\n" + "="*70)
        print("  服务状态检查")
        print("="*70)

        import requests

        services = {
            '后端API': TEST_CONFIG['base_url'],
            '前端服务': TEST_CONFIG['frontend_url'],
        }

        for name, url in services.items():
            try:
                response = requests.get(f"{url}/health", timeout=5)
                if response.status_code == 200:
                    print(f"    ✓ {name}: 运行中 ({url})")
                else:
                    print(f"    ✗ {name}: 异常 (状态码: {response.status_code})")
            except Exception as e:
                print(f"    ✗ {name}: 无法连接 ({url})")

        # 凭据一律从环境变量读取（默认本机开发配置），不入库
        mysql_user = os.getenv('MYSQL_USER', 'crawlopilot')
        mysql_pass = os.getenv('MYSQL_PASSWORD', '')
        mysql_host = os.getenv('MYSQL_HOST', '127.0.0.1')
        mysql_port = int(os.getenv('MYSQL_PORT', 3306))
        mysql_db = os.getenv('MYSQL_DATABASE', 'crawlo_pilot')
        redis_host = os.getenv('REDIS_HOST', '127.0.0.1')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_pass = os.getenv('REDIS_PASSWORD') or None

        # 检查数据库
        try:
            import pymysql
            conn = pymysql.connect(
                host=mysql_host,
                port=mysql_port,
                user=mysql_user,
                password=mysql_pass,
                database=mysql_db
            )
            conn.close()
            print(f"    ✓ MySQL: 连接正常 ({mysql_user}@{mysql_host})")
        except Exception as e:
            print(f"    ✗ MySQL: 连接失败 ({str(e)[:60]})")

        # 检查 Redis
        try:
            import redis as redis_lib
            r = redis_lib.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_pass
            )
            r.ping()
            r.close()
            print(f"    ✓ Redis: 连接正常 ({redis_host}:{redis_port})")
        except Exception as e:
            print(f"    ✗ Redis: 连接失败 ({str(e)[:60]})")
    
    def generate_summary_report(self):
        """生成汇总报告"""
        print("\n" + "="*70)
        print("  测试汇总报告")
        print("="*70)
        
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r['status'] == 'PASS')
        failed = sum(1 for r in self.results.values() if r['status'] == 'FAIL')
        errors = sum(1 for r in self.results.values() if r['status'] == 'ERROR')
        
        total_duration = sum(r.get('duration', 0) for r in self.results.values())
        
        print(f"\n  测试结果统计:")
        print(f"  ├─ 总测试数: {total}")
        print(f"  ├─ 通过: {passed}")
        print(f"  ├─ 失败: {failed}")
        print(f"  ├─ 错误: {errors}")
        print(f"  ├─ 通过率: {passed/total*100:.1f}%" if total > 0 else "  ├─ 通过率: N/A")
        print(f"  └─ 总耗时: {total_duration:.2f}秒")
        
        # 保存报告
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'pass_rate': f"{passed/total*100:.1f}%" if total > 0 else "N/A",
                'total_duration': f"{total_duration:.2f}s"
            },
            'details': self.results
        }
        
        report_file = 'tests/reports/summary_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n  报告已保存至: {report_file}")
        
        return report
    
    def run_all(self):
        """运行所有测试"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  CrawloPilot 完整测试套件")
        print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # 检查服务状态
        self.check_services()
        
        # 运行测试
        self.run_unit_tests()
        self.run_integration_tests()
        self.run_scenario_tests()
        
        # 生成汇总报告
        report = self.generate_summary_report()
        
        total_duration = time.time() - self.start_time
        print(f"\n  总测试耗时: {total_duration:.2f}秒")
        print("="*70)
        
        return report


if __name__ == '__main__':
    runner = TestRunner()
    runner.run_all()
