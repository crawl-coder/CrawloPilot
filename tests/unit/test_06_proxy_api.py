"""
Phase 6: 代理池与API管理模块测试
测试代理管理、API配置、限流熔断等功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestProxyAndAPIModule:
    """代理池与API管理模块测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "Phase6_代理池与API管理"
        self.test_proxy_id = None
        self.test_api_config_id = None
        self.test_project_id = None
    
    def setup(self):
        """测试前准备"""
        timestamp = int(time.time())
        
        user_data = {
            'username': f'proxy_test_{timestamp}',
            'email': f'proxy_test_{timestamp}@example.com',
            'full_name': 'Proxy Test User',
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
        
        if not result.get('access_token'):
            return False
        
        self.client.set_token(result['access_token'])
        
        # 创建测试项目
        project_data = {
            'name': f'代理测试项目_{timestamp}',
            'description': '用于测试代理的项目',
            'team_id': 1
        }
        
        result = self.client.post('/api/v1/projects/', json_data=project_data)
        if result and result.get('id'):
            self.test_project_id = result['id']
            return True
        
        return True
    
    # ==================== 代理池测试 ====================
    
    def test_01_list_proxies(self):
        """测试代理列表"""
        test_name = "代理列表查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/proxies/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取代理列表成功，共 {len(result)} 个代理', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取代理列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_02_add_proxy(self):
        """测试添加代理"""
        test_name = "添加代理"
        start_time = time.time()
        
        try:
            proxy_data = {
                'ip': '192.168.1.100',
                'port': 8080,
                'protocol': 'HTTP',
                'region': '北京',
                'group_name': 'test_group'
            }
            
            result = self.client.post('/api/v1/proxies/', json_data=proxy_data)
            
            if result and result.get('id'):
                self.test_proxy_id = result['id']
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'添加代理成功，ID: {result["id"]}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'添加代理失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_03_update_proxy(self):
        """测试更新代理"""
        test_name = "更新代理"
        start_time = time.time()
        
        if not self.test_proxy_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试代理ID', time.time() - start_time
            )
            return False
        
        try:
            update_data = {
                'health_score': 95.5,
                'region': '上海'
            }
            
            result = self.client.put(
                f'/api/v1/proxies/{self.test_proxy_id}',
                json_data=update_data
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '更新代理成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'更新代理失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_04_proxy_health_check(self):
        """测试代理健康检查"""
        test_name = "代理健康检查"
        start_time = time.time()
        
        try:
            result = self.client.post('/api/v1/proxies/check')
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '代理健康检查执行成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'代理健康检查失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== API配置测试 ====================
    
    def test_05_list_api_configs(self):
        """测试API配置列表"""
        test_name = "API配置列表"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/api-configs/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取API配置列表成功，共 {len(result)} 条配置', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取API配置列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_06_create_api_config(self):
        """测试创建API配置"""
        test_name = "创建API配置"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            config_data = {
                'project_id': self.test_project_id,
                'name': '测试API',
                'base_url': 'https://api.example.com',
                'auth_type': 'api_key',
                'api_key': 'test_api_key_12345',
                'rate_limit': 100,
                'circuit_breaker_threshold': 5
            }
            
            result = self.client.post('/api/v1/api-configs/', json_data=config_data)
            
            if result and result.get('id'):
                self.test_api_config_id = result['id']
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'创建API配置成功，ID: {result["id"]}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'创建API配置失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_07_api_call_stats(self):
        """测试API调用统计"""
        test_name = "API调用统计"
        start_time = time.time()
        
        if not self.test_api_config_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试API配置ID', time.time() - start_time
            )
            return False
        
        try:
            result = self.client.get(
                f'/api/v1/api-configs/{self.test_api_config_id}/stats'
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '获取API调用统计成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取API调用统计失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_08_delete_proxy(self):
        """测试删除代理"""
        test_name = "删除代理"
        start_time = time.time()
        
        if not self.test_proxy_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试代理ID', time.time() - start_time
            )
            return False
        
        try:
            result = self.client.delete(f'/api/v1/proxies/{self.test_proxy_id}')
            
            if result is None:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '删除代理成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'删除代理失败: {result}', time.time() - start_time
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
        print("\n[准备] 创建项目并登录...")
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        # 代理池测试
        print("\n--- 代理池测试 ---")
        print("[1/8] 代理列表查询测试...")
        self.test_01_list_proxies()
        
        print("[2/8] 添加代理测试...")
        self.test_02_add_proxy()
        
        print("[3/8] 更新代理测试...")
        self.test_03_update_proxy()
        
        print("[4/8] 代理健康检查测试...")
        self.test_04_proxy_health_check()
        
        # API配置测试
        print("\n--- API配置测试 ---")
        print("[5/8] API配置列表测试...")
        self.test_05_list_api_configs()
        
        print("[6/8] 创建API配置测试...")
        self.test_06_create_api_config()
        
        print("[7/8] API调用统计测试...")
        self.test_07_api_call_stats()
        
        print("[8/8] 删除代理测试...")
        self.test_08_delete_proxy()
        
        # 生成报告
        report_file = 'tests/reports/test_06_proxy_api_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestProxyAndAPIModule()
    tester.run_all_tests()
