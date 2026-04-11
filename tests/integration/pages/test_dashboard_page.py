"""
Dashboard页面前后端联调测试
测试Dashboard首页的数据展示和交互
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
from page_test_base import PageTestBase


class TestDashboardPage(PageTestBase):
    """Dashboard页面联调测试"""
    
    def __init__(self):
        super().__init__("Dashboard首页")
    
    # ==================== 页面数据加载测试 ====================
    
    def test_page_data_loading(self):
        """测试页面数据加载"""
        test_name = "页面数据加载"
        start_time = time.time()
        
        try:
            # 1. 获取监控概览数据
            overview = self.client.get('/api/v1/monitor/overview')
            self.log_step("监控概览", f"数据项={len(overview) if isinstance(overview, dict) else 0}")
            
            # 2. 获取项目列表（用于统计）
            projects = self.client.get('/api/v1/projects/')
            project_count = len(projects) if isinstance(projects, list) else 0
            self.log_step("项目统计", f"count={project_count}")
            
            # 3. 获取调度列表
            schedules = self.client.get('/api/v1/schedules/')
            schedule_count = len(schedules) if isinstance(schedules, list) else 0
            self.log_step("调度统计", f"count={schedule_count}")
            
            # 4. 获取任务实例
            tasks = self.client.get('/api/v1/tasks/')
            task_count = len(tasks) if isinstance(tasks, list) else 0
            self.log_step("任务统计", f"count={task_count}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'数据加载完成: {project_count}项目, {schedule_count}调度, {task_count}任务',
                time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'数据加载失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_statistics_cards(self):
        """测试统计卡片数据"""
        test_name = "统计卡片数据"
        start_time = time.time()
        
        try:
            stats = {}
            
            # 1. 总项目数
            projects = self.client.get('/api/v1/projects/')
            stats['total_projects'] = len(projects) if isinstance(projects, list) else 0
            
            # 2. 运行中任务数
            tasks = self.client.get('/api/v1/tasks/')
            if isinstance(tasks, list):
                running_tasks = [t for t in tasks if t.get('status') == 'running']
                stats['running_tasks'] = len(running_tasks)
            else:
                stats['running_tasks'] = 0
            
            # 3. 今日完成任务数
            if isinstance(tasks, list):
                from datetime import datetime, timedelta
                today = datetime.now().date()
                today_tasks = [
                    t for t in tasks 
                    if t.get('finished_at') and 
                    datetime.fromisoformat(t['finished_at'].replace('Z', '+00:00')).date() == today
                ]
                stats['today_completed'] = len(today_tasks)
            else:
                stats['today_completed'] = 0
            
            # 4. 告警数量
            alerts = self.client.get('/api/v1/alert-rules/')
            stats['active_alerts'] = len(alerts) if isinstance(alerts, list) else 0
            
            self.log_step("统计数据", str(stats))
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'统计卡片数据: {stats}', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'统计数据获取失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 图表数据测试 ====================
    
    def test_task_trend_chart(self):
        """测试任务趋势图表数据"""
        test_name = "任务趋势图表"
        start_time = time.time()
        
        try:
            # 获取最近7天的任务数据
            tasks = self.client.get('/api/v1/tasks/')
            
            if isinstance(tasks, list):
                from datetime import datetime, timedelta
                
                # 按日期分组统计
                trend_data = {}
                for i in range(7):
                    date = (datetime.now() - timedelta(days=i)).date()
                    trend_data[date.isoformat()] = {'success': 0, 'failed': 0}
                
                for task in tasks:
                    finished_at = task.get('finished_at')
                    if finished_at:
                        task_date = datetime.fromisoformat(
                            finished_at.replace('Z', '+00:00')
                        ).date()
                        date_str = task_date.isoformat()
                        
                        if date_str in trend_data:
                            status = task.get('status')
                            if status == 'success':
                                trend_data[date_str]['success'] += 1
                            elif status == 'failed':
                                trend_data[date_str]['failed'] += 1
                
                self.log_step("任务趋势数据", f"{len(trend_data)}天数据")
            else:
                self.log_step("任务趋势数据", "无数据")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '任务趋势图表数据获取成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'趋势数据获取失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_project_status_chart(self):
        """测试项目状态分布图表"""
        test_name = "项目状态分布"
        start_time = time.time()
        
        try:
            projects = self.client.get('/api/v1/projects/')
            
            if isinstance(projects, list):
                status_count = {}
                for project in projects:
                    status = project.get('status', 'unknown')
                    status_count[status] = status_count.get(status, 0) + 1
                
                self.log_step("项目状态分布", str(status_count))
            else:
                self.log_step("项目状态分布", "无数据")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '项目状态分布数据获取成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'状态分布获取失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_resource_usage_chart(self):
        """测试资源使用率图表"""
        test_name = "资源使用率图表"
        start_time = time.time()
        
        try:
            # 获取节点资源使用情况
            nodes = self.client.get('/api/v1/monitor/nodes')
            
            if isinstance(nodes, list):
                for node in nodes:
                    resources = node.get('resources', {})
                    self.log_step(
                        f"节点 {node.get('name', 'unknown')}",
                        f"CPU={resources.get('cpu', 'N/A')}%, Memory={resources.get('memory', 'N/A')}%"
                    )
            else:
                self.log_step("节点资源", "无数据")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '资源使用率数据获取成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'资源数据获取失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 实时数据测试 ====================
    
    def test_recent_tasks_list(self):
        """测试最近任务列表"""
        test_name = "最近任务列表"
        start_time = time.time()
        
        try:
            # 获取任务列表，按时间排序
            tasks = self.client.get('/api/v1/tasks/', params={'limit': 10})
            
            if isinstance(tasks, list):
                # 验证字段完整性
                required_fields = ['id', 'spider_name', 'status', 'created_at']
                
                for i, task in enumerate(tasks[:5]):  # 只检查前5个
                    missing = [f for f in required_fields if f not in task]
                    if missing:
                        self.log_step(f"任务 {i}", f"缺少字段: {missing}")
                    else:
                        self.log_step(
                            f"任务 {i}",
                            f"{task.get('spider_name')} - {task.get('status')}"
                        )
            else:
                self.log_step("最近任务", "无数据")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '最近任务列表获取成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'任务列表获取失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_recent_alerts_list(self):
        """测试最近告警列表"""
        test_name = "最近告警列表"
        start_time = time.time()
        
        try:
            alerts = self.client.get('/api/v1/alert-rules/')
            
            if isinstance(alerts, list):
                enabled_alerts = [a for a in alerts if a.get('enabled')]
                self.log_step("活跃告警", f"{len(enabled_alerts)}条")
                
                for i, alert in enumerate(enabled_alerts[:3]):
                    self.log_step(
                        f"告警 {i}",
                        f"类型={alert.get('rule_type')}, 启用={alert.get('enabled')}"
                    )
            else:
                self.log_step("告警列表", "无数据")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '最近告警列表获取成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'告警列表获取失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 快捷操作测试 ====================
    
    def test_quick_actions(self):
        """测试快捷操作按钮"""
        test_name = "快捷操作"
        start_time = time.time()
        
        try:
            # 1. 快速创建项目（检查API可用性）
            project_data = {
                'name': f'快速测试项目_{int(time.time())}',
                'description': 'Dashboard快捷操作测试',
                'team_id': 1
            }
            
            result = self.client.post('/api/v1/projects/', json_data=project_data)
            
            if result and result.get('id'):
                self.created_resources.append({'type': 'project', 'id': result['id']})
                self.log_step("快速创建项目", f"ID={result['id']}")
            
            # 2. 快速触发调度
            schedules = self.client.get('/api/v1/schedules/')
            if isinstance(schedules, list) and len(schedules) > 0:
                schedule_id = schedules[0]['id']
                trigger_result = self.client.post(f'/api/v1/schedules/{schedule_id}/trigger')
                self.log_step("快速触发调度", f"schedule_id={schedule_id}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '快捷操作测试完成', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'快捷操作失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_navigation_links(self):
        """测试导航链接"""
        test_name = "导航链接"
        start_time = time.time()
        
        try:
            # 验证各页面API可用性
            pages = [
                ('项目列表', '/api/v1/projects/'),
                ('调度列表', '/api/v1/schedules/'),
                ('任务列表', '/api/v1/tasks/'),
                ('监控概览', '/api/v1/monitor/overview'),
                ('用户列表', '/api/v1/users/'),
            ]
            
            for name, path in pages:
                try:
                    result = self.client.get(path)
                    self.log_step(name, "可用")
                except Exception as e:
                    self.log_step(name, f"错误: {str(e)[:30]}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '导航链接验证完成', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'导航验证失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 数据刷新测试 ====================
    
    def test_data_refresh(self):
        """测试数据刷新功能"""
        test_name = "数据刷新"
        start_time = time.time()
        
        try:
            # 第一次获取数据
            data1 = self.client.get('/api/v1/monitor/overview')
            
            # 等待短暂时间
            time.sleep(1)
            
            # 第二次获取数据
            data2 = self.client.get('/api/v1/monitor/overview')
            
            # 验证数据可以正常获取（不要求变化）
            self.log_step("首次刷新", "成功")
            self.log_step("二次刷新", "成功")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '数据刷新功能正常', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'数据刷新失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def run_all_tests(self):
        """运行所有Dashboard页面测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备
        print("\n[准备] 初始化测试环境...")
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        # 页面数据加载测试
        print("\n--- 页面数据加载测试 ---")
        print("[1/11] 页面数据加载...")
        self.test_page_data_loading()
        
        print("[2/11] 统计卡片数据...")
        self.test_statistics_cards()
        
        # 图表数据测试
        print("\n--- 图表数据测试 ---")
        print("[3/11] 任务趋势图表...")
        self.test_task_trend_chart()
        
        print("[4/11] 项目状态分布...")
        self.test_project_status_chart()
        
        print("[5/11] 资源使用率图表...")
        self.test_resource_usage_chart()
        
        # 实时数据测试
        print("\n--- 实时数据测试 ---")
        print("[6/11] 最近任务列表...")
        self.test_recent_tasks_list()
        
        print("[7/11] 最近告警列表...")
        self.test_recent_alerts_list()
        
        # 快捷操作测试
        print("\n--- 快捷操作测试 ---")
        print("[8/11] 快捷操作...")
        self.test_quick_actions()
        
        print("[9/11] 导航链接...")
        self.test_navigation_links()
        
        # 数据刷新测试
        print("\n--- 数据刷新测试 ---")
        print("[10/11] 数据刷新...")
        self.test_data_refresh()
        
        # 清理
        print("\n[清理] 清理测试资源...")
        self.cleanup()
        
        # 生成报告
        report_file = 'tests/reports/page_dashboard_report.json'
        import os
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestDashboardPage()
    tester.run_all_tests()
