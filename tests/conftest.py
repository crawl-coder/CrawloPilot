"""
测试配置文件
提供测试所需的基础设施和工具函数
"""
import pytest
import requests
import json
import time
import os
from typing import Optional, Dict, Any

# 测试环境配置
# 优先从环境变量读取，默认使用云服务器信息
TEST_CONFIG = {
    'base_url': os.getenv('TEST_BASE_URL', 'http://localhost:8000'),
    'frontend_url': os.getenv('TEST_FRONTEND_URL', 'http://localhost:8080'),
    'nginx_url': os.getenv('TEST_NGINX_URL', 'http://localhost'),
    'mysql_host': os.getenv('MYSQL_HOST', '117.72.16.51'),
    'mysql_port': int(os.getenv('MYSQL_PORT', 3306)),
    'mysql_user': os.getenv('MYSQL_USER', 'crawlo'),
    'mysql_password': os.getenv('MYSQL_PASSWORD', 'bJjGTZN4cDf6bmjc'),
    'mysql_database': os.getenv('MYSQL_DATABASE', 'crawlo_pilot'),
    'redis_host': os.getenv('REDIS_HOST', '117.72.16.51'),
    'redis_port': int(os.getenv('REDIS_PORT', 6379)),
    'admin_username': 'admin',
    'admin_password': 'admin123',
    'test_username': 'test_user',
    'test_password': 'test123456',
    'test_email': 'test@example.com',
}

# 测试结果收集
test_results = {
    'passed': 0,
    'failed': 0,
    'errors': [],
    'start_time': None,
    'end_time': None
}


class APIClient:
    """API 客户端类"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.token: Optional[str] = None
        self.session = requests.Session()
    
    def set_token(self, token: str):
        """设置认证 Token"""
        self.token = token
        self.session.headers.update({'Authorization': f'Bearer {token}'})
    
    def clear_token(self):
        """清除认证 Token"""
        self.token = None
        self.session.headers.pop('Authorization', None)
    
    def get(self, path: str, params: Dict = None) -> Any:
        """GET 请求"""
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=params)
        return self._handle_response(response)
    
    def post(self, path: str, data: Dict = None, json_data: Dict = None, headers: Dict = None) -> Any:
        """POST 请求"""
        url = f"{self.base_url}{path}"
        req_headers = {}
        if headers:
            req_headers.update(headers)
        response = self.session.post(url, data=data, json=json_data, headers=req_headers)
        return self._handle_response(response)
    
    def put(self, path: str, data: Dict = None) -> Any:
        """PUT 请求"""
        url = f"{self.base_url}{path}"
        response = self.session.put(url, json=data)
        return self._handle_response(response)
    
    def delete(self, path: str) -> Any:
        """DELETE 请求"""
        url = f"{self.base_url}{path}"
        response = self.session.delete(url)
        return self._handle_response(response)
    
    def _handle_response(self, response: requests.Response) -> Any:
        """处理响应"""
        try:
            if response.status_code == 204:
                return None
            return response.json()
        except json.JSONDecodeError:
            return {'raw_text': response.text, 'status_code': response.status_code}


class TestReporter:
    """测试报告生成器"""
    
    def __init__(self):
        self.results = []
    
    def add_result(self, module: str, test_name: str, status: str, 
                   message: str = '', duration: float = 0):
        """添加测试结果"""
        self.results.append({
            'module': module,
            'test_name': test_name,
            'status': status,
            'message': message,
            'duration': duration,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    def generate_report(self, filename: str):
        """生成测试报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        failed = sum(1 for r in self.results if r['status'] == 'FAIL')
        error = sum(1 for r in self.results if r['status'] == 'ERROR')
        
        report = {
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'error': error,
                'pass_rate': f"{passed/total*100:.2f}%" if total > 0 else '0%'
            },
            'results': self.results,
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report


@pytest.fixture
def api_client():
    """API 客户端 fixture"""
    return APIClient(TEST_CONFIG['base_url'])


@pytest.fixture
def test_config():
    """测试配置 fixture"""
    return TEST_CONFIG


@pytest.fixture
def reporter():
    """测试报告器 fixture"""
    return TestReporter()
