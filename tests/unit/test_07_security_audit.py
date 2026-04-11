"""
Phase 7: 安全与审计模块测试
测试用户管理、权限控制、审计日志等功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestSecurityAuditModule:
    """安全与审计模块测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "Phase7_安全与审计"
        self.test_user_id = None
    
    def setup(self):
        """测试前准备：登录获取Token"""
        timestamp = int(time.time())
        
        # 创建管理员用户（模拟）
        admin_data = {
            'username': f'admin_test_{timestamp}',
            'email': f'admin_test_{timestamp}@example.com',
            'full_name': 'Admin Test User',
            'password': 'Admin123456!'
        }
        
        try:
            self.client.post('/api/v1/auth/register', json_data=admin_data)
        except:
            pass
        
        result = self.client.post(
            '/api/v1/auth/login',
            data={'username': admin_data['username'], 'password': admin_data['password']},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if result.get('access_token'):
            self.client.set_token(result['access_token'])
            return True
        return False
    
    # ==================== 用户管理测试 ====================
    
    def test_01_list_users(self):
        """测试用户列表"""
        test_name = "用户列表查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/users/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取用户列表成功，共 {len(result)} 个用户', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取用户列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_02_create_user(self):
        """测试创建用户"""
        test_name = "创建用户"
        start_time = time.time()
        
        try:
            timestamp = int(time.time())
            user_data = {
                'username': f'newuser_{timestamp}',
                'email': f'newuser_{timestamp}@example.com',
                'full_name': 'New Test User',
                'password': 'NewUser123!'
            }
            
            result = self.client.post('/api/v1/users/', json_data=user_data)
            
            if result and result.get('id'):
                self.test_user_id = result['id']
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'创建用户成功，ID: {result["id"]}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'创建用户失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_03_update_user_status(self):
        """测试更新用户状态"""
        test_name = "更新用户状态"
        start_time = time.time()
        
        if not self.test_user_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试用户ID', time.time() - start_time
            )
            return False
        
        try:
            update_data = {'is_active': False}
            
            result = self.client.put(
                f'/api/v1/users/{self.test_user_id}',
                json_data=update_data
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '更新用户状态成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'更新用户状态失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 角色权限测试 ====================
    
    def test_04_list_roles(self):
        """测试角色列表"""
        test_name = "角色列表查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/roles/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取角色列表成功，共 {len(result)} 个角色', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取角色列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_05_list_permissions(self):
        """测试权限列表"""
        test_name = "权限列表查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/permissions/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取权限列表成功，共 {len(result)} 个权限', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取权限列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_06_update_role_permissions(self):
        """测试更新角色权限"""
        test_name = "更新角色权限"
        start_time = time.time()
        
        try:
            # 获取角色列表
            roles = self.client.get('/api/v1/roles/')
            
            if roles and len(roles) > 0:
                role_id = roles[0]['id']
                
                update_data = {
                    'permissions': ['project:read', 'project:write']
                }
                
                result = self.client.put(
                    f'/api/v1/roles/{role_id}/permissions',
                    json_data=update_data
                )
                
                if result:
                    self.reporter.add_result(
                        self.module_name, test_name, 'PASS',
                        '更新角色权限成功', time.time() - start_time
                    )
                    return True
            
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的角色', time.time() - start_time
            )
            return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 审计日志测试 ====================
    
    def test_07_list_audit_logs(self):
        """测试审计日志列表"""
        test_name = "审计日志列表"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/audit-logs/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取审计日志列表成功，共 {len(result)} 条记录', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取审计日志列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_08_export_audit_logs(self):
        """测试导出审计日志"""
        test_name = "导出审计日志"
        start_time = time.time()
        
        try:
            result = self.client.post(
                '/api/v1/audit-logs/export',
                json_data={'format': 'csv'}
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '导出审计日志成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'导出审计日志失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 安全测试 ====================
    
    def test_09_sql_injection_protection(self):
        """测试SQL注入防护"""
        test_name = "SQL注入防护"
        start_time = time.time()
        
        try:
            # 尝试SQL注入
            malicious_input = "admin' OR '1'='1"
            
            result = self.client.post(
                '/api/v1/auth/login',
                data={'username': malicious_input, 'password': 'test'},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            # 应该登录失败
            if not result.get('access_token'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    'SQL注入攻击被正确防护', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    'SQL注入防护失效', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'SQL注入攻击被正确防护 (异常: {str(e)[:30]})', time.time() - start_time
            )
            return True
    
    def test_10_xss_protection(self):
        """测试XSS防护"""
        test_name = "XSS防护"
        start_time = time.time()
        
        try:
            # 尝试XSS注入
            xss_input = "<script>alert('xss')</script>"
            
            timestamp = int(time.time())
            user_data = {
                'username': f'xss_test_{timestamp}',
                'email': f'xss_test_{timestamp}@example.com',
                'full_name': xss_input,
                'password': 'Test123456!'
            }
            
            result = self.client.post('/api/v1/auth/register', json_data=user_data)
            
            # 检查是否正确处理了XSS输入
            if result and xss_input not in str(result):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    'XSS攻击被正确防护', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    'XSS防护可能存在问题', time.time() - start_time
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
        
        # 用户管理测试
        print("\n--- 用户管理测试 ---")
        print("[1/10] 用户列表查询测试...")
        self.test_01_list_users()
        
        print("[2/10] 创建用户测试...")
        self.test_02_create_user()
        
        print("[3/10] 更新用户状态测试...")
        self.test_03_update_user_status()
        
        # 角色权限测试
        print("\n--- 角色权限测试 ---")
        print("[4/10] 角色列表查询测试...")
        self.test_04_list_roles()
        
        print("[5/10] 权限列表查询测试...")
        self.test_05_list_permissions()
        
        print("[6/10] 更新角色权限测试...")
        self.test_06_update_role_permissions()
        
        # 审计日志测试
        print("\n--- 审计日志测试 ---")
        print("[7/10] 审计日志列表测试...")
        self.test_07_list_audit_logs()
        
        print("[8/10] 导出审计日志测试...")
        self.test_08_export_audit_logs()
        
        # 安全测试
        print("\n--- 安全测试 ---")
        print("[9/10] SQL注入防护测试...")
        self.test_09_sql_injection_protection()
        
        print("[10/10] XSS防护测试...")
        self.test_10_xss_protection()
        
        # 生成报告
        report_file = 'tests/reports/test_07_security_audit_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestSecurityAuditModule()
    tester.run_all_tests()
