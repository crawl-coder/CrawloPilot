"""
真实场景测试
模拟实际使用场景进行测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from conftest import APIClient, TEST_CONFIG, TestReporter


class TestScenarios:
    """真实场景测试类"""
    
    def __init__(self):
        self.client = APIClient(TEST_CONFIG['base_url'])
        self.reporter = TestReporter()
        self.module_name = "场景测试"
        
        self.test_resources = {
            'users': [],
            'projects': [],
            'schedules': [],
            'containers': []
        }
    
    def setup(self):
        """测试准备"""
        timestamp = int(time.time())
        
        # 创建测试用户并登录
        user_data = {
            'username': f'scenario_test_{timestamp}',
            'email': f'scenario_test_{timestamp}@example.com',
            'full_name': 'Scenario Test User',
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
    
    def cleanup(self):
        """清理测试资源"""
        for project in self.test_resources['projects']:
            try:
                self.client.delete(f"/api/v1/projects/{project['id']}")
            except:
                pass
    
    # ==================== 场景1: 新用户注册并创建第一个项目 ====================
    
    def test_scenario_01_new_user_onboarding(self):
        """场景1: 新用户注册并创建第一个项目"""
        test_name = "新用户注册流程"
        start_time = time.time()
        
        print("\n  模拟场景: 新用户注册并创建第一个爬虫项目")
        
        try:
            # 1. 用户注册
            timestamp = int(time.time())
            user_data = {
                'username': f'newbie_{timestamp}',
                'email': f'newbie_{timestamp}@example.com',
                'full_name': '新用户',
                'password': 'NewUser123!'
            }
            
            user = self.client.post('/api/v1/auth/register', json_data=user_data)
            if not user or not user.get('id'):
                raise Exception('用户注册失败')
            print(f"    ✓ 用户注册成功: {user['username']}")
            
            # 2. 用户登录
            login_result = self.client.post(
                '/api/v1/auth/login',
                data={'username': user_data['username'], 'password': user_data['password']},
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            if not login_result.get('access_token'):
                raise Exception('用户登录失败')
            print("    ✓ 用户登录成功")
            
            # 3. 查看项目列表（应该为空或很少）
            projects = self.client.get('/api/v1/projects/')
            print(f"    ✓ 查看项目列表: {len(projects) if projects else 0}个项目")
            
            # 4. 创建第一个项目
            project_data = {
                'name': f'我的第一个爬虫项目_{timestamp}',
                'description': '这是我的第一个爬虫项目',
                'git_url': 'https://github.com/my/spider-project.git',
                'team_id': 1
            }
            
            project = self.client.post('/api/v1/projects/', json_data=project_data)
            if not project or not project.get('id'):
                raise Exception('创建项目失败')
            print(f"    ✓ 创建项目成功: {project['name']}")
            
            self.test_resources['projects'].append(project)
            
            # 5. 上传第一个版本
            version_data = {
                'version': 'v1.0.0',
                'config_snapshot': {'CONCURRENCY': 8, 'DELAY': 0.5}
            }
            
            version = self.client.post(
                f"/api/v1/projects/{project['id']}/versions",
                json_data=version_data
            )
            print(f"    ✓ 上传版本成功: {version.get('version', 'v1.0.0')}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '新用户注册流程测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'新用户注册流程测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 场景2: 定时爬虫任务调度 ====================
    
    def test_scenario_02_scheduled_spider_task(self):
        """场景2: 定时爬虫任务调度"""
        test_name = "定时爬虫任务调度"
        start_time = time.time()
        
        print("\n  模拟场景: 创建定时爬虫任务并监控执行")
        
        try:
            # 1. 创建项目
            timestamp = int(time.time())
            project_data = {
                'name': f'电商价格监控_{timestamp}',
                'description': '定时采集电商商品价格',
                'team_id': 1
            }
            
            project = self.client.post('/api/v1/projects/', json_data=project_data)
            if not project or not project.get('id'):
                raise Exception('创建项目失败')
            print(f"    ✓ 创建项目: {project['name']}")
            
            self.test_resources['projects'].append(project)
            
            # 2. 创建每日定时调度（每天早上8点）
            schedule_data = {
                'project_id': project['id'],
                'spider_name': 'price_monitor',
                'schedule_type': 'cron',
                'cron_expr': '0 8 * * *',
                'priority': 5,
                'max_concurrency': 1,
                'timeout_seconds': 7200,
                'enabled': True
            }
            
            schedule = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            print(f"    ✓ 创建定时调度: 每日8点执行")
            
            # 3. 创建间隔调度（每2小时）
            interval_schedule = {
                'project_id': project['id'],
                'spider_name': 'price_monitor_realtime',
                'schedule_type': 'interval',
                'interval_seconds': 7200,
                'priority': 3,
                'enabled': True
            }
            
            interval = self.client.post('/api/v1/schedules/', json_data=interval_schedule)
            print(f"    ✓ 创建间隔调度: 每2小时执行")
            
            # 4. 手动触发一次测试
            if schedule and schedule.get('id'):
                task = self.client.post(f"/api/v1/schedules/{schedule['id']}/trigger")
                print(f"    ✓ 手动触发测试任务")
            
            # 5. 查看任务执行状态
            tasks = self.client.get('/api/v1/tasks/')
            print(f"    ✓ 查看任务执行状态: {len(tasks) if tasks else 0}个任务")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '定时爬虫任务调度测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'定时爬虫任务调度测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 场景3: 故障恢复测试 ====================
    
    def test_scenario_03_failure_recovery(self):
        """场景3: 故障恢复测试"""
        test_name = "故障恢复测试"
        start_time = time.time()
        
        print("\n  模拟场景: 任务失败后的重试和恢复")
        
        try:
            # 1. 创建项目和调度
            timestamp = int(time.time())
            project_data = {
                'name': f'故障测试项目_{timestamp}',
                'description': '用于测试故障恢复',
                'team_id': 1
            }
            
            project = self.client.post('/api/v1/projects/', json_data=project_data)
            if not project or not project.get('id'):
                raise Exception('创建项目失败')
            print(f"    ✓ 创建项目: {project['name']}")
            
            self.test_resources['projects'].append(project)
            
            # 2. 创建带重试策略的调度
            schedule_data = {
                'project_id': project['id'],
                'spider_name': 'test_spider',
                'schedule_type': 'once',
                'priority': 5,
                'timeout_seconds': 600,
                'retry_strategy': {
                    'max_retries': 3,
                    'retry_delay': 60,
                    'backoff_factor': 2
                },
                'enabled': True
            }
            
            schedule = self.client.post('/api/v1/schedules/', json_data=schedule_data)
            print(f"    ✓ 创建带重试策略的调度")
            
            # 3. 创建告警规则（任务失败时告警）
            if project:
                alert_data = {
                    'project_id': project['id'],
                    'rule_type': 'status',
                    'condition': {'status': ['failed', 'timeout']},
                    'channel': {'type': 'email', 'recipients': ['admin@example.com']},
                    'enabled': True
                }
                
                alert = self.client.post('/api/v1/alert-rules/', json_data=alert_data)
                print(f"    ✓ 创建失败告警规则")
            
            # 4. 触发任务
            if schedule and schedule.get('id'):
                task = self.client.post(f"/api/v1/schedules/{schedule['id']}/trigger")
                print(f"    ✓ 触发任务")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '故障恢复测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'故障恢复测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 场景4: 多项目管理 ====================
    
    def test_scenario_04_multiple_projects_management(self):
        """场景4: 多项目管理"""
        test_name = "多项目管理"
        start_time = time.time()
        
        print("\n  模拟场景: 管理多个爬虫项目")
        
        try:
            timestamp = int(time.time())
            projects_created = []
            
            # 1. 创建多个项目
            project_names = [
                f'新闻爬虫_{timestamp}',
                f'电商爬虫_{timestamp}',
                f'社交爬虫_{timestamp}'
            ]
            
            for name in project_names:
                project_data = {
                    'name': name,
                    'description': f'{name}描述',
                    'team_id': 1
                }
                
                project = self.client.post('/api/v1/projects/', json_data=project_data)
                if project and project.get('id'):
                    projects_created.append(project)
                    print(f"    ✓ 创建项目: {name}")
            
            self.test_resources['projects'].extend(projects_created)
            
            # 2. 查看项目列表
            all_projects = self.client.get('/api/v1/projects/')
            print(f"    ✓ 查看所有项目: {len(all_projects) if all_projects else 0}个")
            
            # 3. 查看监控概览
            overview = self.client.get('/api/v1/monitor/overview')
            print(f"    ✓ 查看监控概览")
            
            # 4. 批量查看项目状态
            for project in projects_created:
                status = self.client.get(f"/api/v1/monitor/projects/{project['id']}/status")
                print(f"    ✓ 查看项目 [{project['name']}] 状态")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'多项目管理测试成功，创建了{len(projects_created)}个项目', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'多项目管理测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 场景5: 团队协作场景 ====================
    
    def test_scenario_05_team_collaboration(self):
        """场景5: 团队协作场景"""
        test_name = "团队协作"
        start_time = time.time()
        
        print("\n  模拟场景: 团队成员协作管理项目")
        
        try:
            # 1. 创建团队
            timestamp = int(time.time())
            team_data = {
                'name': f'数据采集团队_{timestamp}',
                'description': '负责数据采集的团队'
            }
            
            team = self.client.post('/api/v1/teams/', json_data=team_data)
            print(f"    ✓ 创建团队: {team_data['name']}")
            
            # 2. 创建团队成员（不同角色）
            roles = ['admin', 'developer', 'viewer']
            for role in roles:
                user_data = {
                    'username': f'{role}_user_{timestamp}',
                    'email': f'{role}_{timestamp}@example.com',
                    'full_name': f'{role}用户',
                    'password': 'Test123456!'
                }
                
                user = self.client.post('/api/v1/auth/register', json_data=user_data)
                if user and team and team.get('id'):
                    member_data = {
                        'user_id': user['id'],
                        'role': role
                    }
                    self.client.post(f"/api/v1/teams/{team['id']}/members", json_data=member_data)
                    print(f"    ✓ 添加成员: {role}")
            
            # 3. 创建团队项目
            if team and team.get('id'):
                project_data = {
                    'name': f'团队项目_{timestamp}',
                    'description': '团队共享项目',
                    'team_id': team['id']
                }
                
                project = self.client.post('/api/v1/projects/', json_data=project_data)
                if project:
                    self.test_resources['projects'].append(project)
                    print(f"    ✓ 创建团队项目")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '团队协作测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'团队协作测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 场景6: 数据质量监控场景 ====================
    
    def test_scenario_06_data_quality_monitoring(self):
        """场景6: 数据质量监控场景"""
        test_name = "数据质量监控"
        start_time = time.time()
        
        print("\n  模拟场景: 监控爬虫采集数据质量")
        
        try:
            # 1. 创建项目
            timestamp = int(time.time())
            project_data = {
                'name': f'数据质量测试项目_{timestamp}',
                'description': '用于测试数据质量监控',
                'team_id': 1
            }
            
            project = self.client.post('/api/v1/projects/', json_data=project_data)
            if not project or not project.get('id'):
                raise Exception('创建项目失败')
            print(f"    ✓ 创建项目: {project['name']}")
            
            self.test_resources['projects'].append(project)
            
            # 2. 配置数据质量检测规则
            quality_config = {
                'project_id': project['id'],
                'rules': [
                    {'type': 'volume', 'threshold': {'min': 100, 'max': 10000}},
                    {'type': 'null_rate', 'threshold': {'max': 0.1}},
                    {'type': 'duplicate_rate', 'threshold': {'max': 0.05}}
                ]
            }
            
            # 3. 触发数据质量检测
            check_result = self.client.post(
                '/api/v1/data-quality/check',
                json_data={'project_id': project['id']}
            )
            print(f"    ✓ 触发数据质量检测")
            
            # 4. 查看质量报告
            reports = self.client.get('/api/v1/data-quality/reports')
            print(f"    ✓ 查看质量报告: {len(reports) if reports else 0}条")
            
            # 5. 查看数据统计
            stats = self.client.get('/api/v1/data-quality/stats')
            print(f"    ✓ 查看数据统计")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '数据质量监控测试成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'数据质量监控测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def run_all_tests(self):
        """运行所有场景测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备工作
        print("\n[准备] 创建测试环境...")
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        # 执行场景测试
        print("\n" + "="*50)
        print("[场景1] 新用户注册并创建第一个项目")
        print("="*50)
        self.test_scenario_01_new_user_onboarding()
        
        print("\n" + "="*50)
        print("[场景2] 定时爬虫任务调度")
        print("="*50)
        self.test_scenario_02_scheduled_spider_task()
        
        print("\n" + "="*50)
        print("[场景3] 故障恢复测试")
        print("="*50)
        self.test_scenario_03_failure_recovery()
        
        print("\n" + "="*50)
        print("[场景4] 多项目管理")
        print("="*50)
        self.test_scenario_04_multiple_projects_management()
        
        print("\n" + "="*50)
        print("[场景5] 团队协作场景")
        print("="*50)
        self.test_scenario_05_team_collaboration()
        
        print("\n" + "="*50)
        print("[场景6] 数据质量监控场景")
        print("="*50)
        self.test_scenario_06_data_quality_monitoring()
        
        # 清理
        print("\n[清理] 清理测试资源...")
        self.cleanup()
        
        # 生成报告
        report_file = 'tests/reports/scenarios_test_report.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestScenarios()
    tester.run_all_tests()
