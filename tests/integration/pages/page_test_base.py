"""
页面联调测试基类
提供页面测试的通用功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import json
from typing import Dict, Any, List, Optional
from conftest import APIClient, TEST_CONFIG, TestReporter


class PageTestBase:
    """页面联调测试基类"""
    
    def __init__(self, page_name: str):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.page_name = page_name
        self.module_name = f"页面联调-{page_name}"
        
        # 测试数据存储
        self.test_data: Dict[str, Any] = {}
        self.created_resources: List[Dict] = []
    
    def setup(self) -> bool:
        """测试准备：创建测试用户并登录"""
        timestamp = int(time.time())
        
        # 创建测试用户
        user_data = {
            'username': f'page_test_{timestamp}',
            'email': f'page_test_{timestamp}@example.com',
            'full_name': 'Page Test User',
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
            self.test_data['user'] = user_data
            self.test_data['token'] = result['access_token']
            return True
        
        return False
    
    def cleanup(self):
        """清理测试资源"""
        for resource in self.created_resources:
            try:
                resource_type = resource.get('type')
                resource_id = resource.get('id')
                
                if resource_type == 'project':
                    self.client.delete(f'/api/v1/projects/{resource_id}')
                elif resource_type == 'user':
                    self.client.delete(f'/api/v1/users/{resource_id}')
            except:
                pass
    
    def assert_response_format(self, response: Any, expected_fields: List[str], 
                               test_name: str) -> bool:
        """验证响应格式"""
        if not isinstance(response, dict):
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'响应格式错误: 期望dict, 实际{type(response)}'
            )
            return False
        
        missing_fields = [f for f in expected_fields if f not in response]
        if missing_fields:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'响应缺少字段: {missing_fields}'
            )
            return False
        
        return True
    
    def assert_api_success(self, response: Any, test_name: str) -> bool:
        """验证API调用成功"""
        if isinstance(response, dict) and 'detail' in response:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'API返回错误: {response.get("detail")}'
            )
            return False
        return True
    
    def log_step(self, step_name: str, details: str = ''):
        """记录测试步骤"""
        if details:
            print(f"    ✓ {step_name}: {details}")
        else:
            print(f"    ✓ {step_name}")
    
    def run_all_tests(self):
        """运行所有测试（子类实现）"""
        raise NotImplementedError
