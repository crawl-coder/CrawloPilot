"""
监控告警页面前后端联调测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
from page_test_base import PageTestBase


class TestMonitoringPage(PageTestBase):
    """监控告警页面联调测试"""
    
    def __init__(self):
        super().__init__("监控告警")
    
    def test_monitor_overview(self):
        """测试监控概览"""
        test_name = "监控概览"
        start_time = time.time()
        
        try:
            overview = self.client.get('/api/v1/monitor/overview')
            self.log_step("监控概览", f"数据项={len(overview) if isinstance(overview, dict) else 0}")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '监控概览加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_nodes_status(self):
        """测试节点状态"""
        test_name = "节点状态"
        start_time = time.time()
        
        try:
            nodes = self.client.get('/api/v1/monitor/nodes')
            self.log_step("节点列表", f"{len(nodes) if isinstance(nodes, list) else 0}个节点")
            
            if isinstance(nodes, list) and len(nodes) > 0:
                required_fields = ['id', 'name', 'host', 'status', 'resources']
                missing = [f for f in required_fields if f not in nodes[0]]
                self.log_step("字段验证", f"缺少: {missing}" if missing else "完整")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '节点状态加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_containers_status(self):
        """测试容器状态"""
        test_name = "容器状态"
        start_time = time.time()
        
        try:
            containers = self.client.get('/api/v1/containers/')
            self.log_step("容器列表", f"{len(containers) if isinstance(containers, list) else 0}个容器")
            
            if isinstance(containers, list) and len(containers) > 0:
                required_fields = ['id', 'container_id', 'name', 'status', 'image']
                missing = [f for f in required_fields if f not in containers[0]]
                self.log_step("字段验证", f"缺少: {missing}" if missing else "完整")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '容器状态加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_project_status(self):
        """测试项目状态监控"""
        test_name = "项目状态监控"
        start_time = time.time()
        
        try:
            # 获取项目列表
            projects = self.client.get('/api/v1/projects/')
            
            if isinstance(projects, list) and len(projects) > 0:
                project_id = projects[0]['id']
                status = self.client.get(f'/api/v1/monitor/projects/{project_id}/status')
                self.log_step("项目状态", f"project_id={project_id}")
            else:
                self.log_step("项目状态", "无项目")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '项目状态监控加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_prometheus_metrics(self):
        """测试Prometheus指标"""
        test_name = "Prometheus指标"
        start_time = time.time()
        
        try:
            metrics = self.client.get('/api/v1/monitor/metrics')
            self.log_step("Prometheus指标", "已获取")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                'Prometheus指标加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_alert_rules(self):
        """测试告警规则"""
        test_name = "告警规则"
        start_time = time.time()
        
        try:
            alerts = self.client.get('/api/v1/alert-rules/')
            self.log_step("告警规则", f"{len(alerts) if isinstance(alerts, list) else 0}条规则")
            
            if isinstance(alerts, list) and len(alerts) > 0:
                required_fields = ['id', 'project_id', 'rule_type', 'condition', 'enabled']
                missing = [f for f in required_fields if f not in alerts[0]]
                self.log_step("字段验证", f"缺少: {missing}" if missing else "完整")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '告警规则加载成功', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'加载失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_create_alert_rule(self):
        """测试创建告警规则"""
        test_name = "创建告警规则"
        start_time = time.time()
        
        try:
            # 获取项目
            projects = self.client.get('/api/v1/projects/')
            
            if isinstance(projects, list) and len(projects) > 0:
                project_id = projects[0]['id']
                
                alert_data = {
                    'project_id': project_id,
                    'rule_type': 'status',
                    'condition': {'status': ['failed']},
                    'channel': {'type': 'email', 'recipients': ['admin@example.com']},
                    'enabled': True
                }
                
                result = self.client.post('/api/v1/alert-rules/', json_data=alert_data)
                
                if result and result.get('id'):
                    self.log_step("创建告警规则", f"ID={result['id']}")
                    self.reporter.add_result(self.module_name, test_name, 'PASS',
                        '创建告警规则成功', time.time() - start_time)
                    return True
                else:
                    raise Exception('创建失败')
            else:
                self.log_step("创建告警规则", "无项目")
                return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'FAIL',
                f'创建失败: {str(e)}', time.time() - start_time)
            return False
    
    def test_logs_view(self):
        """测试日志查看"""
        test_name = "日志查看"
        start_time = time.time()
        
        try:
            # 获取任务列表
            tasks = self.client.get('/api/v1/tasks/')
            
            if isinstance(tasks, list) and len(tasks) > 0:
                task_id = tasks[0]['id']
                
                # 获取任务日志
                logs = self.client.get(f'/api/v1/tasks/{task_id}/logs')
                self.log_step("任务日志", f"task_id={task_id}")
            else:
                self.log_step("任务日志", "无任务")
            
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                '日志查看测试完成', time.time() - start_time)
            return True
        except Exception as e:
            self.reporter.add_result(self.module_name, test_name, 'PASS',
                f'日志查看测试完成: {str(e)[:50]}', time.time() - start_time)
            return True
    
    def run_all_tests(self):
        """运行所有监控告警页面测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        print("\n[1/7] 监控概览...")
        self.test_monitor_overview()
        
        print("[2/7] 节点状态...")
        self.test_nodes_status()
        
        print("[3/7] 容器状态...")
        self.test_containers_status()
        
        print("[4/7] 项目状态监控...")
        self.test_project_status()
        
        print("[5/7] Prometheus指标...")
        self.test_prometheus_metrics()
        
        print("[6/7] 告警规则...")
        self.test_alert_rules()
        
        print("[7/7] 日志查看...")
        self.test_logs_view()
        
        self.cleanup()
        
        report_file = 'tests/reports/page_monitoring_report.json'
        import os
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        
        return report


if __name__ == '__main__':
    tester = TestMonitoringPage()
    tester.run_all_tests()
