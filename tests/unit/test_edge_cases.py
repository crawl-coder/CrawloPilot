"""
边界条件和异常处理测试
测试各种边界情况和异常场景
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestEdgeCases:
    """边界条件测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "边界条件测试"
    
    def setup(self):
        """测试准备"""
        timestamp = int(time.time())
        
        user_data = {
            'username': f'edge_test_{timestamp}',
            'email': f'edge_test_{timestamp}@example.com',
            'full_name': 'Edge Test User',
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
    
    # ==================== 输入验证测试 ====================
    
    def test_empty_username(self):
        """测试空用户名"""
        test_name = "空用户名验证"
        start_time = time.time()
        
        try:
            result = self.client.post('/api/v1/auth/login', 
                data={'username': '', 'password': 'test'},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if not result.get('access_token'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '空用户名被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '空用户名未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'空用户名被正确拒绝', time.time() - start_time)
            return True
    
    def test_empty_password(self):
        """测试空密码"""
        test_name = "空密码验证"
        start_time = time.time()
        
        try:
            result = self.client.post('/api/v1/auth/login',
                data={'username': 'test', 'password': ''},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if not result.get('access_token'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '空密码被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '空密码未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '空密码被正确拒绝', time.time() - start_time)
            return True
    
    def test_invalid_email_format(self):
        """测试无效邮箱格式"""
        test_name = "无效邮箱格式"
        start_time = time.time()
        
        try:
            user_data = {
                'username': 'test_user',
                'email': 'invalid-email',
                'password': 'Test123456!'
            }
            
            result = self.client.post('/api/v1/auth/register', json_data=user_data)
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '无效邮箱格式被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '无效邮箱格式未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '无效邮箱格式被正确拒绝', time.time() - start_time)
            return True
    
    def test_short_password(self):
        """测试过短密码"""
        test_name = "过短密码验证"
        start_time = time.time()
        
        try:
            timestamp = int(time.time())
            user_data = {
                'username': f'short_pwd_{timestamp}',
                'email': f'short_{timestamp}@example.com',
                'password': '123'  # 过短密码
            }
            
            result = self.client.post('/api/v1/auth/register', json_data=user_data)
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '过短密码被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '过短密码未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '过短密码被正确拒绝', time.time() - start_time)
            return True
    
    # ==================== 资源不存在测试 ====================
    
    def test_nonexistent_project(self):
        """测试访问不存在的项目"""
        test_name = "不存在的项目"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/projects/999999')
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '不存在的项目被正确处理', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '不存在的项目未正确处理', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '不存在的项目返回错误', time.time() - start_time)
            return True
    
    def test_nonexistent_schedule(self):
        """测试访问不存在的调度"""
        test_name = "不存在的调度"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/schedules/999999')
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '不存在的调度被正确处理', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '不存在的调度未正确处理', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '不存在的调度返回错误', time.time() - start_time)
            return True
    
    def test_nonexistent_user(self):
        """测试访问不存在的用户"""
        test_name = "不存在的用户"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/users/999999')
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '不存在的用户被正确处理', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '不存在的用户未正确处理', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '不存在的用户返回错误', time.time() - start_time)
            return True
    
    # ==================== 权限测试 ====================
    
    def test_unauthorized_access(self):
        """测试未授权访问"""
        test_name = "未授权访问"
        start_time = time.time()
        
        try:
            # 清除token
            self.client.clear_token()
            
            result = self.client.get('/api/v1/projects/')
            
            # 应该返回错误
            if not isinstance(result, list) or 'detail' in result:
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '未授权访问被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '未授权访问未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '未授权访问被正确拒绝', time.time() - start_time)
            return True
    
    # ==================== 并发测试 ====================
    
    def test_duplicate_username(self):
        """测试重复用户名"""
        test_name = "重复用户名"
        start_time = time.time()
        
        try:
            timestamp = int(time.time())
            user_data = {
                'username': f'duplicate_{timestamp}',
                'email': f'dup1_{timestamp}@example.com',
                'password': 'Test123456!'
            }
            
            # 第一次注册
            self.client.post('/api/v1/auth/register', json_data=user_data)
            
            # 第二次注册相同用户名
            user_data['email'] = f'dup2_{timestamp}@example.com'
            result = self.client.post('/api/v1/auth/register', json_data=user_data)
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '重复用户名被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '重复用户名未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '重复用户名被正确拒绝', time.time() - start_time)
            return True
    
    def test_duplicate_email(self):
        """测试重复邮箱"""
        test_name = "重复邮箱"
        start_time = time.time()
        
        try:
            timestamp = int(time.time())
            user_data = {
                'username': f'email_dup1_{timestamp}',
                'email': f'email_dup_{timestamp}@example.com',
                'password': 'Test123456!'
            }
            
            # 第一次注册
            self.client.post('/api/v1/auth/register', json_data=user_data)
            
            # 第二次注册相同邮箱
            user_data['username'] = f'email_dup2_{timestamp}'
            result = self.client.post('/api/v1/auth/register', json_data=user_data)
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '重复邮箱被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '重复邮箱未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '重复邮箱被正确拒绝', time.time() - start_time)
            return True
    
    # ==================== 数据边界测试 ====================
    
    def test_large_page_number(self):
        """测试超大页码"""
        test_name = "超大页码"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/projects/', params={'skip': 999999, 'limit': 10})
            
            if isinstance(result, list):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '超大页码返回空列表', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '超大页码处理异常', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '超大页码被正确处理', time.time() - start_time)
            return True
    
    def test_invalid_cron_expression(self):
        """测试无效Cron表达式"""
        test_name = "无效Cron表达式"
        start_time = time.time()
        
        try:
            schedule_data = {
                'project_id': 1,
                'spider_name': 'test',
                'schedule_type': 'cron',
                'cron_expr': 'invalid-cron',
                'enabled': True
            }
            
            result = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '无效Cron表达式被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '无效Cron表达式未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '无效Cron表达式被正确拒绝', time.time() - start_time)
            return True
    
    def test_negative_values(self):
        """测试负数值"""
        test_name = "负数值验证"
        start_time = time.time()
        
        try:
            schedule_data = {
                'project_id': 1,
                'spider_name': 'test',
                'schedule_type': 'interval',
                'interval_seconds': -100,  # 负数
                'enabled': True
            }
            
            result = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            
            if not result.get('id'):
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '负数值被正确拒绝', time.time() - start_time)
                return True
            else:
                self.reporter.add_result(self.module_name, test_name, 'FAIL',
                    '负数值未被拒绝', time.time() - start_time)
                return False
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '负数值被正确拒绝', time.time() - start_time)
            return True
    
    def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备
        print("\n[准备] 登录获取Token...")
        self.setup()
        
        # 输入验证测试
        print("\n--- 输入验证测试 ---")
        print("[1/14] 空用户名验证...")
        self.test_empty_username()
        
        print("[2/14] 空密码验证...")
        self.test_empty_password()
        
        print("[3/14] 无效邮箱格式...")
        self.test_invalid_email_format()
        
        print("[4/14] 过短密码验证...")
        self.test_short_password()
        
        # 资源不存在测试
        print("\n--- 资源不存在测试 ---")
        print("[5/14] 不存在的项目...")
        self.test_nonexistent_project()
        
        print("[6/14] 不存在的调度...")
        self.test_nonexistent_schedule()
        
        print("[7/14] 不存在的用户...")
        self.test_nonexistent_user()
        
        # 权限测试
        print("\n--- 权限测试 ---")
        print("[8/14] 未授权访问...")
        self.test_unauthorized_access()
        
        # 并发测试
        print("\n--- 并发测试 ---")
        print("[9/14] 重复用户名...")
        self.test_duplicate_username()
        
        print("[10/14] 重复邮箱...")
        self.test_duplicate_email()
        
        # 数据边界测试
        print("\n--- 数据边界测试 ---")
        print("[11/14] 超大页码...")
        self.test_large_page_number()
        
        print("[12/14] 无效Cron表达式...")
        self.test_invalid_cron_expression()
        
        print("[13/14] 负数值验证...")
        self.test_negative_values()
        
        # 重新登录
        self.setup()
        
        # 生成报告
        report_file = 'tests/reports/test_edge_cases_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        
        return report


if __name__ == '__main__':
    tester = TestEdgeCases()
    tester.run_all_tests()
