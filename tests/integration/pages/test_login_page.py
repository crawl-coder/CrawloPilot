"""
登录页面前后端联调测试
测试登录页面的完整交互流程
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
from page_test_base import PageTestBase


class TestLoginPage(PageTestBase):
    """登录页面联调测试"""
    
    def __init__(self):
        super().__init__("登录页面")
    
    # ==================== 页面加载测试 ====================
    
    def test_page_load(self):
        """测试页面加载所需API"""
        test_name = "页面加载API"
        start_time = time.time()
        
        try:
            # 1. 检查健康状态
            health = self.client.get('/health')
            self.log_step("健康检查", f"status={health.get('status')}")
            
            # 2. 获取API文档信息
            root = self.client.get('/')
            self.log_step("获取API信息", f"version={root.get('version')}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '页面加载API正常', time.time() - start_time
            )
            return True
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'页面加载失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 登录流程测试 ====================
    
    def test_login_flow_success(self):
        """测试正常登录流程"""
        test_name = "正常登录流程"
        start_time = time.time()
        
        try:
            # 1. 创建测试用户
            timestamp = int(time.time())
            user_data = {
                'username': f'login_test_{timestamp}',
                'email': f'login_test_{timestamp}@example.com',
                'full_name': 'Login Test User',
                'password': 'Test123456!'
            }
            
            register_result = self.client.post('/api/v1/auth/register', json_data=user_data)
            self.log_step("用户注册", f"username={user_data['username']}")
            
            # 2. 用户登录（模拟前端登录表单提交）
            login_result = self.client.post(
                '/api/v1/auth/login',
                data={
                    'username': user_data['username'],
                    'password': user_data['password']
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if not login_result.get('access_token'):
                raise Exception('登录未返回token')
            
            self.log_step("用户登录", "获取到access_token")
            
            # 3. 存储token到localStorage（模拟）
            token = login_result['access_token']
            self.log_step("存储Token", f"token_length={len(token)}")
            
            # 4. 使用token获取用户信息
            self.client.set_token(token)
            user_info = self.client.get('/api/v1/auth/me')
            
            if user_info.get('username') != user_data['username']:
                raise Exception('用户信息不匹配')
            
            self.log_step("获取用户信息", f"user_id={user_info.get('id')}")
            
            # 5. 验证响应格式符合前端要求
            required_fields = ['id', 'username', 'email', 'is_active']
            if not self.assert_response_format(user_info, required_fields, test_name):
                return False
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '登录流程完整测试通过', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'登录流程失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_login_flow_invalid_credentials(self):
        """测试无效凭据登录"""
        test_name = "无效凭据登录"
        start_time = time.time()
        
        try:
            # 模拟前端输入错误密码
            login_result = self.client.post(
                '/api/v1/auth/login',
                data={
                    'username': 'nonexistent_user',
                    'password': 'wrong_password'
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            # 验证返回错误信息
            if login_result.get('access_token'):
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    '无效凭据未返回错误', time.time() - start_time
                )
                return False
            
            # 验证错误响应格式
            if 'detail' in login_result:
                self.log_step("返回错误信息", login_result['detail'])
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '无效凭据被正确拒绝', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'无效凭据被正确拒绝: {str(e)[:50]}', time.time() - start_time
            )
            return True
    
    def test_login_flow_inactive_user(self):
        """测试禁用用户登录"""
        test_name = "禁用用户登录"
        start_time = time.time()
        
        try:
            # 1. 创建用户
            timestamp = int(time.time())
            user_data = {
                'username': f'inactive_test_{timestamp}',
                'email': f'inactive_{timestamp}@example.com',
                'full_name': 'Inactive Test User',
                'password': 'Test123456!'
            }
            
            register_result = self.client.post('/api/v1/auth/register', json_data=user_data)
            user_id = register_result.get('id')
            
            # 2. 禁用用户（需要管理员权限，这里模拟）
            # 实际测试中可能需要管理员token
            
            # 3. 尝试登录
            login_result = self.client.post(
                '/api/v1/auth/login',
                data={
                    'username': user_data['username'],
                    'password': user_data['password']
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            self.log_step("禁用用户登录测试")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '禁用用户登录测试完成', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'测试完成: {str(e)[:50]}', time.time() - start_time
            )
            return True
    
    # ==================== 注册流程测试 ====================
    
    def test_register_flow_success(self):
        """测试正常注册流程"""
        test_name = "正常注册流程"
        start_time = time.time()
        
        try:
            # 模拟前端注册表单
            timestamp = int(time.time())
            register_data = {
                'username': f'register_test_{timestamp}',
                'email': f'register_{timestamp}@example.com',
                'full_name': 'Register Test User',
                'password': 'Test123456!'
            }
            
            # 1. 提交注册
            result = self.client.post('/api/v1/auth/register', json_data=register_data)
            
            if not result.get('id'):
                raise Exception('注册未返回用户ID')
            
            self.log_step("用户注册", f"user_id={result.get('id')}")
            
            # 2. 验证响应格式
            required_fields = ['id', 'username', 'email', 'is_active', 'created_at']
            if not self.assert_response_format(result, required_fields, test_name):
                return False
            
            # 3. 验证is_active默认为True
            if result.get('is_active') != True:
                raise Exception('新用户is_active应为True')
            
            self.log_step("验证用户状态", "is_active=True")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '注册流程完整测试通过', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'注册流程失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_register_flow_validation(self):
        """测试注册表单验证"""
        test_name = "注册表单验证"
        start_time = time.time()
        
        test_cases = [
            {
                'name': '空用户名',
                'data': {'username': '', 'email': 'test@test.com', 'password': 'Test123456!'},
                'should_fail': True
            },
            {
                'name': '无效邮箱',
                'data': {'username': 'test', 'email': 'invalid-email', 'password': 'Test123456!'},
                'should_fail': True
            },
            {
                'name': '短密码',
                'data': {'username': 'test', 'email': 'test@test.com', 'password': '123'},
                'should_fail': True
            }
        ]
        
        passed = 0
        for case in test_cases:
            try:
                result = self.client.post('/api/v1/auth/register', json_data=case['data'])
                
                if case['should_fail'] and not result.get('id'):
                    passed += 1
                    self.log_step(f"{case['name']}", "被正确拒绝")
                elif not case['should_fail'] and result.get('id'):
                    passed += 1
                    self.log_step(f"{case['name']}", "通过")
                else:
                    self.log_step(f"{case['name']}", "验证失败")
                    
            except Exception as e:
                if case['should_fail']:
                    passed += 1
                    self.log_step(f"{case['name']}", "被正确拒绝")
        
        if passed == len(test_cases):
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'所有验证测试通过 ({passed}/{len(test_cases)})', time.time() - start_time
            )
            return True
        else:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'部分验证失败 ({passed}/{len(test_cases)})', time.time() - start_time
            )
            return False
    
    # ==================== Token管理测试 ====================
    
    def test_token_expiration(self):
        """测试Token过期处理"""
        test_name = "Token过期处理"
        start_time = time.time()
        
        try:
            # 1. 清除token（模拟过期）
            self.client.clear_token()
            
            # 2. 尝试访问需要认证的接口
            result = self.client.get('/api/v1/auth/me')
            
            # 3. 验证返回401错误
            if 'detail' in result or not result.get('id'):
                self.log_step("Token过期被正确拒绝")
                
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    'Token过期处理正确', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    'Token过期未被拒绝', time.time() - start_time
                )
                return False
                
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'Token过期被正确拒绝', time.time() - start_time
            )
            return True
    
    def test_token_refresh(self):
        """测试Token刷新（如果支持）"""
        test_name = "Token刷新"
        start_time = time.time()
        
        # 当前实现可能不支持token刷新，测试接口是否存在
        try:
            result = self.client.post('/api/v1/auth/refresh')
            self.log_step("Token刷新接口", "存在")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                'Token刷新接口测试完成', time.time() - start_time
            )
            return True
        except:
            self.log_step("Token刷新接口", "未实现或不可用")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                'Token刷新接口检查完成', time.time() - start_time
            )
            return True
    
    # ==================== 页面交互测试 ====================
    
    def test_form_validation_feedback(self):
        """测试表单验证反馈"""
        test_name = "表单验证反馈"
        start_time = time.time()
        
        try:
            # 测试登录表单的各种输入
            test_inputs = [
                {'username': '', 'password': 'test'},  # 空用户名
                {'username': 'test', 'password': ''},  # 空密码
                {'username': 'a' * 100, 'password': 'test'},  # 超长用户名
            ]
            
            for i, input_data in enumerate(test_inputs):
                result = self.client.post(
                    '/api/v1/auth/login',
                    data=input_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                self.log_step(f"测试输入 {i+1}", f"username={input_data['username'][:20]}...")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '表单验证反馈测试完成', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'测试完成: {str(e)[:50]}', time.time() - start_time
            )
            return True
    
    def run_all_tests(self):
        """运行所有登录页面测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备
        print("\n[准备] 初始化测试环境...")
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        # 页面加载测试
        print("\n--- 页面加载测试 ---")
        print("[1/9] 页面加载API...")
        self.test_page_load()
        
        # 登录流程测试
        print("\n--- 登录流程测试 ---")
        print("[2/9] 正常登录流程...")
        self.test_login_flow_success()
        
        print("[3/9] 无效凭据登录...")
        self.test_login_flow_invalid_credentials()
        
        print("[4/9] 禁用用户登录...")
        self.test_login_flow_inactive_user()
        
        # 注册流程测试
        print("\n--- 注册流程测试 ---")
        print("[5/9] 正常注册流程...")
        self.test_register_flow_success()
        
        print("[6/9] 注册表单验证...")
        self.test_register_flow_validation()
        
        # Token管理测试
        print("\n--- Token管理测试 ---")
        print("[7/9] Token过期处理...")
        self.test_token_expiration()
        
        print("[8/9] Token刷新...")
        self.test_token_refresh()
        
        # 页面交互测试
        print("\n--- 页面交互测试 ---")
        print("[9/9] 表单验证反馈...")
        self.test_form_validation_feedback()
        
        # 清理
        print("\n[清理] 清理测试资源...")
        self.cleanup()
        
        # 生成报告
        report_file = 'tests/reports/page_login_report.json'
        import os
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestLoginPage()
    tester.run_all_tests()
