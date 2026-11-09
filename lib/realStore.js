'use strict';
/**
 * realStore —— 真实组件数据访问层
 *   Redis : 真实 redis-server（bin/redis，6379）—— 库存预扣 / Lua 脚本 / 订单队列
 *   MySQL : 真实 mysqld（bin/mysql，3306）—— 权威库存与订单表
 * 业务代码使用的命令语义与生产一致，可平滑替换为云端 Redis/MySQL。
 */
const fs = require('fs');
const path = require('path');
const Redis = require('ioredis');
const mysql = require('mysql2/promise');

const redis = new Redis({ host: '127.0.0.1', port: 6379, lazyConnect: false });

/** 消费者专用连接：BRPOP 是阻塞命令，必须用独立连接，否则会卡住主连接上的所有命令 */
function newConsumer() {
  return redis.duplicate();
}
const LUA_DIR = path.join(__dirname, '..', 'lua');

let pool = null;
let versions = { redis: '-', mysql: '-' };

/* ---------- Lua 脚本加载（生产惯例：SCRIPT LOAD 后用 EVALSHA） ---------- */
const lua = {};
function loadLua(name) {
  const file = path.join(LUA_DIR, name);
  lua[name] = fs.readFileSync(file, 'utf8');
  return lua[name];
}

async function ensureLuaLoaded() {
  for (const name of ['seckill.lua', 'ratelimit.lua']) {
    if (!lua[name]) loadLua(name);
    // SCRIPT LOAD 幂等：返回 sha；EVALSHA 未命中时自动降级 EVAL
    await redis.script('LOAD', lua[name]);
  }
}

/* ---------- MySQL 初始化：建库建表（幂等：重试时跳过已建好的池，避免泄漏） ---------- */
async function initMysql() {
  if (pool) return;
  pool = mysql.createPool({
    host: '127.0.0.1', port: 3306, user: 'root', password: '',
    // 200 并发实验的连接数上限：给 mysqld max_connections 留出余量，避免 errno 1040
    database: 'miaosha', connectionLimit: 120, waitForConnections: true,
  });
  await pool.query(`
    CREATE TABLE IF NOT EXISTS goods (
      id    VARCHAR(32) PRIMARY KEY,
      name  VARCHAR(128) NOT NULL,
      stock INT NOT NULL DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);
  await pool.query(`
    CREATE TABLE IF NOT EXISTS orders (
      order_id   VARCHAR(48) PRIMARY KEY,
      user_id    VARCHAR(32) NOT NULL,
      goods_id   VARCHAR(32) NOT NULL,
      status     VARCHAR(16) NOT NULL,
      created_at DATETIME(3) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);
}

/* ---------- 版本探测（引擎徽章展示，成功后缓存；失败允许下次重新探测） ---------- */
let versionsDetected = false;
async function detectVersions() {
  if (versionsDetected) return versions;
  try {
    const info = await redis.info('server');
    const m = info.match(/redis_version:([\d.]+)/);
    versions.redis = m ? 'Redis ' + m[1] : 'Redis';
  } catch (_) { versions.redis = 'Redis 不可达'; }
  try {
    const [[row]] = await pool.query('SELECT VERSION() v');
    versions.mysql = 'MySQL ' + row.v;
  } catch (_) { versions.mysql = 'MySQL 不可达'; }
  if (versions.redis !== 'Redis 不可达' && versions.mysql !== 'MySQL 不可达') versionsDetected = true;
  return versions;
}

/* ---------- 管理通道：用独立连接发 KILL（池连接全忙时 pool.query 会死锁） ---------- */
let adminConn = null;
async function killQuery(threadId) {
  try {
    if (!adminConn) {
      adminConn = await mysql.createConnection({ host: '127.0.0.1', port: 3306, user: 'root', password: '' });
    }
    await adminConn.query('KILL QUERY ' + threadId);
  } catch (_) { /* 连接失效时下次重建 */ adminConn = null; }
}

/* ---------- 初始化入口 ---------- */
async function init() {
  await initMysql();
  // 真实连通性检查：createPool 是惰性的，建表被幂等跳过时不能证明 MySQL 已就绪，
  // 必须显式 ping 一次，否则重试循环会"假成功"导致后续业务预热失败
  await pool.query('SELECT 1');
  await ensureLuaLoaded();
  await detectVersions();
}

/* ---------- 商品/库存重置 ---------- */
async function resetGoods(goodsId, name, stock) {
  await pool.query(
    `INSERT INTO goods (id, name, stock) VALUES (?, ?, ?)
     ON DUPLICATE KEY UPDATE name = VALUES(name), stock = VALUES(stock)`,
    [goodsId, name, stock]);
  await redis.set('stock:' + goodsId, stock);
  await redis.del('bought:' + goodsId);
}

async function getDbStock(goodsId) {
  const [[row]] = await pool.query('SELECT stock FROM goods WHERE id = ?', [goodsId]);
  return row ? row.stock : null;
}

async function countOrders() {
  const [[row]] = await pool.query('SELECT COUNT(*) c FROM orders');
  return row.c;
}

async function recentOrders(limit = 50) {
  const [rows] = await pool.query(
    'SELECT order_id, user_id, goods_id, status, created_at FROM orders ORDER BY created_at DESC LIMIT ?',
    [limit]);
  return rows;
}

module.exports = { redis, newConsumer, pool: () => pool, lua, loadLua, ensureLuaLoaded, init, detectVersions, versions, resetGoods, getDbStock, countOrders, recentOrders, killQuery };
