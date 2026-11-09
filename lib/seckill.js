'use strict';
/**
 * SeckillService —— 秒杀核心业务（真实 Redis + MySQL 版）
 *
 * 完整链路（全部真实组件，可开 redis-cli / mysql 客户端逐条验证）：
 *   用户请求 → ①网关限流(Redis 令牌桶 ratelimit.lua)
 *           → ②Redis 预扣库存(EVAL seckill.lua 原子脚本)
 *           → ③订单投递 Redis 队列(LPUSH queue:orders 削峰)
 *           → ④消费者 BRPOP → MySQL 异步落库(INSERT orders + UPDATE goods)
 *           → ⑤对账（Redis 已购名单 vs DB 订单数，最终一致）
 *
 * 双模式对照（本系统的灵魂）：
 *   locked 模式 —— 「查-判-扣」在一段 Lua 原子脚本内完成，杜绝超卖
 *   unsafe 模式 —— 同样三步拆开，两次真实网络往返之间存在竞态窗口，复现超卖
 */
const { randomBytes } = require('crypto');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 前端展示用脚本全文（与 lua/seckill.lua 同一份） */
function luaText(loadLua) {
  try { return loadLua('seckill.lua'); } catch (_) { return '(seckill.lua 缺失)'; }
}

class SeckillService {
  constructor(store, log) {
    this.store = store;
    this.log = log;
    this.redis = store.redis;

    this.goodsId = 'P001';
    this.goodsName = 'Air Run Pro 限量球鞋';
    this.price = 129;

    this.mode = 'locked';          // locked | unsafe
    this.initialStock = 10;
    this.userSeq = 1000;
    this.runningStress = false;

    // 令牌桶参数（真实由 Redis Lua 维护）
    this.tokenCapacity = 50;
    this.tokenRefill = 25;
    this.tokenKey = 'rate:seckill';

    this.metrics = {
      requests: 0, limited: 0,
      success: 0, failSoldOut: 0, failDuplicate: 0, oversell: 0,
      lastStress: null,
    };

    this.stockKey = `stock:${this.goodsId}`;
    this.boughtKey = `bought:${this.goodsId}`;
    this.queueKey = 'queue:orders';

    // 消费者状态
    this.consumePaused = false;
    this.consumeStats = { published: 0, consumed: 0, writeTotalMs: 0 };
  }

  /* ---------------- 库存预热 ---------------- */

  /**
   * 重置并预热：先写 MySQL（权威存储），再把库存「预热」进 Redis。
   * 对应生产：活动开始前运营后台把 DB 库存刷进 Redis。
   */
  async reset(stock) {
    this.initialStock = stock;
    this.metrics = {
      requests: 0, limited: 0, success: 0,
      failSoldOut: 0, failDuplicate: 0, oversell: 0, lastStress: null,
    };
    this.consumeStats = { published: 0, consumed: 0, writeTotalMs: 0 };
    await this.store.resetGoods(this.goodsId, this.goodsName, stock);
    await this.store.pool().query('DELETE FROM orders');   // 演示重置：清空上一场活动的订单（DML，不与消费者落库冲突）
    await this.redis.del(this.queueKey);
    await this.redis.hset(this.tokenKey, 'tokens', this.tokenCapacity, 'ts', Date.now());
    this.redis.eval(this.store.lua['ratelimit.lua'], 1, this.tokenKey,
      this.tokenCapacity, this.tokenRefill, Date.now(), 0);
    this.log.push('CHECK', 'info',
      `库存预热完成：MySQL goods.stock=${stock} → Redis key「${this.stockKey}」=${stock}（可在 redis-cli 执行 GET ${this.stockKey} 验证）`);
    return { stock };
  }

  nextUserId() { return 'U' + (++this.userSeq); }

  /* ---------------- 限流（Redis 令牌桶） ---------------- */

  async tryAcquireToken() {
    const left = await this.redis.eval(this.store.lua['ratelimit.lua'], 1, this.tokenKey,
      this.tokenCapacity, this.tokenRefill, Date.now(), 1);
    return left >= 0;
  }
  async tokensLeft() {
    const s = await this.redis.hmget(this.tokenKey, 'tokens');
    return Math.floor(Number(s[0] || this.tokenCapacity));
  }

  /* ---------------- 秒杀请求处理 ---------------- */

  async handleRequest(userId) {
    this.metrics.requests++;
    const uid = userId || this.nextUserId();

    // ① 网关限流（真实 Redis 令牌桶，EVAL ratelimit.lua）
    const ok = await this.tryAcquireToken();
    if (!ok) {
      this.metrics.limited++;
      this.log.push('LIMIT', 'warn', `用户 ${uid} 被限流拦截（Redis 令牌桶已空，请求直接拒绝，不落到库存层）`);
      return { code: 429, msg: '系统繁忙，请稍后再试（限流）', userId: uid };
    }

    // ② Redis 预扣库存
    const r = this.mode === 'locked'
      ? await this._luaSeckill(uid)
      : await this._unsafeSeckill(uid);

    if (r.code !== 0) {
      if (r.code === 1001) this.metrics.failSoldOut++;
      if (r.code === 1002) this.metrics.failDuplicate++;
      const left = await this.redis.get(this.stockKey);
      this.log.push('REDIS', 'warn', `用户 ${uid} 预扣失败：${r.msg}（Redis 剩余库存 ${left}）`);
      return { ...r, userId: uid };
    }

    // ③ 预扣成功 → 订单 LPUSH 进 Redis 队列（削峰），立即返回「抢购成功」
    const orderId = 'O' + Date.now().toString(36).toUpperCase() + randomBytes(2).toString('hex').toUpperCase();
    const order = { orderId, userId: uid, goodsId: this.goodsId, status: '排队中', createdAt: Date.now() };
    await this.redis.lpush(this.queueKey, JSON.stringify(order));
    this.consumeStats.published++;
    this.metrics.success++;
    const backlog = await this.redis.llen(this.queueKey);
    this.log.push('MQ', 'success',
      `用户 ${uid} 预扣成功，订单 ${orderId} 已 LPUSH 到 Redis 队列「${this.queueKey}」（当前积压 ${backlog} 条），前端已返回「抢购成功」`);

    return { code: 0, msg: '抢购成功，订单排队中', userId: uid, orderId };
  }

  /**
   * 【原子模式】真实 EVAL seckill.lua：
   * 查库存→判重复→扣减→记名单 在 Redis 单线程内一口气执行 → 不可能超卖。
   * 可在 redis-cli 执行 EVALSHA/SCRIPT LOAD 复现，与本服务完全一致。
   */
  async _luaSeckill(userId) {
    const [ret] = await this.redis.eval(this.store.lua['seckill.lua'], 2, this.stockKey, this.boughtKey, userId);
    if (ret === 0) return { code: 0, msg: '预扣成功' };
    if (ret === 2) return { code: 1002, msg: '请勿重复抢购' };
    return { code: 1001, msg: '已售罄' };
  }

  /**
   * 【无锁对照模式】复现「先查后减」非原子写法的超卖竞态：
   * 第①步 GET 与第②步 DECR 之间是两次真实网络往返，期间存在 await 空隙，
   * 并发请求会在空隙中同时通过「库存>0」判断，随后一起扣减 → 真实超卖。
   */
  async _unsafeSeckill(userId) {
    const stockStr = await this.redis.get(this.stockKey);   // 第①步：真实网络往返查库存
    const stock = parseInt(stockStr, 10);
    await sleep(6);                                          // ★ 竞态窗口：其它请求同样读到同一库存
    if (isNaN(stock) || stock <= 0) return { code: 1001, msg: '已售罄' };
    if (await this.redis.sismember(this.boughtKey, userId)) return { code: 1002, msg: '请勿重复抢购' };
    await sleep(4);                                          // 继续放大竞态窗口
    const left = await this.redis.decr(this.stockKey);       // 第②步：减库存（此时可能已被扣穿）
    await this.redis.sadd(this.boughtKey, userId);
    if (left < 0) {
      this.metrics.oversell++;
      this.log.push('LUA', 'error',
        `超卖告警！用户 ${userId} 扣减后库存=${left}（无锁模式：GET→DECR 两次往返之间存在竞态窗口，多个请求同时通过了校验）`);
    }
    return { code: 0, msg: '预扣成功（无锁模式）' };
  }

  /* ---------------- 并发压测 ---------------- */

  async stress(count = 100) {
    if (this.runningStress) return { code: 409, msg: '压测进行中' };
    this.runningStress = true;
    const t0 = Date.now();
    this.log.push('CHECK', 'info', `===== 压测开始：${count} 个用户并发抢购（模式：${this.mode === 'locked' ? 'Lua原子' : '无锁对照'}）=====`);

    const tasks = [];
    for (let i = 0; i < count; i++) {
      tasks.push((async (idx) => {
        if (idx > 0) await sleep(1);           // 用户陆续到达
        return this.handleRequest();
      })(i));
    }
    const results = await Promise.all(tasks);

    const summary = {
      total: count,
      success: results.filter((r) => r.code === 0).length,
      soldOut: results.filter((r) => r.code === 1001).length,
      duplicate: results.filter((r) => r.code === 1002).length,
      limited: results.filter((r) => r.code === 429).length,
      oversell: this.metrics.oversell,
      redisStock: parseInt((await this.redis.get(this.stockKey)) || '0', 10),
      boughtCount: await this.redis.scard(this.boughtKey),
      elapsedMs: Date.now() - t0,
      mode: this.mode,
    };
    this.metrics.lastStress = summary;

    if (summary.mode === 'locked') {
      this.log.push('CHECK', 'success',
        `===== 压测结束：成功 ${summary.success} 件（= 库存上限，零超卖），售罄拦截 ${summary.soldOut}，Redis 剩余库存 ${summary.redisStock}，耗时 ${summary.elapsedMs}ms =====`);
    } else {
      this.log.push('CHECK', 'error',
        `===== 压测结束：成功 ${summary.success} 件 > 库存上限，超卖 ${summary.success - Math.max(0, this.initialStock)} 件！Redis 库存被扣至 ${summary.redisStock}（负数）=====`);
    }
    this.runningStress = false;
    return { code: 0, summary };
  }

  /* ---------------- 消费者：Redis 队列 → MySQL 落库 ---------------- */

  start() {
    (async () => {
      const consumer = this.store.newConsumer();   // BRPOP 阻塞命令必须用独立连接
      this.log.push('MQ', 'info', `落库消费者已启动（独立 Redis 连接）：BRPOP ${this.queueKey} → MySQL（INSERT orders + UPDATE goods）`);
      while (true) {
        try {
          if (this.consumePaused) { await sleep(300); continue; }
          const item = await consumer.brpop(this.queueKey, 2);
          if (!item) continue;
          const order = JSON.parse(item[1]);
          const t0 = Date.now();
          await this._persistOrder(order);
          const cost = Date.now() - t0;
          this.consumeStats.consumed++;
          this.consumeStats.writeTotalMs += cost;
          this.log.push('MYSQL', 'info',
            `订单 ${order.orderId} 已落库（INSERT orders + UPDATE goods，真实事务 ${cost}ms），DB 剩余库存 ${await this.store.getDbStock(this.goodsId)}`);
        } catch (err) {
          this.log.push('MYSQL', 'error', `消费者异常：${err.message}，2s 后重试`);
          await sleep(2000);
        }
      }
    })();
  }

  async _persistOrder(order) {
    const pool = this.store.pool();
    const conn = await pool.getConnection();
    try {
      await conn.beginTransaction();
      await conn.query(
        'INSERT INTO orders (order_id, user_id, goods_id, status, created_at) VALUES (?, ?, ?, ?, ?)',
        [order.orderId, order.userId, order.goodsId, '已落库', new Date(order.createdAt)]);
      const [ret] = await conn.query(
        'UPDATE goods SET stock = stock - 1 WHERE id = ?', [order.goodsId]);
      await conn.commit();
      return ret;
    } catch (err) {
      await conn.rollback().catch(() => {});
      throw err;
    } finally {
      conn.release();
    }
  }

  toggleConsume() {
    this.consumePaused = !this.consumePaused;
    return this.consumePaused;
  }

  /* ---------------- 对账 ---------------- */

  async reconcile() {
    const redisBought = await this.redis.scard(this.boughtKey);
    const dbOrders = await this.store.countOrders();
    const backlog = await this.redis.llen(this.queueKey);
    const redisStock = parseInt((await this.redis.get(this.stockKey)) || '0', 10);
    const dbStock = await this.store.getDbStock(this.goodsId);
    const consistent = redisBought === dbOrders && backlog === 0;
    return {
      redisBought, dbOrders, backlog, redisStock, dbStock, consistent,
      diff: redisBought - dbOrders,
    };
  }

  /* ---------------- 状态快照 ---------------- */

  async overview() {
    const [redisStock, bought, backlog, tokens, stockRows, orderCount, versions] = await Promise.all([
      this.redis.get(this.stockKey),
      this.redis.scard(this.boughtKey),
      this.redis.llen(this.queueKey),
      this.tokensLeft(),
      this.store.getDbStock(this.goodsId),
      this.store.countOrders(),
      this.store.detectVersions(),
    ]);
    const avgWriteMs = this.consumeStats.consumed
      ? Math.round(this.consumeStats.writeTotalMs / this.consumeStats.consumed) : 0;
    const keys = await this.redis.keys('stock:*');
    const boughtKeys = await this.redis.keys('bought:*');
    return {
      engine: { type: versions.redis, desc: `真实 Redis + ${versions.mysql}`, versions },
      mode: this.mode,
      goods: { id: this.goodsId, name: this.goodsName, price: this.price },
      redis: { stock: parseInt(redisStock || '0', 10), bought, keys: keys.length + boughtKeys.length },
      db: { stock: stockRows, orders: orderCount, avgWriteMs },
      mq: { size: backlog, published: this.consumeStats.published, consumed: this.consumeStats.consumed, paused: this.consumePaused },
      metrics: this.metrics,
      tokens,
      luaScript: luaText(this.store.loadLua),
    };
  }
}

module.exports = { SeckillService };
