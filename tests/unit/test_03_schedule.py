"""
Phase 3: 任务调度模块测试
测试调度配置、任务实例管理等功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestScheduleModule:
    """任务调度模块测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "Phase3_任务调度"
        self.test_project_id = None
        self.test_schedule_id = None
    
    def setup(self):
        """测试前准备：创建项目并登录"""
        timestamp = int(time.time())
        
        # 注册并登录
        user_data = {
            'username': f'schedule_test_{timestamp}',
            'email': f'schedule_test_{timestamp}@example.com',
            'full_name': 'Schedule Test User',
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
            'name': f'调度测试项目_{timestamp}',
            'description': '用于测试调度的项目',
            'team_id': 1
        }
        
        result = self.client.post('/api/v1/projects/', json_data=project_data)
        if result and result.get('id'):
            self.test_project_id = result['id']
            return True
        
        return False
    
    def test_01_create_cron_schedule(self):
        """测试创建 Cron 调度"""
        test_name = "创建Cron调度"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            schedule_data = {
                'project_id': self.test_project_id,
                'spider_name': 'test_spider',
                'schedule_type': 'cron',
                'cron_expr': '0 8 * * *',  # 每天8点执行
                'priority': 5,
                'max_concurrency': 1,
                'timeout_seconds': 3600,
                'enabled': True
            }
            
            result = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            
            if result and result.get('id'):
                self.test_schedule_id = result['id']
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'创建Cron调度成功，ID: {result["id"]}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'创建调度失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_02_create_interval_schedule(self):
        """测试创建间隔调度"""
        test_name = "创建间隔调度"
        start_time = time.time()
        
        if not self.test_project_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试项目ID', time.time() - start_time
            )
            return False
        
        try:
            schedule_data = {
                'project_id': self.test_project_id,
                'spider_name': 'test_spider_interval',
                'schedule_type': 'interval',
                'interval_seconds': 1800,  # 每30分钟
                'priority': 3,
                'enabled': True
            }
            
            result = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            
            if result and result.get('id'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'创建间隔调度成功，ID: {result["id"]}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'创建调度失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_03_list_schedules(self):
        """测试调度列表"""
        test_name = "调度列表查询"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/schedules/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取调度列表成功，共 {len(result)} 个调度', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取调度列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_04_update_schedule(self):
        """测试更新调度"""
        test_name = "更新调度"
        start_time = time.time()
        
        if not self.test_schedule_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试调度ID', time.time() - start_time
            )
            return False
        
        try:
            update_data = {
                'priority': 8,
                'timeout_seconds': 7200
            }
            
            result = self.client.put(
                f'/api/v1/schedules/{self.test_schedule_id}',
                json_data=update_data
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '更新调度成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'更新调度失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_05_trigger_schedule(self):
        """测试手动触发调度"""
        test_name = "手动触发调度"
        start_time = time.time()
        
        if not self.test_schedule_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试调度ID', time.time() - start_time
            )
            return False
        
        try:
            result = self.client.post(
                f'/api/v1/schedules/{self.test_schedule_id}/trigger'
            )
            
            if result and result.get('task_id'):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'手动触发成功，任务ID: {result.get("task_id")}', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'手动触发失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_06_list_task_instances(self):
        """测试任务实例列表"""
        test_name = "任务实例列表"
        start_time = time.time()
        
        try:
            result = self.client.get('/api/v1/tasks/')
            
            if isinstance(result, list):
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    f'获取任务实例列表成功，共 {len(result)} 个任务', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'获取任务实例列表失败: {result}', time.time() - start_time
                )
                return False
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'ERROR',
                f'请求异常: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_07_pause_resume_schedule(self):
        """测试暂停和恢复调度"""
        test_name = "暂停恢复调度"
        start_time = time.time()
        
        if not self.test_schedule_id:
            self.reporter.add_result(
                self.module_name, test_name, 'SKIP',
                '没有可用的测试调度ID', time.time() - start_time
            )
            return False
        
        try:
            # 暂停
            result = self.client.post(
                f'/api/v1/schedules/{self.test_schedule_id}/pause'
            )
            
            # 恢复
            result = self.client.post(
                f'/api/v1/schedules/{self.test_schedule_id}/resume'
            )
            
            if result:
                self.reporter.add_result(
                    self.module_name, test_name, 'PASS',
                    '暂停/恢复调度成功', time.time() - start_time
                )
                return True
            else:
                self.reporter.add_result(
                    self.module_name, test_name, 'FAIL',
                    f'暂停/恢复调度失败: {result}', time.time() - start_time
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
        print("[1/7] 创建Cron调度测试...")
        self.test_01_create_cron_schedule()
        
        print("[2/7] 创建间隔调度测试...")
        self.test_02_create_interval_schedule()
        
        print("[3/7] 调度列表查询测试...")
        self.test_03_list_schedules()
        
        print("[4/7] 更新调度测试...")
        self.test_04_update_schedule()
        
        print("[5/7] 手动触发调度测试...")
        self.test_05_trigger_schedule()
        
        print("[6/7] 任务实例列表测试...")
        self.test_06_list_task_instances()
        
        print("[7/7] 暂停恢复调度测试...")
        self.test_07_pause_resume_schedule()
        
        # 生成报告
        report_file = 'tests/reports/test_03_schedule_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestScheduleModule()
    tester.run_all_tests()
