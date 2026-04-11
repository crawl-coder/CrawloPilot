"""
Phase 1: 用户认证模块测试
测试用户登录、注册、权限验证等功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestAuthModule:
    """用户认证模块测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "Phase1_用户认证"
    
    def test_01_health_check(self):
        """测试服务健康检查"""
        test_name = "服务健康检查"
        start_time = time.time()
        
        try:
            # 测试后端健康检查端点
            result = self.client.get('/health')
            
            if result and result.get('status') == 'healthy':
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '服务健康检查通过', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'健康检查失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_02_user_registration(self):
        """测试用户注册"""
        test_name = "用户注册"
        start_time = time.time()
        
        try:
            # 生成唯一用户名
            timestamp = int(time.time())
            user_data = {
                'username': f'test_user_{timestamp}',
                'email': f'test_{timestamp}@example.com',
                'full_name': 'Test User',
                'password': 'Test123456!'
            }
            
            result = self.client.post('/api/v1/auth/register', json_data=user_data)
            
            if result and result.get('id'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'用户注册成功: {result.get("username")}', time.time() - start_time
                )
                return True, user_data
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'用户注册失败: {result}', time.time() - start_time
                )
                return False, None
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False, None
    
    def test_03_user_login(self, username: str = None, password: str = None):
        """测试用户登录"""
        test_name = "用户登录"
        start_time = time.time()
        
        try:
            # 使用默认测试账号或传入的账号
            login_data = {
                'username': username or TEST_CONFIG['test_username'],
                'password': password or TEST_CONFIG['test_password']
            }
            
            # OAuth2 表单格式
            form_data = f"username={login_data['username']}&password={login_data['password']}"
            result = self.client.post(
                '/api/v1/auth/login',
                data={'username': login_data['username'], 'password': login_data['password']},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if result and result.get('access_token'):
                self.client.set_token(result['access_token'])
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '用户登录成功，获取到 Token', time.time() - start_time
                )
                return True, result['access_token']
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'用户登录失败: {result}', time.time() - start_time
                )
                return False, None
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False, None
    
    def test_04_get_current_user(self):
        """测试获取当前用户信息"""
        test_name = "获取当前用户信息"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/auth/me')
            
            if result and result.get('id'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取用户信息成功: {result.get("username")}', time.time() - start_time
                )
                return True, result
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取用户信息失败: {result}', time.time() - start_time
                )
                return False, None
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False, None
    
    def test_05_invalid_login(self):
        """测试无效登录"""
        test_name = "无效登录验证"
        start_time = time.time()
        
        try:
            result = self.client.post(
                '/api/v1/auth/login',
                data={'username': 'invalid_user', 'password': 'wrong_password'},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            # 期望返回401错误
            if not result.get('access_token'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '无效登录被正确拒绝', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    '无效登录未被拒绝', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_06_token_validation(self):
        """测试 Token 验证"""
        test_name = "Token验证"
        start_time = time.time()
        
        try:
            # 清除 Token
            self.client.clear_token()
            
            # 无 Token 访问受保护接口
            result = self.client.get('/api/v1/auth/me')
            
            if not result.get('id'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '无Token访问被正确拒绝', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    '无Token访问未被拒绝', time.time() - start_time
                )
                return False
        except Exception as e:
            # 无Token访问应该抛出异常或返回错误
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'无Token访问被正确拒绝 (异常: {str(e)[:50]})', time.time() - start_time
            )
            return True
    
    def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 1. 健康检查
        print("\n[1/6] 服务健康检查...")
        self.test_01_health_check()
        
        # 2. 用户注册
        print("[2/6] 用户注册测试...")
        success, user_data = self.test_02_user_registration()
        
        # 3. 使用新注册的用户登录
        print("[3/6] 用户登录测试...")
        if success and user_data:
            self.test_03_user_login(user_data['username'], user_data['password'])
        else:
            # 尝试使用配置的测试账号
            self.test_03_user_login()
        
        # 4. 获取当前用户
        print("[4/6] 获取当前用户信息测试...")
        self.test_04_get_current_user()
        
        # 5. 无效登录测试
        print("[5/6] 无效登录验证测试...")
        self.test_05_invalid_login()
        
        # 6. Token 验证测试
        print("[6/6] Token验证测试...")
        self.test_06_token_validation()
        
        # 生成报告
        report_file = 'tests/reports/test_01_auth_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestAuthModule()
    tester.run_all_tests()
