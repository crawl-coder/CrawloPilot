"""
Phase 5: 数据质量模块测试
测试数据质量检测、统计报表等功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestDataQualityModule:
    """数据质量模块测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "Phase5_数据质量"
        self.test_project_id = None
    
    def setup(self):
        """测试前准备：创建项目并登录"""
        timestamp = int(time.time())
        
        user_data = {
            'username': f'quality_test_{timestamp}',
            'email': f'quality_test_{timestamp}@example.com',
            'full_name': 'Quality Test User',
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
        
        if not result.get('access_token'):
            return False
        
        self.client.set_token(result['access_token'])
        
        # 创建测试项目
        project_data = {
            'name': f'数据质量测试项目_{timestamp}',
            'description': '用于测试数据质量的项目',
            'team_id': 1
        }
        
        result = self.client.post('/api/v1/projects/', json_data=project_data)
        if result and result.get('id'):
            self.test_project_id = result['id']
            return True
        
        return False
    
    def test_01_quality_reports(self):
        """测试质量报告列表"""
        test_name = "质量报告列表"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/data-quality/reports')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取质量报告列表成功，共 {len(result)} 条报告', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取质量报告列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_02_data_stats(self):
        """测试数据统计"""
        test_name = "数据统计"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/data-quality/stats')
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '获取数据统计成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取数据统计失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_03_trigger_quality_check(self):
        """测试触发质量检测"""
        test_name = "触发质量检测"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            check_data = {
                'project_id': self.test_project_id,
                'check_types': ['volume', 'null_rate', 'duplicate_rate']
            }
            
            result = self.client.post(
                '/api/v1/data-quality/check',
                json_data=check_data
            )
            
            if result and result.get('check_id'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'触发质量检测成功，检测ID: {result.get("check_id")}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'触发质量检测失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_04_project_quality_trend(self):
        """测试项目质量趋势"""
        test_name = "项目质量趋势"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            result = self.client.get(
                f'/api/v1/data-quality/projects/{self.test_project_id}/trend',
                params={'days': 7}
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '获取项目质量趋势成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取项目质量趋势失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_05_export_quality_report(self):
        """测试导出质量报告"""
        test_name = "导出质量报告"
        start_time = time.time()
        
        try:
            result = self.client.post(
                '/api/v1/data-quality/export',
                json_data={'format': 'json'}
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '导出质量报告成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'导出质量报告失败: {result}', time.time() - start_time
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
        print("\n[准备] 创建项目并登录...")
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        # 执行测试
        print("[1/5] 质量报告列表测试...")
        self.test_01_quality_reports()
        
        print("[2/5] 数据统计测试...")
        self.test_02_data_stats()
        
        print("[3/5] 触发质量检测测试...")
        self.test_03_trigger_quality_check()
        
        print("[4/5] 项目质量趋势测试...")
        self.test_04_project_quality_trend()
        
        print("[5/5] 导出质量报告测试...")
        self.test_05_export_quality_report()
        
        # 生成报告
        report_file = 'tests/reports/test_05_quality_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestDataQualityModule()
    tester.run_all_tests()
