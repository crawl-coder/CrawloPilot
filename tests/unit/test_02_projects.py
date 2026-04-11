"""
Phase 2: 项目管理模块测试
测试项目CRUD、版本管理等功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestProjectModule:
    """项目管理模块测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "Phase2_项目管理"
        self.test_project_id = None
        self.test_version_id = None
    
    def setup(self):
        """测试前准备：登录获取Token"""
        # 首先尝试注册测试用户
        timestamp = int(time.time())
        user_data = {
            'username': f'project_test_{timestamp}',
            'email': f'project_test_{timestamp}@example.com',
            'full_name': 'Project Test User',
            'password': 'Test123456!'
        }
        
        try:
            self.client.post('/api/v1/auth/register', json_data=user_data)
        except:
            pass
        
        # 登录
        result = self.client.post(
            '/api/v1/auth/login',
            data={'username': user_data['username'], 'password': user_data['password']},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if result.get('access_token'):
            self.client.set_token(result['access_token'])
            return True
        return False
    
    def test_01_list_projects(self):
        """测试项目列表"""
        test_name = "项目列表查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/projects/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取项目列表成功，共 {len(result)} 个项目', time.time() - start_time
                )
                return True, result
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取项目列表失败: {result}', time.time() - start_time
                )
                return False, None
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False, None
    
    def test_02_create_project(self):
        """测试创建项目"""
        test_name = "创建项目"
        start_time = time.time()
        
        try:
            timestamp = int(time.time())
            project_data = {
                'name': f'测试项目_{timestamp}',
                'description': '这是一个自动化测试创建的项目',
                'git_url': 'https://github.com/test/test-spider.git',
                'team_id': 1
            }
            
            result = self.client.post('/api/v1/projects/', json_data=project_data)
            
            if result and result.get('id'):
                self.test_project_id = result['id']
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'创建项目成功，ID: {result["id"]}', time.time() - start_time
                )
                return True, result
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'创建项目失败: {result}', time.time() - start_time
                )
                return False, None
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False, None
    
    def test_03_get_project_detail(self):
        """测试获取项目详情"""
        test_name = "获取项目详情"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False, None
        
        try:
            result = self.client.get(f'/api/v1/projects/{self.test_project_id}')
            
            if result and result.get('id') == self.test_project_id:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取项目详情成功: {result.get("name")}', time.time() - start_time
                )
                return True, result
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取项目详情失败: {result}', time.time() - start_time
                )
                return False, None
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False, None
    
    def test_04_update_project(self):
        """测试更新项目"""
        test_name = "更新项目"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            update_data = {
                'description': f'更新后的描述 - {int(time.time())}'
            }
            
            result = self.client.put(
                f'/api/v1/projects/{self.test_project_id}',
                json_data=update_data
            )
            
            if result and result.get('description') == update_data['description']:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '更新项目成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'更新项目失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_05_create_project_version(self):
        """测试创建项目版本"""
        test_name = "创建项目版本"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            version_data = {
                'version': f'v1.0.{int(time.time() % 1000)}',
                'config_snapshot': {
                    'CONCURRENCY': 16,
                    'DELAY': 1.0,
                    'TIMEOUT': 30
                }
            }
            
            result = self.client.post(
                f'/api/v1/projects/{self.test_project_id}/versions',
                json_data=version_data
            )
            
            if result and result.get('id'):
                self.test_version_id = result['id']
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'创建项目版本成功: {result.get("version")}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'创建项目版本失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_06_list_project_versions(self):
        """测试获取项目版本列表"""
        test_name = "项目版本列表"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            result = self.client.get(
                f'/api/v1/projects/{self.test_project_id}/versions'
            )
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取版本列表成功，共 {len(result)} 个版本', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取版本列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_07_delete_project(self):
        """测试删除项目"""
        test_name = "删除项目"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            result = self.client.delete(f'/api/v1/projects/{self.test_project_id}')
            
            # 删除成功返回204 No Content
            if result is None:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '删除项目成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'删除项目失败: {result}', time.time() - start_time
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
        print("[1/7] 项目列表查询测试...")
        self.test_01_list_projects()
        
        print("[2/7] 创建项目测试...")
        self.test_02_create_project()
        
        print("[3/7] 获取项目详情测试...")
        self.test_03_get_project_detail()
        
        print("[4/7] 更新项目测试...")
        self.test_04_update_project()
        
        print("[5/7] 创建项目版本测试...")
        self.test_05_create_project_version()
        
        print("[6/7] 项目版本列表测试...")
        self.test_06_list_project_versions()
        
        print("[7/7] 删除项目测试...")
        self.test_07_delete_project()
        
        # 生成报告
        report_file = 'tests/reports/test_02_projects_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestProjectModule()
    tester.run_all_tests()
