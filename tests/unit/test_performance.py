"""
性能测试
测试API响应时间和并发性能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import concurrent.futures
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestPerformance:
    """性能测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "性能测试"
        
        # 性能阈值配置
        self.thresholds = {
            'api_response_time': 500,  # ms
            'auth_response_time': 1000,  # ms (认证接口可稍慢)
            'list_response_time': 200,  # ms
            'concurrent_requests': 50,
            'success_rate': 95  # %
        }
    
    def setup(self):
        """测试准备"""
        timestamp = int(time.time())
        
        user_data = {
            'username': f'perf_test_{timestamp}',
            'email': f'perf_test_{timestamp}@example.com',
            'full_name': 'Performance Test User',
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
    
    def measure_response_time(self, func, *args, **kwargs):
        """测量响应时间"""
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000  # ms
            return result, duration, None
        except Exception as e:
            duration = (time.time() - start) * 1000
            return None, duration, str(e)
    
    # ==================== 响应时间测试 ====================
    
    def test_health_check_response_time(self):
        """测试健康检查响应时间"""
        test_name = "健康检查响应时间"
        start_time = time.time()
        
        result, duration, error = self.measure_response_time(
            self.client.get, '/health'
        )
        
        if error:
            self.reporter.add_result(self.module_name, test_name, 'ERROR',
                f'请求失败: {error}', time.time() - start_time)
            return False
        
        if duration < self.thresholds['list_response_time']:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'响应时间: {duration:.2f}ms (阈值: {self.thresholds["list_response_time"]}ms)',
                time.time() - start_time)
            return True
        else:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'响应时间过长: {duration:.2f}ms (阈值: {self.thresholds["list_response_time"]}ms)',
                time.time() - start_time)
            return False
    
    def test_project_list_response_time(self):
        """测试项目列表响应时间"""
        test_name = "项目列表响应时间"
        start_time = time.time()
        
        result, duration, error = self.measure_response_time(
            self.client.get, '/api/v1/projects/'
        )
        
        if error:
            self.reporter.add_result(self.module_name, test_name, 'ERROR',
                f'请求失败: {error}', time.time() - start_time)
            return False
        
        if duration < self.thresholds['list_response_time']:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'响应时间: {duration:.2f}ms', time.time() - start_time)
            return True
        else:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'响应时间过长: {duration:.2f}ms', time.time() - start_time)
            return False
    
    def test_auth_response_time(self):
        """测试认证响应时间"""
        test_name = "认证响应时间"
        start_time = time.time()
        
        timestamp = int(time.time())
        result, duration, error = self.measure_response_time(
            self.client.post,
            '/api/v1/auth/login',
            data={'username': 'test', 'password': 'wrong'},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if duration < self.thresholds['auth_response_time']:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'响应时间: {duration:.2f}ms', time.time() - start_time)
            return True
        else:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'响应时间过长: {duration:.2f}ms', time.time() - start_time)
            return False
    
    def test_create_project_response_time(self):
        """测试创建项目响应时间"""
        test_name = "创建项目响应时间"
        start_time = time.time()
        
        timestamp = int(time.time())
        project_data = {
            'name': f'性能测试项目_{timestamp}',
            'description': '性能测试',
            'team_id': 1
        }
        
        result, duration, error = self.measure_response_time(
            self.client.post, '/api/v1/projects/', json_data=project_data
        )
        
        if duration < self.thresholds['api_response_time']:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'响应时间: {duration:.2f}ms', time.time() - start_time)
            return True
        else:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'响应时间过长: {duration:.2f}ms', time.time() - start_time)
            return False
    
    # ==================== 并发测试 ====================
    
    def test_concurrent_requests(self):
        """测试并发请求"""
        test_name = "并发请求测试"
        start_time = time.time()
        
        num_requests = self.thresholds['concurrent_requests']
        success_count = 0
        error_count = 0
        response_times = []
        
        def make_request(_):
            try:
                client = APIClient(TEST_CONFIG['base_url'])
                start = time.time()
                client.get('/health')
                duration = (time.time() - start) * 1000
                return True, duration
            except:
                return False, 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            for future in concurrent.futures.as_completed(futures):
                success, duration = future.result()
                if success:
                    success_count += 1
                    response_times.append(duration)
                else:
                    error_count += 1
        
        success_rate = (success_count / num_requests) * 100
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        if success_rate >= self.thresholds['success_rate']:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'成功率: {success_rate:.1f}%, 平均响应: {avg_response_time:.2f}ms',
                time.time() - start_time)
            return True
        else:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'成功率过低: {success_rate:.1f}% (阈值: {self.thresholds["success_rate"]}%)',
                time.time() - start_time)
            return False
    
    def test_concurrent_project_reads(self):
        """测试并发读取项目"""
        test_name = "并发读取项目"
        start_time = time.time()
        
        num_requests = 20
        success_count = 0
        
        def read_projects(_):
            try:
                client = APIClient(TEST_CONFIG['base_url'])
                client.get('/api/v1/projects/')
                return True
            except:
                return False
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(read_projects, i) for i in range(num_requests)]
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    success_count += 1
        
        success_rate = (success_count / num_requests) * 100
        
        if success_rate >= self.thresholds['success_rate']:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'成功率: {success_rate:.1f}%', time.time() - start_time)
            return True
        else:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'成功率: {success_rate:.1f}%', time.time() - start_time)
            return False
    
    # ==================== 压力测试 ====================
    
    def test_sustained_load(self):
        """测试持续负载"""
        test_name = "持续负载测试"
        start_time = time.time()
        
        duration_seconds = 10  # 持续10秒
        requests_per_second = 5
        total_requests = duration_seconds * requests_per_second
        
        success_count = 0
        error_count = 0
        
        print(f"\n    运行持续负载测试 ({duration_seconds}秒)...")
        
        def make_request():
            try:
                client = APIClient(TEST_CONFIG['base_url'])
                client.get('/health')
                return True
            except:
                return False
        
        start = time.time()
        request_count = 0
        
        while time.time() - start < duration_seconds:
            if make_request():
                success_count += 1
            else:
                error_count += 1
            request_count += 1
            time.sleep(1 / requests_per_second)
        
        success_rate = (success_count / request_count) * 100 if request_count > 0 else 0
        
        if success_rate >= 90:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'完成 {request_count} 请求, 成功率: {success_rate:.1f}%',
                time.time() - start_time)
            return True
        else:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'成功率: {success_rate:.1f}%', time.time() - start_time)
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备
        print("\n[准备] 登录获取Token...")
        self.setup()
        
        # 响应时间测试
        print("\n--- 响应时间测试 ---")
        print("[1/4] 健康检查响应时间...")
        self.test_health_check_response_time()
        
        print("[2/4] 项目列表响应时间...")
        self.test_project_list_response_time()
        
        print("[3/4] 认证响应时间...")
        self.test_auth_response_time()
        
        print("[4/4] 创建项目响应时间...")
        self.test_create_project_response_time()
        
        # 并发测试
        print("\n--- 并发测试 ---")
        print("[5/7] 并发请求测试...")
        self.test_concurrent_requests()
        
        print("[6/7] 并发读取项目...")
        self.test_concurrent_project_reads()
        
        # 压力测试
        print("\n--- 压力测试 ---")
        print("[7/7] 持续负载测试...")
        self.test_sustained_load()
        
        # 生成报告
        report_file = 'tests/reports/test_performance_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        
        return report


if __name__ == '__main__':
    tester = TestPerformance()
    tester.run_all_tests()
