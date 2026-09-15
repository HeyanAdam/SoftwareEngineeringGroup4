-- =============================================================================
-- SG4 —— MySQL 初始化脚本 (幂等)
-- 位置: infra/mysql/init/01-init.sql
-- 挂载: docker-compose.yml -> ./infra/mysql/init:/docker-entrypoint-initdb.d:ro
--
-- 执行时机: *仅当* 数据卷 mysql_data 为空(首次启动)时, 由官方镜像
--           docker-entrypoint.sh 按文件名字典序执行。已有数据卷时不会重跑。
--           需要重跑: docker compose down -v (会删除数据, 谨慎!) 后重新 up。
--
-- 官方 entrypoint 已经根据环境变量完成了"建库 + 建账号 + 授权":
--   MYSQL_DATABASE            -> CREATE DATABASE IF NOT EXISTS <db> CHARACTER SET utf8mb4
--                                COLLATE utf8mb4_0900_ai_ci  (mysql:8.4 的默认排序规则)
--   MYSQL_USER/MYSQL_PASSWORD -> CREATE USER '<user>'@'%' + GRANT ALL ON <db>.*
-- 所以本文件 *不* 硬编码库名/用户名/密码(避免与 .env 不一致)。
--
-- 本文件的职责:
--   1) 字符集 sanity check —— 首次启动日志里能一眼看出 utf8mb4 是否生效;
--   2) 兜底把业务库的默认字符集对齐到 utf8mb4 / utf8mb4_0900_ai_ci;
--   3) 明确宣告: 业务表 *全部* 由 alembic 迁移创建 (容器入口执行
--      `alembic upgrade head`), 本文件不建任何业务表。
--      请勿在此写 CREATE TABLE, 否则会与 alembic 版本产生冲突。
--
-- 幂等性: 仅使用 SELECT / 幂等 ALTER DATABASE, 重复执行安全。
-- =============================================================================

-- 会话级字符集, 保证脚本内语句按 utf8mb4 处理(含 4 字节 emoji)
SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 1) 字符集 sanity check
--    期望输出: server_charset=utf8mb4 / server_collation=utf8mb4_0900_ai_ci
--    若显示 latin1 等值, 说明启动参数 --character-set-server 未生效,
--    请检查 docker-compose.yml 中 mysql 服务的 command。
-- ---------------------------------------------------------------------------
SELECT
  @@character_set_server   AS `server_charset`,
  @@collation_server       AS `server_collation`,
  @@character_set_database AS `database_charset`,
  @@collation_database     AS `database_collation`;

-- ---------------------------------------------------------------------------
-- 2) 兜底: 把业务库默认字符集对齐到 utf8mb4(幂等; 只改库级默认值, 不动表数据)
--    库名与 .env 的 MYSQL_DATABASE 保持一致, 默认 sg4。
--    注意: MySQL 的 ALTER DATABASE 不支持 IF EXISTS 子句; 因此本语句执行的前提
--    是 entrypoint 已按 MYSQL_DATABASE 建好库(正常情况下一定成立)。
--    若你把 MYSQL_DATABASE 改成了别的名字, 请同步修改下面的库名。
--    另外: 这里刻意不写 GRANT —— 账号与授权已由 entrypoint 依据环境变量完成,
--    重复授权没有收益, 且硬编码账号会与 .env 脱节。
-- ---------------------------------------------------------------------------
ALTER DATABASE `sg4`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 3) 业务表由 alembic 创建, 这里不建表。
--    验证迁移结果:
--      docker compose exec mysql mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" \
--        -e "SHOW TABLES; SHOW VARIABLES LIKE 'character_set_database';" "$MYSQL_DATABASE"
-- ---------------------------------------------------------------------------

-- =============================================================================
-- 提示: 需要新增 SQL 初始化步骤时, 在同一目录按 02-xxx.sql / 03-xxx.sql 命名,
--       官方 entrypoint 会按文件名字典序依次执行。
-- =============================================================================
