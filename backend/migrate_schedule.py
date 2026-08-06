"""
定时任务功能迁移脚本（幂等）

- schedule 表补充 spider_id / name / run_at / timezone / last_run_* / run_count 等列
- 按 spider_name 匹配回填 spider_id（匹配不到的行置 enabled=0）
- task_instance 增加 expected_run_at 列 + (schedule_id, expected_run_at) 唯一索引

可直接运行：python migrate_schedule.py
"""
import logging

from sqlalchemy import text

from app.core.database import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migrate_schedule")


SCHEDULE_COLUMNS = {
    "name": "VARCHAR(128)",
    "spider_id": "BIGINT",
    "run_at": "DATETIME",
    "timezone": "VARCHAR(64) DEFAULT 'Asia/Shanghai'",
    "last_run_at": "DATETIME",
    "last_run_status": "VARCHAR(32)",
    "last_run_task_id": "BIGINT",
    "run_count": "INTEGER DEFAULT 0",
    "success_count": "INTEGER DEFAULT 0",
    "fail_count": "INTEGER DEFAULT 0",
    "description": "TEXT",
    "created_by": "BIGINT",
}


def _existing_columns(conn, table: str) -> set:
    rows = conn.execute(text(f"SHOW COLUMNS FROM {table}")).fetchall()
    return {r[0] for r in rows}


def _add_column(conn, table: str, name: str, ddl: str):
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
    logger.info("  + %s.%s", table, name)


def migrate_schedule_table(conn):
    logger.info("schedule 表补列...")
    existing = _existing_columns(conn, "schedule")
    for name, ddl in SCHEDULE_COLUMNS.items():
        if name not in existing:
            _add_column(conn, "schedule", name, ddl)

    # 回填 spider_id（按名称匹配；匹配不到置 enabled=0）
    logger.info("回填 schedule.spider_id ...")
    result = conn.execute(text(
        "UPDATE schedule s JOIN spider sp ON sp.name = s.spider_name "
        "SET s.spider_id = sp.id"
    ))
    logger.info("  匹配回填 %s 行", result.rowcount)
    result = conn.execute(text(
        "UPDATE schedule SET enabled = 0 WHERE spider_id IS NULL"
    ))
    logger.info("  未匹配置禁用 %s 行", result.rowcount)


def migrate_task_instance_table(conn):
    logger.info("task_instance 表补列...")
    existing = _existing_columns(conn, "task_instance")
    if "expected_run_at" not in existing:
        _add_column(conn, "task_instance", "expected_run_at", "DATETIME")
    indexes = {r[2] for r in conn.execute(text("SHOW INDEX FROM task_instance")).fetchall()}
    if "uq_schedule_expected_run" not in indexes:
        conn.execute(text(
            "ALTER TABLE task_instance ADD UNIQUE INDEX "
            "uq_schedule_expected_run (schedule_id, expected_run_at)"
        ))
        logger.info("  + task_instance 唯一索引 uq_schedule_expected_run")


def main():
    with engine.begin() as conn:
        migrate_schedule_table(conn)
        migrate_task_instance_table(conn)
    logger.info("迁移完成")


if __name__ == "__main__":
    main()
