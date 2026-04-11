# 测试指南

## 概述
CrawloPilot提供完整的测试体系，包括单元测试、集成测试和页面级联调测试。

## 测试结构

```
tests/
├── unit/                    # 单元测试
│   ├── test_01_auth.py     # 认证测试
│   ├── test_02_projects.py # 项目测试
│   ├── test_03_schedule.py # 调度测试
│   ├── test_04_monitor.py  # 监控测试
│   ├── test_05_quality.py  # 质量测试
│   ├── test_06_proxy_api.py # 代理和API测试
│   ├── test_07_security_audit.py # 安全审计测试
│   ├── test_edge_cases.py  # 边界情况测试
│   └── test_performance.py # 性能测试
├── integration/             # 集成测试
│   ├── test_integration.py # API集成测试
│   └── pages/              # 页面级测试
│       ├── page_test_base.py
│       ├── test_login_page.py
│       ├── test_dashboard_page.py
│       ├── test_projects_page.py
│       └── ...
├── scenarios/               # 测试场景
│   └── test_scenarios.py
├── conftest.py             # pytest配置
├── run_all_tests.py        # 测试运行器
└── project_assessment.py   # 项目评估
```

## 运行测试

### 运行所有测试
```bash
cd /Users/oscar/projects/CrawloPilot
python tests/run_all_tests.py
```

### 运行单元测试
```bash
pytest tests/unit/ -v
```

### 运行特定测试
```bash
pytest tests/unit/test_01_auth.py -v
```

### 运行集成测试
```bash
pytest tests/integration/ -v
```

### 运行页面级测试
```bash
python tests/integration/pages/run_page_tests.py
```

### 带覆盖率报告
```bash
pytest tests/ --cov=backend/app --cov-report=html
```

## 单元测试

### 测试结构
```python
import pytest
from fastapi.testclient import TestClient

class TestAuth:
    """认证模块测试"""
    
    def test_login_success(self, client, test_user):
        """测试登录成功"""
        response = client.post("/api/v1/auth/login", data={
            "username": test_user.username,
            "password": "testpassword"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()
    
    def test_login_invalid_password(self, client, test_user):
        """测试登录失败-密码错误"""
        response = client.post("/api/v1/auth/login", data={
            "username": test_user.username,
            "password": "wrongpassword"
        })
        assert response.status_code == 401
```

### 测试夹具（Fixtures）
位置: `tests/conftest.py`

```python
@pytest.fixture
def client():
    """测试客户端"""
    from app.main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def test_user(db_session):
    """测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("testpassword")
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def auth_headers(client, test_user):
    """认证请求头"""
    response = client.post("/api/v1/auth/login", data={
        "username": test_user.username,
        "password": "testpassword"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### 测试数据库
- 使用独立的测试数据库
- 每个测试用例独立事务
- 测试后自动清理

## 集成测试

### API集成测试
```python
class TestProjectAPI:
    """项目API集成测试"""
    
    def test_create_project(self, client, auth_headers):
        """测试创建项目"""
        response = client.post("/api/v1/projects/", json={
            "name": "Test Project",
            "description": "A test project"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Project"
        assert "id" in data
        
        # 验证数据库
        project = db.query(Project).filter(Project.id == data["id"]).first()
        assert project is not None
```

### 页面级联调测试
位置: `tests/integration/pages/`

```python
from page_test_base import BasePageTest

class TestLoginPage(BasePageTest):
    """登录页面测试"""
    
    def test_page_load(self):
        """测试页面加载"""
        self.navigate_to('/login')
        assert self.page.title() == 'Login - CrawloPilot'
    
    def test_login_success(self):
        """测试登录成功"""
        self.login('admin', 'admin123')
        self.wait_for_url('/dashboard')
        assert '/dashboard' in self.page.url()
    
    def test_login_invalid_password(self):
        """测试密码错误"""
        self.login('admin', 'wrong')
        error_msg = self.get_error_message()
        assert 'Incorrect username or password' in error_msg
```

### 页面测试基类
```python
class BasePageTest:
    """页面测试基类"""
    
    def setup_method(self):
        """每个测试前执行"""
        self.browser = playwright.chromium.launch()
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
    
    def teardown_method(self):
        """每个测试后执行"""
        self.browser.close()
    
    def navigate_to(self, path):
        """导航到页面"""
        self.page.goto(f"http://localhost:3000{path}")
    
    def login(self, username, password):
        """执行登录"""
        self.navigate_to('/login')
        self.page.fill('input[name="username"]', username)
        self.page.fill('input[name="password"]', password)
        self.page.click('button[type="submit"]')
```

## 测试场景

### 完整工作流测试
```python
def test_complete_workflow():
    """测试完整工作流程"""
    client = TestClient(app)
    
    # 1. 登录
    token = login(client, "admin", "admin123")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. 创建项目
    project = create_project(client, headers, "Test Project")
    
    # 3. 克隆Git仓库
    git_clone(client, headers, project["id"], {
        "url": "https://github.com/user/repo.git"
    })
    
    # 4. 创建调度任务
    schedule = create_schedule(client, headers, project["id"])
    
    # 5. 触发任务
    trigger_schedule(client, headers, schedule["id"])
    
    # 6. 查看监控数据
    metrics = get_metrics(client, headers)
    assert metrics["total_tasks"] > 0
```

## 编写测试

### 测试命名规范
```python
# 格式: test_<功能>_<场景>_<预期结果>
def test_login_success_with_valid_credentials():
    pass

def test_login_fail_with_invalid_password():
    pass

def test_create_project_success():
    pass

def test_create_project_fail_duplicate_name():
    pass
```

### 测试组织原则
1. **AAA模式**: Arrange（准备） → Act（执行） → Assert（断言）
2. **单一职责**: 每个测试只验证一个功能点
3. **独立性**: 测试之间互不依赖
4. **可重复**: 每次运行结果一致

### 断言示例
```python
# 状态码
assert response.status_code == 200

# 响应数据
assert response.json()["status"] == "success"

# 数据库验证
assert db.query(User).count() == 1

# 异常测试
with pytest.raises(HTTPException) as exc:
    await some_function()
assert exc.value.status_code == 404
```

## 测试覆盖率

### 查看覆盖率
```bash
pytest --cov=backend/app --cov-report=term-missing
```

### 覆盖率目标
- 核心业务逻辑: > 90%
- API接口: > 85%
- 工具函数: > 80%
- 整体覆盖率: > 80%

### 排除项
```ini
# .coveragerc
[run]
omit =
    tests/*
    backend/app/models/*
    backend/app/schemas/*
    */__init__.py
```

## 性能测试

### 响应时间测试
```python
import time

def test_api_response_time():
    """测试API响应时间"""
    start = time.time()
    response = client.get("/api/v1/projects/")
    elapsed = time.time() - start
    
    assert elapsed < 0.5  # 500ms以内
    assert response.status_code == 200
```

### 并发测试
```python
from concurrent.futures import ThreadPoolExecutor

def test_concurrent_requests():
    """测试并发请求"""
    def make_request():
        return client.get("/api/v1/projects/")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(100)]
        results = [f.result() for f in futures]
    
    # 所有请求都应该成功
    assert all(r.status_code == 200 for r in results)
```

## 持续集成

### GitHub Actions
位置: `.github/workflows/ci.yml`

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      mysql:
        image: mysql:8.0
      redis:
        image: redis:7
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest tests/ --cov=backend/app
```

## 调试技巧

### 1. 打印响应
```python
def test_debug():
    response = client.get("/api/v1/projects/")
    print(response.status_code)
    print(response.json())
    assert False  # 暂停测试
```

### 2. 使用pdb
```python
import pdb

def test_debug():
    response = client.post("/api/v1/auth/login", data={...})
    pdb.set_trace()  # 断点
    assert response.status_code == 200
```

### 3. 查看SQL
```python
from sqlalchemy import event

@event.listens_for(db_session, "before_cursor_execute")
def log_sql(conn, cursor, statement, parameters, context, executemany):
    print(f"SQL: {statement}")
    print(f"Params: {parameters}")
```

## 常见问题

### Q: 测试数据库连接失败
```bash
# 确保测试数据库存在
mysql -u root -p -e "CREATE DATABASE test_crawlopilot;"
```

### Q: 测试数据污染
- 使用事务回滚
- 每个测试独立数据
- 测试后清理数据

### Q: 前端测试失败
- 确保前端服务运行在3000端口
- 检查浏览器驱动
- 增加等待时间

## 最佳实践

1. **先写测试**: TDD开发模式
2. **频繁运行**: 每次修改后运行相关测试
3. **保持快速**: 单个测试< 1秒
4. **有意义的断言**: 清晰的失败信息
5. **测试边界**: 正常值、边界值、异常值
6. **Mock外部依赖**: 数据库、API、文件系统
7. **定期审查**: 删除过时测试，补充缺失测试

## 测试检查清单

提交代码前确认：
- [ ] 所有单元测试通过
- [ ] 集成测试通过
- [ ] 新增代码有测试覆盖
- [ ] 测试覆盖率未下降
- [ ] 无性能回退

## 相关资源
- [pytest文档](https://docs.pytest.org/)
- [FastAPI测试](https://fastapi.tiangolo.com/tutorial/testing/)
- [Playwright文档](https://playwright.dev/python/)
- [覆盖率工具](https://coverage.readthedocs.io/)
