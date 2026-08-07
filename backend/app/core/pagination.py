"""
分页参数钳制工具

统一钳制 limit/skip 到合法范围，避免负数（如 limit=-1）传入
SQLAlchemy 的 .limit()/.offset() 导致 500。
"""


def clamp_pagination(
    skip: int = 0,
    limit: int = 20,
    default_limit: int = 20,
    max_limit: int = 200,
) -> tuple:
    """钳制分页参数，返回 (skip, limit)。

    - skip 下限 0
    - limit 下限 1，上限 max_limit；None/0 时回落到 default_limit
    """
    try:
        skip_i = int(skip or 0)
    except (TypeError, ValueError):
        skip_i = 0
    try:
        limit_i = int(limit or default_limit)
    except (TypeError, ValueError):
        limit_i = default_limit

    skip_i = max(skip_i, 0)
    limit_i = min(max(limit_i, 1), max_limit)
    return skip_i, limit_i
