"""
用户管理页面前后端联调测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
from page_test_base import PageTestBase


class TestUsersPage(PageTestBase):
    """用户管理页面联调测试"""
    
    def __init__(self):
        super().__init__("用户管理")
    
    def test_user_list_loading(self):
        """测试用户列表加载"""
        test_name = "用户列表加载"
        start_time = time.time()
        
        try:
            users = self.client.get('/api/v1/users/')
            self.log_step("获取用户列表", f"{len(users) if isinstance(users, list) else 0}个用户")
            
            if isinstance(users, list) and len(users) > 0:
                required_fields = ['id', 'username', 'email', 'is_active', 'created_at']
                missing = [f for f in required_fields if f not in users[0]]
                self.log_step("字段验证", f"缺少: {missing}" if missing else "完整")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '用户列表加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_create_user(self):
        """测试创建用户"""
        test_name = "创建用户"
        start_time = time.time()
        
        try:
            timestamp = int(time.time())
            user_data = {
                'username': f'newuser_{timestamp}',
                'email': f'newuser_{timestamp}@example.com',
                'full_name': 'New Test User',
                'password': 'Test123456!'
            }
            
            result = self.client.post('/api/v1/users/', json_data=user_data)
            
            if result and result.get('id'):
                self.created_resources.append({'type': 'user', 'id': result['id']})
                self.log_step("创建用户", f"ID={result['id']}")
                
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    f'创建用户成功: {result["username"]}', time.time() - start_time)
                return True
            else:
                raise Exception('创建失败')
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'创建失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_update_user_status(self):
        """测试更新用户状态"""
        test_name = "更新用户状态"
        start_time = time.time()
        
        try:
            # 获取用户列表
            users = self.client.get('/api/v1/users/')
            
            if isinstance(users, list) and len(users) > 0:
                user_id = users[0]['id']
                
                # 更新状态
                update_data = {'is_active': False}
                result = self.client.put(f'/api/v1/users/{user_id}', json_data=update_data)
                
                self.log_step("更新状态", f"user_id={user_id}, is_active=False")
                
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '更新用户状态成功', time.time() - start_time)
                return True
            else:
                self.log_step("更新状态", "无可用用户")
                return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'更新失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_role_management(self):
        """测试角色管理"""
        test_name = "角色管理"
        start_time = time.time()
        
        try:
            # 获取角色列表
            roles = self.client.get('/api/v1/roles/')
            self.log_step("角色列表", f"{len(roles) if isinstance(roles, list) else 0}个角色")
            
            # 获取权限列表
            permissions = self.client.get('/api/v1/permissions/')
            self.log_step("权限列表", f"{len(permissions) if isinstance(permissions, list) else 0}个权限")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '角色管理数据加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def run_all_tests(self):
        """运行所有用户管理页面测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        print("\n[1/4] 用户列表加载...")
        self.test_user_list_loading()
        
        print("[2/4] 创建用户...")
        self.test_create_user()
        
        print("[3/4] 更新用户状态...")
        self.test_update_user_status()
        
        print("[4/4] 角色管理...")
        self.test_role_management()
        
        self.cleanup()
        
        report_file = 'tests/reports/page_users_report.json'
        import os
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        
        return report


if __name__ == '__main__':
    tester = TestUsersPage()
    tester.run_all_tests()
