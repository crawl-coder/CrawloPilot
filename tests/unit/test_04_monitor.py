"""
Phase 4: 运行监控模块测试
测试监控概览、节点状态、指标采集等功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestMonitorModule:
    """运行监控模块测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "Phase4_运行监控"
    
    def setup(self):
        """测试前准备：登录获取Token"""
        timestamp = int(time.time())
        
        user_data = {
            'username': f'monitor_test_{timestamp}',
            'email': f'monitor_test_{timestamp}@example.com',
            'full_name': 'Monitor Test User',
            'password': 'Test123456!'
        }
        
        try:
            self.client.post('/api/v1/auth/register', json_data=user_data)
        except:
            pass
        
        result = self.client.post(
            '/api/v1/auth/login',
            data={'username': user_data['username'], 'password': user_data['password']},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if result.get('access_token'):
            self.client.set_token(result['access_token'])
            return True
        return False
    
    def test_01_monitor_overview(self):
        """测试监控概览"""
        test_name = "监控概览"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/monitor/overview')
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取监控概览成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取监控概览失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_02_list_nodes(self):
        """测试节点列表"""
        test_name = "节点列表查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/monitor/nodes')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取节点列表成功，共 {len(result)} 个节点', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取节点列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_03_project_status(self):
        """测试项目状态"""
        test_name = "项目状态查询"
        start_time = time.time()
        
        try:
            # 获取项目列表
            projects = self.client.get('/api/v1/projects/')
            
            if projects and len(projects) > 0:
                project_id = projects[0]['id']
                result = self.client.get(f'/api/v1/monitor/projects/{project_id}/status')
                
                if result:
                    self.reporter.add_result(
                        self.module_name, test_name, 'PASS',
                        f'获取项目状态成功', time.time() - start_time
                    )
                    return True
            
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的项目', time.time() - start_time
            )
            return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_04_prometheus_metrics(self):
        """测试 Prometheus 指标"""
        test_name = "Prometheus指标"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/monitor/metrics')
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '获取Prometheus指标成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取指标失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_05_container_status(self):
        """测试容器状态"""
        test_name = "容器状态查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/containers/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取容器列表成功，共 {len(result)} 个容器', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取容器列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_06_resource_usage(self):
        """测试资源使用情况"""
        test_name = "资源使用情况"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/monitor/resources')
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '获取资源使用情况成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取资源使用情况失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备工作
        print("\n[准备] 登录获取Token...")
        if not self.setup():
            print("登录失败，跳过测试")
            return None
        
        # 执行测试
        print("[1/6] 监控概览测试...")
        self.test_01_monitor_overview()
        
        print("[2/6] 节点列表查询测试...")
        self.test_02_list_nodes()
        
        print("[3/6] 项目状态查询测试...")
        self.test_03_project_status()
        
        print("[4/6] Prometheus指标测试...")
        self.test_04_prometheus_metrics()
        
        print("[5/6] 容器状态查询测试...")
        self.test_05_container_status()
        
        print("[6/6] 资源使用情况测试...")
        self.test_06_resource_usage()
        
        # 生成报告
        report_file = 'tests/reports/test_04_monitor_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestMonitorModule()
    tester.run_all_tests()
