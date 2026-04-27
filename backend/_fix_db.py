"""临时脚本：数据库修复和数据初始化"""
import pymysql

conn = pymysql.connect(
    host='117.72.16.51', port=3306,
    user='crawlo', password='bJjGTZN4cDf6bmjc',
    database='crawlo_pilot'
)
cur = conn.cursor()

# 将用户加入团队
cur.execute("INSERT IGNORE INTO team_member (user_id, team_id, role) VALUES (2, 1, 'owner')")
cur.execute("INSERT IGNORE INTO team_member (user_id, team_id, role) VALUES (1, 1, 'member')")
conn.commit()

# 检查团队关系
cur.execute('SELECT * FROM team_member')
print("=== team_member ===")
for row in cur.fetchall():
    print(row)

# 检查用户表
cur.execute('SELECT id, username, email FROM user')
print("\n=== users ===")
for row in cur.fetchall():
    print(row)

conn.close()
print("\nDone!")
