"""跨数据库方言的类型别名。

为什么要这个文件:
    《权限表》要求主键是 BIGINT 自增。MySQL 里 BIGINT AUTO_INCREMENT 没问题,
    但 SQLite 只有声明为 INTEGER PRIMARY KEY 的列才会自增(BIGINT 不会),
    直接用 BigInteger 会在本地 SQLite 环境插入失败。

    with_variant 让同一个模型在两套库上都正确:
        MySQL / PostgreSQL -> BIGINT
        SQLite            -> INTEGER(SQLite 的 rowid 别名, 自增有效)
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer

# 自增主键类型: 逻辑上是 BIGINT, 落到 SQLite 时退化为 INTEGER
BigIntPK = BigInteger().with_variant(Integer, "sqlite")
