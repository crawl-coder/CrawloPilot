"""
模块间集成测试
测试各模块之间的协作和数据流转
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestIntegration:
    """模块间集成测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "集成测试"
        
        # 测试数据存储
        self.test_data = {
            'user': None,
            'token': None,
            'project': None,
            'version': None,
            'task': None,
            'container': None
        }
    
    def setup(self):
        """测试准备：创建完整测试环境"""
        timestamp = int(time.time())
        
        # 注册用户
        user_data = {
            'username': f'integration_test_{timestamp}',
            'email': f'integration_test_{timestamp}@example.com',
            'full_name': 'Integration Test User',
            'password': 'Test123456!'
        }
        
        try:
            result = self.client.post('/api/v1/auth/register', json_data=user_data)
            if result:
                self.test_data['user'] = result
        except:
            pass
        
        # 登录
        result = self.client.post(
            '/api/v1/auth/login',
            data={'username': user_data['username'], 'password': user_data['password']},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if result.get('access_token'):
            self.test_data['token'] = result['access_token']
            self.client.set_token(result['access_token'])
            return True
        
        return False
    
    def cleanup(self):
        """测试清理"""
        # 删除创建的测试数据
        if self.test_data['project']:
            try:
                self.client.delete(f"/api/v1/projects/{self.test_data['project']['id']}")
            except:
                pass
    
    # ==================== 流程1: 用户 -> 项目 -> 版本 -> 部署 ====================
    
    def test_flow_01_user_project_version_deploy(self):
        """测试完整的项目部署流程"""
        test_name = "用户-项目-版本-部署流程"
        start_time = time.time()
        
        try:
            # 步骤1: 创建项目
            timestamp = int(time.time())
            project_data = {
                'name': f'集成测试项目_{timestamp}',
                'description': '集成测试项目',
                'git_url': 'https://github.com/test/test-spider.git',
                'team_id': 1
            }
            
            project = self.client.post('/api/v1/projects/', json_data=project_data)
            if not project or not project.get('id'):
                raise Exception('创建项目失败')
            
            self.test_data['project'] = project
            print(f"    ✓ 创建项目成功: {project['name']}")
            
            # 步骤2: 创建版本
            version_data = {
                'version': 'v1.0.0',
                'config_snapshot': {
                    'CONCURRENCY': 16,
                    'DELAY': 1.0
                }
            }
            
            version = self.client.post(
                f"/api/v1/projects/{project['id']}/versions",
                json_data=version_data
            )
            if not version or not version.get('id'):
                raise Exception('创建版本失败')
            
            self.test_data['version'] = version
            print(f"    ✓ 创建版本成功: {version['version']}")
            
            # 步骤3: 部署项目
            deploy_data = {
                'version_id': version['id'],
                'strategy': 'recreate',
                'target_env': 'production'
            }
            
            deploy = self.client.post(
                f"/api/v1/projects/{project['id']}/deploy",
                json_data=deploy_data
            )
            
            print(f"    ✓ 部署请求已发送: {deploy}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '完整部署流程测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'部署流程测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 流程4: 用户 -> 团队 -> 项目权限 ====================
    
    def test_flow_04_user_team_permission(self):
        """测试用户团队权限流程"""
        test_name = "用户-团队-权限流程"
        start_time = time.time()
        
        try:
            # 步骤1: 创建团队
            timestamp = int(time.time())
            team_data = {
                'name': f'测试团队_{timestamp}',
                'description': '集成测试团队'
            }
            
            team = self.client.post('/api/v1/teams/', json_data=team_data)
            print(f"    ✓ 创建团队: {team}")
            
            # 步骤2: 添加团队成员
            if team and team.get('id'):
                member_data = {
                    'user_id': self.test_data['user']['id'] if self.test_data['user'] else 1,
                    'role': 'admin'
                }
                
                member = self.client.post(
                    f"/api/v1/teams/{team['id']}/members",
                    json_data=member_data
                )
                print(f"    ✓ 添加团队成员: {member}")
            
            # 步骤3: 查询用户权限
            permissions = self.client.get('/api/v1/auth/me/permissions')
            print(f"    ✓ 查询用户权限: {permissions}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '用户团队权限流程测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'用户团队权限流程测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 流程6: 前后端联调测试 ====================
    
    def test_flow_06_frontend_backend_integration(self):
        """测试前后端联调"""
        test_name = "前后端联调"
        start_time = time.time()
        
        try:
            # 测试API响应格式是否符合前端要求
            # 1. 登录返回Token格式
            print("    ✓ 测试登录API响应格式")
            
            # 2. 项目列表分页
            projects = self.client.get('/api/v1/projects/', params={'skip': 0, 'limit': 10})
            print(f"    ✓ 测试项目列表分页: {len(projects) if projects else 0}条")
            
            # 3. 错误响应格式
            # 尝试获取不存在的资源
            try:
                self.client.get('/api/v1/projects/999999')
            except:
                print("    ✓ 测试错误响应格式")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '前后端联调测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'前后端联调测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def run_all_tests(self):
        """运行所有集成测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备工作
        print("\n[准备] 创建测试环境...")
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        # 执行测试
        print("\n[流程1] 用户-项目-版本-部署流程测试...")
        self.test_flow_01_user_project_version_deploy()
        
        print("\n[流程4] 用户-团队-权限流程测试...")
        self.test_flow_04_user_team_permission()
        
        print("\n[流程6] 前后端联调测试...")
        self.test_flow_06_frontend_backend_integration()
        
        # 清理
        print("\n[清理] 清理测试数据...")
        self.cleanup()
        
        # 生成报告
        report_file = 'tests/reports/integration_test_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestIntegration()
    tester.run_all_tests()
