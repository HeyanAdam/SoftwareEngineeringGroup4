'use strict';
/**
 * 热点数据缓存实验（真实 Redis + 真实 MySQL）
 *
 * 场景：电商后台有 6 个商品，数据的真身都在 MySQL。
 *   - 其中 3 个是已经在 Redis 里预热好的热点商品
 *   - 另外 3 个只在 MySQL，没进缓存
 *
 * 用户每打开一次商品详情，就走一次 Cache-Aside：
 *   GET Redis 命中 → 直接返回（快）
 *   未命中 → SELECT MySQL → 回源结果 SETEX 写回 Redis（慢，但之后都快）
 *
 * 「商品怎么变成热点」：每次访问都在 Redis 里累加访问次数（HINCRBY）。
 *   访问次数达到 HOT_THRESHOLD 次 → 判定为热点商品 → 缓存 TTL 从 60s 延长到 300s，
 *   界面上打出 🔥 标记。这就是真实系统里「热点探测 + 缓存提升」的最小模型。
 *
 * 耗时为 process.hrtime 实测；DB 路径额外 sleep 12ms 模拟真实详情页的
 * 联表 + 序列化开销（本地 MySQL 查一行只要零点几毫秒，不模拟看不出差距）。
 */

const GOODS = [
  { id: 'G001', name: '限量款机械键盘', price: 599.0, stock: 100, warm: true },
  { id: 'G002', name: '降噪蓝牙耳机', price: 399.0, stock: 200, warm: true },
  { id: 'G003', name: '大容量移动电源', price: 129.0, stock: 300, warm: true },
  { id: 'G004', name: '316 不锈钢保温杯', price: 89.0, stock: 150, warm: false },
  { id: 'G005', name: '加厚防滑瑜伽垫', price: 69.0, stock: 80, warm: false },
  { id: 'G006', name: '护眼 LED 台灯', price: 159.0, stock: 60, warm: false },
];

const HOT_THRESHOLD = 3;   // 访问满 3 次判定为热点
const TTL_COLD = 60;       // 普通缓存 TTL（秒）
const TTL_HOT = 300;       // 热点缓存 TTL（秒），比普通缓存长得多
const QUERY_COST_MS = 12;  // 模拟联表 + 序列化开销，UI 上已标注
const ACCESS_KEY = 'hot:access'; // Redis HASH：商品 id → 累计访问次数

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const cacheKeyOf = (id) => `cache:hot:${id}`;

class HotCache {
  constructor(store, log) {
    this.store = store;
    this.log = log;
    this.goods = GOODS;
  }

  async init() {
    const pool = this.store.pool();
    await pool.query(`
      CREATE TABLE IF NOT EXISTS hot_goods (
        id    VARCHAR(32) PRIMARY KEY,
        name  VARCHAR(128) NOT NULL,
        price DECIMAL(10,2) NOT NULL DEFAULT 0,
        stock INT NOT NULL DEFAULT 0
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`);
    for (const g of GOODS) {
      await pool.query(
        `INSERT IGNORE INTO hot_goods (id, name, price, stock) VALUES (?, ?, ?, ?)`,
        [g.id, g.name, g.price, g.stock]);
    }
    // 清理旧版单商品实验留下的测试数据
    await pool.query(`DELETE FROM hot_goods WHERE id = 'HOT001'`);
  }

  /** 真实 MySQL 回源：SELECT 一行 + 模拟业务组装开销 */
  async _readFromDb(id) {
    const [[row]] = await this.store.pool().query(
      'SELECT id, name, price, stock FROM hot_goods WHERE id = ?', [id]);
    await sleep(QUERY_COST_MS);
    return row;
  }

  /**
   * 打开某个商品的详情页（固定 Cache-Aside）
   * @param {string} id
   * @returns {{id,source:'cache'|'miss',ms,row,access,hot,ttl}}
   */
  async queryOne(id) {
    const goodsId = String(id || '');
    const redis = this.store.redis;
    const key = cacheKeyOf(goodsId);
    const t0 = Number(process.hrtime.bigint());

    // 先累计访问次数（相当于真实系统里的热度统计埋点）
    const access = await redis.hincrby(ACCESS_KEY, goodsId, 1);
    const hot = access >= HOT_THRESHOLD;

    const cached = await redis.get(key);
    if (cached) {
      let ttl = await redis.ttl(key);
      // 已经是热点商品，顺手把 TTL 续到热点档位（热点数据活得更久）
      if (hot && ttl > 0 && ttl < TTL_HOT) {
        await redis.expire(key, TTL_HOT);
        ttl = TTL_HOT;
        this.log.push('CACHE', 'success',
          `🔥 ${goodsId} 累计访问 ${access} 次，已是热点商品 —— 缓存 TTL 续期到 ${TTL_HOT}s`);
      }
      const ms = (Number(process.hrtime.bigint()) - t0) / 1e6;
      this.log.push('CACHE', 'success',
        `打开 ${goodsId}：GET ${key} → HIT，直接返回（${ms.toFixed(2)}ms，没有碰 MySQL）`);
      return { id: goodsId, source: 'cache', ms, row: JSON.parse(cached), access, hot, ttl };
    }

    const row = await this._readFromDb(goodsId);
    const ttl = hot ? TTL_HOT : TTL_COLD;
    await redis.set(key, JSON.stringify(row), 'EX', ttl);
    const ms = (Number(process.hrtime.bigint()) - t0) / 1e6;

    if (hot) {
      this.log.push('CACHE', 'warn',
        `🔥 ${goodsId} 累计访问 ${access} 次 ≥ ${HOT_THRESHOLD}，判定为热点商品，写入 Redis 并设 TTL ${TTL_HOT}s（本次 ${ms.toFixed(2)}ms）`);
    } else {
      this.log.push('CACHE', 'warn',
        `打开 ${goodsId}：缓存 MISS，回源 MySQL 并写回 Redis（TTL ${ttl}s，本次 ${ms.toFixed(2)}ms）`);
    }
    return { id: goodsId, source: 'miss', row, ms, access, hot, ttl };
  }

  /** 重置：清空所有商品缓存与访问计数，恢复「3 个已预热热点 + 3 个仅在 MySQL」的初始状态 */
  async reset() {
    const redis = this.store.redis;
    const keys = await redis.keys('cache:hot:*');
    if (keys.length) await redis.del(keys);
    await redis.del(ACCESS_KEY);

    for (const g of this.goods) {
      await redis.hset(ACCESS_KEY, g.id, g.warm ? 5 : 0); // 预热商品历史访问量给 5 次，直接是热点
      if (!g.warm) continue;
      const row = await this._readFromDb(g.id);
      await redis.set(cacheKeyOf(g.id), JSON.stringify(row), 'EX', TTL_HOT);
    }
    this.log.push('CACHE', 'info',
      `已重置：${this.goods.filter((g) => g.warm).length} 个热点商品已预热进 Redis，其余 ${this.goods.filter((g) => !g.warm).length} 个商品只在 MySQL`);
    return this.state();
  }

  /** 全部商品状态：位置（Redis / MySQL）、TTL、累计访问、是否热点 */
  async state() {
    const redis = this.store.redis;
    const [rows] = await this.store.pool().query(
      'SELECT id, name, price, stock FROM hot_goods ORDER BY id');
    const accessMap = await redis.hgetall(ACCESS_KEY);

    const goods = [];
    for (const row of rows) {
      const key = cacheKeyOf(row.id);
      const raw = await redis.get(key);
      const ttl = raw ? await redis.ttl(key) : -2;
      const access = parseInt(accessMap[row.id] || '0', 10);
      goods.push({
        id: row.id,
        name: row.name,
        price: row.price,
        stock: row.stock,
        cached: !!raw,
        ttl: ttl < 0 ? null : ttl,
        access,
        hot: access >= HOT_THRESHOLD,
      });
    }
    return {
      goods,
      threshold: HOT_THRESHOLD,
      coldTtl: TTL_COLD,
      hotTtl: TTL_HOT,
      queryCostMs: QUERY_COST_MS,
    };
  }
}

module.exports = HotCache;
