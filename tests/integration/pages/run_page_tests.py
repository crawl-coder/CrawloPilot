#!/usr/bin/env python
"""
页面联调测试运行器
运行所有页面的前后端联调测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import json
from datetime import datetime

# 导入所有页面测试
from test_login_page import TestLoginPage
from test_dashboard_page import TestDashboardPage
from test_projects_page import TestProjectsPage
from test_users_page import TestUsersPage
from test_schedules_page import TestSchedulesPage
from test_monitoring_page import TestMonitoringPage


class PageTestRunner:
    """页面联调测试运行器"""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
    
    def run_all_page_tests(self):
        """运行所有页面测试"""
        self.start_time = time.time()
        
        print("\n" + "="*70)
        print("  CrawloPilot 页面联调测试套件")
        print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # 定义所有页面测试
        page_tests = [
            ("登录页面", TestLoginPage),
            ("Dashboard首页", TestDashboardPage),
            ("项目管理", TestProjectsPage),
            ("用户管理", TestUsersPage),
            ("任务调度", TestSchedulesPage),
            ("监控告警", TestMonitoringPage),
        ]
        
        total_passed = 0
        total_failed = 0
        
        for page_name, test_class in page_tests:
            print(f"\n{'='*70}")
            print(f"  测试页面: {page_name}")
            print(f"{'='*70}")
            
            try:
                tester = test_class()
                report = tester.run_all_tests()
                
                if report:
                    self.results[page_name] = report
                    total_passed += report['summary']['passed']
                    total_failed += report['summary']['failed']
                    
            except Exception as e:
                print(f"\n  ✗ {page_name} 测试异常: {str(e)}")
                self.results[page_name] = {
                    'error': str(e),
                    'summary': {'passed': 0, 'failed': 0, 'total': 0}
                }
        
        # 生成汇总报告
        self.generate_summary_report(total_passed, total_failed)
    
    def generate_summary_report(self, total_passed, total_failed):
        """生成汇总报告"""
        total_duration = time.time() - self.start_time
        total_tests = total_passed + total_failed
        
        print("\n" + "="*70)
        print("  页面联调测试汇总报告")
        print("="*70)
        
        print(f"\n  测试统计:")
        print(f"  ├─ 总测试数: {total_tests}")
        print(f"  ├─ 通过: {total_passed}")
        print(f"  ├─ 失败: {total_failed}")
        print(f"  ├─ 通过率: {total_passed/total_tests*100:.1f}%" if total_tests > 0 else "  ├─ 通过率: N/A")
        print(f"  └─ 总耗时: {total_duration:.2f}秒")
        
        print(f"\n  各页面测试结果:")
        for page_name, result in self.results.items():
            summary = result.get('summary', {})
            passed = summary.get('passed', 0)
            total = summary.get('total', 0)
            status = "✓" if passed == total and total > 0 else "✗"
            print(f"  {status} {page_name}: {passed}/{total}")
        
        # 保存汇总报告
        summary_report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': total_passed,
                'failed': total_failed,
                'pass_rate': f"{total_passed/total_tests*100:.1f}%" if total_tests > 0 else "N/A",
                'total_duration': f"{total_duration:.2f}s"
            },
            'page_results': self.results
        }
        
        report_file = 'tests/reports/page_tests_summary.json'
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(summary_report, f, ensure_ascii=False, indent=2)
        
        print(f"\n  详细报告已保存至: {report_file}")
        print("="*70)


if __name__ == '__main__':
    runner = PageTestRunner()
    runner.run_all_page_tests()
