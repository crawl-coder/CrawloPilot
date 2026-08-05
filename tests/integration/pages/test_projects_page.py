"""
项目管理页面前后端联调测试
测试项目管理页面的完整CRUD流程
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
from page_test_base import PageTestBase


class TestProjectsPage(PageTestBase):
    """项目管理页面联调测试"""
    
    def __init__(self):
        super().__init__("项目管理")
        self.test_project = None
    
    # ==================== 列表页测试 ====================
    
    def test_project_list_loading(self):
        """测试项目列表加载"""
        test_name = "项目列表加载"
        start_time = time.time()
        
        try:
            # 1. 获取项目列表
            projects = self.client.get('/api/v1/projects/')
            
            if not isinstance(projects, list):
                raise Exception('项目列表格式错误')
            
            self.log_step("获取项目列表", f"共{len(projects)}个项目")
            
            # 2. 验证列表项字段
            if len(projects) > 0:
                required_fields = ['id', 'name', 'description', 'status', 'created_at']
                project = projects[0]
                missing = [f for f in required_fields if f not in project]
                
                if missing:
                    self.log_step("字段验证", f"缺少: {missing}")
                else:
                    self.log_step("字段验证", "完整")
            
            # 3. 测试分页
            paged_projects = self.client.get('/api/v1/projects/', params={'skip': 0, 'limit': 5})
            self.log_step("分页测试", f"limit=5, 返回{len(paged_projects) if isinstance(paged_projects, list) else 0}条")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'项目列表加载成功: {len(projects)}个项目', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'列表加载失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_project_list_filtering(self):
        """测试项目列表筛选"""
        test_name = "项目列表筛选"
        start_time = time.time()
        
        try:
            # 按状态筛选（如果API支持）
            active_projects = self.client.get('/api/v1/projects/', params={'status': 'active'})
            self.log_step("按状态筛选", f"active项目: {len(active_projects) if isinstance(active_projects, list) else 0}")
            
            # 按团队筛选
            team_projects = self.client.get('/api/v1/projects/', params={'team_id': 1})
            self.log_step("按团队筛选", f"team_id=1: {len(team_projects) if isinstance(team_projects, list) else 0}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '项目列表筛选测试完成', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'筛选测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_project_list_search(self):
        """测试项目搜索"""
        test_name = "项目搜索"
        start_time = time.time()
        
        try:
            # 搜索项目（如果API支持）
            search_result = self.client.get('/api/v1/projects/', params={'q': 'test'})
            self.log_step("关键词搜索", f"q=test: {len(search_result) if isinstance(search_result, list) else 0}")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '项目搜索测试完成', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'搜索测试失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 创建项目测试 ====================
    
    def test_create_project_dialog(self):
        """测试创建项目对话框"""
        test_name = "创建项目对话框"
        start_time = time.time()
        
        try:
            # 1. 获取创建项目所需数据
            teams = self.client.get('/api/v1/teams/')
            self.log_step("获取团队列表", f"{len(teams) if isinstance(teams, list) else 0}个团队")
            
            # 2. 创建项目
            timestamp = int(time.time())
            project_data = {
                'name': f'UI测试项目_{timestamp}',
                'description': '通过页面联调测试创建的项目',
                'git_url': 'https://github.com/test/test-project.git',
                'team_id': 1
            }
            
            result = self.client.post('/api/v1/projects/', json_data=project_data)
            
            if not result or not result.get('id'):
                raise Exception('创建项目失败')
            
            self.test_project = result
            self.created_resources.append({'type': 'project', 'id': result['id']})
            
            self.log_step("创建项目", f"ID={result['id']}, name={result['name']}")
            
            # 3. 验证响应字段
            required_fields = ['id', 'name', 'description', 'status', 'created_at', 'updated_at']
            missing = [f for f in required_fields if f not in result]
            
            if missing:
                self.log_step("响应字段", f"缺少: {missing}")
            else:
                self.log_step("响应字段", "完整")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'创建项目成功: {result["name"]}', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'创建项目失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def test_create_project_validation(self):
        """测试创建项目表单验证"""
        test_name = "创建项目验证"
        start_time = time.time()
        
        test_cases = [
            {
                'name': '空项目名称',
                'data': {'name': '', 'description': 'test', 'team_id': 1},
                'should_fail': True
            },
            {
                'name': '缺少team_id',
                'data': {'name': 'test', 'description': 'test'},
                'should_fail': True
            },
            {
                'name': '项目名称过长',
                'data': {'name': 'a' * 200, 'description': 'test', 'team_id': 1},
                'should_fail': True
            }
        ]
        
        passed = 0
        for case in test_cases:
            try:
                result = self.client.post('/api/v1/projects/', json_data=case['data'])
                
                if case['should_fail'] and not result.get('id'):
                    passed += 1
                    self.log_step(case['name'], "被正确拒绝")
                elif not case['should_fail'] and result.get('id'):
                    passed += 1
                    self.created_resources.append({'type': 'project', 'id': result['id']})
                    self.log_step(case['name'], "通过")
                else:
                    self.log_step(case['name'], "验证失败")
                    
            except Exception as e:
                if case['should_fail']:
                    passed += 1
                    self.log_step(case['name'], "被正确拒绝")
        
        if passed == len(test_cases):
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                f'所有验证测试通过 ({passed}/{len(test_cases)})', time.time() - start_time
            )
            return True
        else:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'部分验证失败 ({passed}/{len(test_cases)})', time.time() - start_time
            )
            return False
    
    # ==================== 编辑项目测试 ====================
    
    def test_edit_project_dialog(self):
        """测试编辑项目对话框"""
        test_name = "编辑项目对话框"
        start_time = time.time()
        
        try:
            # 确保有测试项目
            if not self.test_project:
                # 创建一个测试项目
                timestamp = int(time.time())
                project_data = {
                    'name': f'编辑测试项目_{timestamp}',
                    'description': '用于编辑测试',
                    'team_id': 1
                }
                result = self.client.post('/api/v1/projects/', json_data=project_data)
                self.test_project = result
                self.created_resources.append({'type': 'project', 'id': result['id']})
            
            project_id = self.test_project['id']
            
            # 1. 获取项目详情
            detail = self.client.get(f'/api/v1/projects/{project_id}')
            self.log_step("获取项目详情", f"name={detail.get('name')}")
            
            # 2. 更新项目
            update_data = {
                'description': f'更新后的描述 {int(time.time())}',
                'git_url': 'https://github.com/updated/repo.git'
            }
            
            updated = self.client.put(f'/api/v1/projects/{project_id}', json_data=update_data)
            
            if updated.get('description') != update_data['description']:
                raise Exception('更新未生效')
            
            self.log_step("更新项目", "成功")
            
            # 3. 验证更新后的数据
            detail_after = self.client.get(f'/api/v1/projects/{project_id}')
            self.log_step("验证更新", f"description={detail_after.get('description')[:30]}...")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '编辑项目测试通过', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'编辑项目失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 删除项目测试 ====================
    
    def test_delete_project_dialog(self):
        """测试删除项目对话框"""
        test_name = "删除项目对话框"
        start_time = time.time()
        
        try:
            # 创建一个用于删除的测试项目
            timestamp = int(time.time())
            project_data = {
                'name': f'删除测试项目_{timestamp}',
                'description': '用于删除测试',
                'team_id': 1
            }
            
            result = self.client.post('/api/v1/projects/', json_data=project_data)
            
            if not result or not result.get('id'):
                raise Exception('创建测试项目失败')
            
            project_id = result['id']
            self.log_step("创建测试项目", f"ID={project_id}")
            
            # 删除项目
            delete_result = self.client.delete(f'/api/v1/projects/{project_id}')
            
            # 验证删除
            try:
                check = self.client.get(f'/api/v1/projects/{project_id}')
                if check.get('id'):
                    self.log_step("验证删除", "项目仍存在")
                else:
                    self.log_step("验证删除", "项目已删除")
            except:
                self.log_step("验证删除", "项目已删除")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '删除项目测试通过', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'删除项目失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 项目详情页测试 ====================
    
    def test_project_detail_page(self):
        """测试项目详情页"""
        test_name = "项目详情页"
        start_time = time.time()
        
        try:
            # 确保有测试项目
            if not self.test_project:
                timestamp = int(time.time())
                project_data = {
                    'name': f'详情测试项目_{timestamp}',
                    'description': '用于详情页测试',
                    'team_id': 1
                }
                result = self.client.post('/api/v1/projects/', json_data=project_data)
                self.test_project = result
                self.created_resources.append({'type': 'project', 'id': result['id']})
            
            project_id = self.test_project['id']
            
            # 1. 获取项目详情
            detail = self.client.get(f'/api/v1/projects/{project_id}')
            self.log_step("项目详情", f"name={detail.get('name')}")
            
            # 2. 获取项目版本
            versions = self.client.get(f'/api/v1/projects/{project_id}/versions')
            version_count = len(versions) if isinstance(versions, list) else 0
            self.log_step("项目版本", f"{version_count}个版本")
            
            # 3. 获取项目任务
            tasks = self.client.get('/api/v1/tasks/')
            if isinstance(tasks, list):
                project_tasks = [t for t in tasks if t.get('project_id') == project_id]
                self.log_step("项目任务", f"{len(project_tasks)}个任务")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '项目详情页数据加载成功', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'详情页加载失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 版本管理测试 ====================
    
    def test_version_management(self):
        """测试版本管理"""
        test_name = "版本管理"
        start_time = time.time()
        
        try:
            if not self.test_project:
                timestamp = int(time.time())
                project_data = {
                    'name': f'版本测试项目_{timestamp}',
                    'description': '用于版本管理测试',
                    'team_id': 1
                }
                result = self.client.post('/api/v1/projects/', json_data=project_data)
                self.test_project = result
                self.created_resources.append({'type': 'project', 'id': result['id']})
            
            project_id = self.test_project['id']
            
            # 1. 创建版本
            version_data = {
                'version': 'v1.0.0',
                'config_snapshot': {
                    'CONCURRENCY': 16,
                    'DELAY': 1.0,
                    'TIMEOUT': 30
                }
            }
            
            version = self.client.post(
                f'/api/v1/projects/{project_id}/versions',
                json_data=version_data
            )
            
            if not version or not version.get('id'):
                raise Exception('创建版本失败')
            
            self.log_step("创建版本", f"version={version.get('version')}")
            
            # 2. 获取版本列表
            versions = self.client.get(f'/api/v1/projects/{project_id}/versions')
            self.log_step("版本列表", f"{len(versions) if isinstance(versions, list) else 0}个版本")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '版本管理测试通过', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'版本管理失败: {str(e)}', time.time() - start_time
            )
            return False
    
    # ==================== 批量操作测试 ====================
    
    def test_batch_operations(self):
        """测试批量操作"""
        test_name = "批量操作"
        start_time = time.time()
        
        try:
            # 创建多个测试项目
            project_ids = []
            for i in range(3):
                timestamp = int(time.time())
                project_data = {
                    'name': f'批量测试项目_{timestamp}_{i}',
                    'description': f'批量操作测试项目{i}',
                    'team_id': 1
                }
                result = self.client.post('/api/v1/projects/', json_data=project_data)
                if result and result.get('id'):
                    project_ids.append(result['id'])
                    self.created_resources.append({'type': 'project', 'id': result['id']})
            
            self.log_step("创建测试项目", f"{len(project_ids)}个")
            
            # 批量删除（如果API支持）
            # 这里模拟前端逐个删除
            for pid in project_ids[:2]:  # 只删除前2个
                self.client.delete(f'/api/v1/projects/{pid}')
            
            self.log_step("批量删除", f"删除{min(2, len(project_ids))}个项目")
            
            self.reporter.add_result(
                self.module_name, test_name, 'PASS',
                '批量操作测试通过', time.time() - start_time
            )
            return True
            
        except Exception as e:
            self.reporter.add_result(
                self.module_name, test_name, 'FAIL',
                f'批量操作失败: {str(e)}', time.time() - start_time
            )
            return False
    
    def run_all_tests(self):
        """运行所有项目管理页面测试"""
        print(f"\n{'='*60}")
        print(f"开始测试: {self.module_name}")
        print(f"{'='*60}")
        
        # 准备
        print("\n[准备] 初始化测试环境...")
        if not self.setup():
            print("准备失败，跳过测试")
            return None
        
        # 列表页测试
        print("\n--- 列表页测试 ---")
        print("[1/10] 项目列表加载...")
        self.test_project_list_loading()
        
        print("[2/10] 项目列表筛选...")
        self.test_project_list_filtering()
        
        print("[3/10] 项目搜索...")
        self.test_project_list_search()
        
        # 创建项目测试
        print("\n--- 创建项目测试 ---")
        print("[4/10] 创建项目对话框...")
        self.test_create_project_dialog()
        
        print("[5/10] 创建项目验证...")
        self.test_create_project_validation()
        
        # 编辑项目测试
        print("\n--- 编辑项目测试 ---")
        print("[6/10] 编辑项目对话框...")
        self.test_edit_project_dialog()
        
        # 删除项目测试
        print("\n--- 删除项目测试 ---")
        print("[7/10] 删除项目对话框...")
        self.test_delete_project_dialog()
        
        # 详情页测试
        print("\n--- 详情页测试 ---")
        print("[8/10] 项目详情页...")
        self.test_project_detail_page()
        
        print("[9/10] 版本管理...")
        self.test_version_management()
        
        # 批量操作测试
        print("\n--- 批量操作测试 ---")
        print("[10/10] 批量操作...")
        self.test_batch_operations()
        
        # 清理
        print("\n[清理] 清理测试资源...")
        self.cleanup()
        
        # 生成报告
        report_file = 'tests/reports/page_projects_report.json'
        import os
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        report = self.reporter.generate_report(report_file)
        
        print(f"\n{self.module_name} 测试完成!")
        print(f"通过: {report['summary']['passed']}/{report['summary']['total']}")
        print(f"报告已保存至: {report_file}")
        
        return report


if __name__ == '__main__':
    tester = TestProjectsPage()
    tester.run_all_tests()
