"""查询节点和项目列表"""
import requests, json

login = requests.post("http://localhost:8000/api/v1/auth/login", data={"username":"admin","password":"admin123"})
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("="*60)
print("节点列表:")
nodes = requests.get("http://localhost:8000/api/v1/nodes", headers=headers)
print(json.dumps(nodes.json(), indent=2, ensure_ascii=False))

print("="*60)
print("\n项目列表:")
projects = requests.get("http://localhost:8000/api/v1/projects?skip=0&limit=50", headers=headers)
print(json.dumps(projects.json(), indent=2, ensure_ascii=False))

print("="*60)
print("\n爬虫列表:")
spiders = requests.get("http://localhost:8000/api/v1/spiders?skip=0&limit=50", headers=headers)
print(json.dumps(spiders.json(), indent=2, ensure_ascii=False))
