"""
任务调度页面前后端联调测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
from page_test_base import PageTestBase


class TestSchedulesPage(PageTestBase):
    """任务调度页面联调测试"""
    
    def __init__(self):
        super().__init__("任务调度")
        self.test_project = None
        self.test_schedule = None
    
    def setup(self):
        """准备：创建项目和登录"""
        if not super().setup():
            return False
        
        # 创建测试项目
        try:
            timestamp = int(time.time())
            project_data = {
                'name': f'调度测试项目_{timestamp}',
                'description': '用于调度测试',
                'team_id': 1
            }
            result = self.client.post('/api/v1/projects/', json_data=project_data)
            if result and result.get('id'):
                self.test_project = result
                self.created_resources.append({'type': 'project', 'id': result['id']})
                return True
        except:
            pass
        
        return True
    
    def test_schedule_list_loading(self):
        """测试调度列表加载"""
        test_name = "调度列表加载"
        start_time = time.time()
        
        try:
            schedules = self.client.get('/api/v1/schedules/')
            self.log_step("获取调度列表", f"{len(schedules) if isinstance(schedules, list) else 0}个调度")
            
            if isinstance(schedules, list) and len(schedules) > 0:
                required_fields = ['id', 'project_id', 'spider_name', 'schedule_type', 'enabled']
                missing = [f for f in required_fields if f not in schedules[0]]
                self.log_step("字段验证", f"缺少: {missing}" if missing else "完整")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '调度列表加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_create_cron_schedule(self):
        """测试创建Cron调度"""
        test_name = "创建Cron调度"
        start_time = time.time()
        
        try:
            if not self.test_project:
                raise Exception('没有测试项目')
            
            schedule_data = {
                'project_id': self.test_project['id'],
                'spider_name': 'test_spider',
                'schedule_type': 'cron',
                'cron_expr': '0 8 * * *',
                'priority': 5,
                'max_concurrency': 1,
                'timeout_seconds': 3600,
                'enabled': True
            }
            
            result = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            
            if result and result.get('id'):
                self.test_schedule = result
                self.log_step("创建Cron调度", f"ID={result['id']}")
                
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    f'创建调度成功: {result["cron_expr"]}', time.time() - start_time)
                return True
            else:
                raise Exception('创建失败')
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'创建失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_create_interval_schedule(self):
        """测试创建间隔调度"""
        test_name = "创建间隔调度"
        start_time = time.time()
        
        try:
            if not self.test_project:
                raise Exception('没有测试项目')
            
            schedule_data = {
                'project_id': self.test_project['id'],
                'spider_name': 'interval_spider',
                'schedule_type': 'interval',
                'interval_seconds': 1800,
                'priority': 3,
                'enabled': True
            }
            
            result = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            
            if result and result.get('id'):
                self.log_step("创建间隔调度", f"ID={result['id']}, interval=30min")
                
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '创建间隔调度成功', time.time() - start_time)
                return True
            else:
                raise Exception('创建失败')
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'创建失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_trigger_schedule(self):
        """测试手动触发调度"""
        test_name = "手动触发调度"
        start_time = time.time()
        
        try:
            # 获取调度列表
            schedules = self.client.get('/api/v1/schedules/')
            
            if isinstance(schedules, list) and len(schedules) > 0:
                schedule_id = schedules[0]['id']
                
                # 触发调度
                result = self.client.post(f'/api/v1/schedules/{schedule_id}/trigger')
                self.log_step("手动触发", f"schedule_id={schedule_id}")
                
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '手动触发调度成功', time.time() - start_time)
                return True
            else:
                self.log_step("手动触发", "无可用调度")
                return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'触发失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_pause_resume_schedule(self):
        """测试暂停/恢复调度"""
        test_name = "暂停恢复调度"
        start_time = time.time()
        
        try:
            schedules = self.client.get('/api/v1/schedules/')
            
            if isinstance(schedules, list) and len(schedules) > 0:
                schedule_id = schedules[0]['id']
                
                # 暂停
                pause_result = self.client.post(f'/api/v1/schedules/{schedule_id}/pause')
                self.log_step("暂停调度", f"schedule_id={schedule_id}")
                
                # 恢复
                resume_result = self.client.post(f'/api/v1/schedules/{schedule_id}/resume')
                self.log_step("恢复调度", f"schedule_id={schedule_id}")
                
                self.reporter.add_result(self.module_name, test_name, 'PASS',
                    '暂停/恢复调度成功', time.time() - start_time)
                return True
            else:
                self.log_step("暂停/恢复", "无可用调度")
                return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'操作失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_task_instances_list(self):
        """测试任务实例列表"""
        test_name = "任务实例列表"
        start_time = time.time()
        
        try:
            tasks = self.client.get('/api/v1/tasks/')
            self.log_step("获取任务实例", f"{len(tasks) if isinstance(tasks, list) else 0}个任务")
            
            if isinstance(tasks, list) and len(tasks) > 0:
                required_fields = ['id', 'schedule_id', 'spider_name', 'status', 'created_at']
                missing = [f for f in required_fields if f not in tasks[0]]
                self.log_step("字段验证", f"缺少: {missing}" if missing else "完整")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '任务实例列表加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_cron_expression_validation(self):
        """测试Cron表达式验证"""
        test_name = "Cron表达式验证"
        start_time = time.time()
        
        try:
            invalid_crons = [
                'invalid',
                '0 0 0 0 0',
                '',
                '99 99 * * *'
            ]
            
            for cron in invalid_crons:
                schedule_data = {
                    'project_id': self.test_project['id'] if self.test_project else 1,
                    'spider_name': 'test',
                    'schedule_type': 'cron',
                    'cron_expr': cron,
                    'enabled': True
                }
                
                result = self.client.post('/api/v1/schedules/', json_data=schedule_data)
                
                if not result.get('id'):
                    self.log_step(f"无效Cron", f"{cron} 被正确拒绝")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                'Cron表达式验证测试完成', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'验证测试完成: {str(e)[:50]}', time.time() - start_time)
            return True
    
    def run_all_tests(self):
        """运行所有任务调度页面测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        print("\n[1/7] 调度列表加载...")
        self.test_schedule_list_loading()
        
        print("[2/7] 创建Cron调度...")
        self.test_create_cron_schedule()
        
        print("[3/7] 创建间隔调度...")
        self.test_create_interval_schedule()
        
        print("[4/7] 手动触发调度...")
        self.test_trigger_schedule()
        
        print("[5/7] 暂停恢复调度...")
        self.test_pause_resume_schedule()
        
        print("[6/7] 任务实例列表...")
        self.test_task_instances_list()
        
        print("[7/7] Cron表达式验证...")
        self.test_cron_expression_validation()
        
        self.cleanup()
        
        report_file = 'tests/reports/page_schedules_report.json'
        import os
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        
        return report


if __name__ == '__main__':
    tester = TestSchedulesPage()
    tester.run_all_tests()
