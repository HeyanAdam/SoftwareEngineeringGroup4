'use strict';
/**
 * SeckillService —— 秒杀核心业务（读写一致性教学演示核心）
 *
 * 完整链路：
 *   用户请求 → ①限流(令牌桶) → ②Redis预扣库存(Lua原子脚本) → ③消息队列(削峰)
 *           → ④MySQL异步落库 → ⑤状态查询/对账（最终一致）
 *
 * 双模式对照实验（本系统的灵魂）：
 *   locked 模式 —— 库存「查-判-扣」三步在一个 Lua 原子脚本内完成（对应真实 Redis EVAL）
 *   unsafe 模式 —— 同样的三步被人为拆开并插入 await 网络间隙，复现超卖竞态
 */
const { sleep } = require('./miniredis');

/** 生产环境真实使用的 Lua 脚本（前端「原理与代码」板块同步展示） */
const LUA_SECKILL = `-- seckill.lua：库存预扣 + 防重复，整体原子执行
-- KEYS[1]=库存key  KEYS[2]=已购名单key  ARGV[1]=用户ID
local stock = tonumber(redis.call('GET', KEYS[1]))
if stock == nil or stock <= 0 then
  return -1                                  -- 已售罄
end
if redis.call('SISMEMBER', KEYS[2], ARGV[1]) == 1 then
  return -2                                  -- 重复购买
end
redis.call('DECR', KEYS[1])                  -- 扣减库存
redis.call('SADD', KEYS[2], ARGV[1])         -- 记入已购名单
return 1                                     -- 预扣成功`;

class SeckillService {
  constructor(redis, mysql, mq, log) {
    this.redis = redis;
    this.db = mysql;
    this.mq = mq;
    this.log = log;

    this.goodsId = 'P001';
    this.goodsName = 'Air Run Pro 限量球鞋';
    this.price = 129;

    this.mode = 'locked';          // locked | unsafe
    this.initialStock = 10;
    this.userSeq = 1000;
    this.runningStress = false;

    // 简易令牌桶：容量 50，每秒补充 25 —— 演示网关限流
    this.tokenCapacity = 50;
    this.tokens = 50;

    this.metrics = {
      requests: 0, limited: 0,
      success: 0, failSoldOut: 0, failDuplicate: 0, oversell: 0,
      lastStress: null,
    };

    this.stockKey = `stock:${this.goodsId}`;
    this.boughtKey = `bought:${this.goodsId}`;
  }

  /* ---------------- 库存预热 ---------------- */

  /**
   * 重置并预热：先写 MySQL（磁盘层），再把库存「预热」进 Redis。
   * 对应生产：活动开始前运营后台把 DB 库存刷进 Redis。
   */
  async reset(stock) {
    this.initialStock = stock;
    this.redis.flushdb();
    await this.db.initGoods(this.goodsId, this.goodsName, this.price, stock);
    this.redis.set(this.stockKey, stock);            // 预热：DB 库存 → Redis
    this.redis.expire(this.stockKey, 86400);
    this.db.orders.clear();
    this.mq.clear();
    this.mq.paused = false;
    Object.assign(this.metrics, {
      requests: 0, limited: 0, success: 0,
      failSoldOut: 0, failDuplicate: 0, oversell: 0, lastStress: null,
    });
    this.tokens = this.tokenCapacity;
    this.log.push('CHECK', 'info', `库存预热完成：MySQL stock=${stock} → Redis key「${this.stockKey}」=${stock}`);
    return { stock };
  }

  nextUserId() { return 'U' + (++this.userSeq); }

  /* ---------------- 秒杀请求处理 ---------------- */

  async handleRequest(userId) {
    this.metrics.requests++;
    const uid = userId || this.nextUserId();

    // ① 网关限流（令牌桶）： protects 下游 Redis/MySQL
    if (this.tokens <= 0) {
      this.metrics.limited++;
      this.log.push('LIMIT', 'warn', `用户 ${uid} 被限流拦截（令牌桶已空，请求直接拒绝，不落到 Redis）`);
      return { code: 429, msg: '系统繁忙，请稍后再试（限流）', userId: uid };
    }
    this.tokens--;

    // ② Redis 预扣库存
    let r;
    if (this.mode === 'locked') {
      r = this._luaSeckill(uid);
    } else {
      r = await this._unsafeSeckill(uid);
    }

    // 失败：售罄 / 重复
    if (r.code !== 0) {
      if (r.code === 1001) this.metrics.failSoldOut++;
      if (r.code === 1002) this.metrics.failDuplicate++;
      this.log.push('REDIS', r.code === 1001 ? 'warn' : 'warn',
        `用户 ${uid} 预扣失败：${r.msg}（Redis 剩余库存 ${this.redis.get(this.stockKey)}）`);
      return { ...r, userId: uid };
    }

    // ③ 预扣成功 → 订单投递消息队列（异步落库），立即返回「抢购成功」
    const orderId = 'O' + Date.now().toString(36).toUpperCase() + Math.floor(Math.random() * 1000);
    const order = {
      orderId, userId: uid, goodsId: this.goodsId,
      status: '排队中', createdAt: Date.now(), paidAt: null,
    };
    this.mq.publish(order);
    this.metrics.success++;
    this.log.push('MQ', 'success',
      `用户 ${uid} 预扣成功，订单 ${orderId} 投递消息队列（当前积压 ${this.mq.size()} 条），前端已返回「抢购成功」`);

    return { code: 0, msg: '抢购成功，订单排队中', userId: uid, orderId };
  }

  /**
   * 【原子模式】对应真实环境的 EVAL seckill.lua：
   * 查库存 → 判重复 → 扣减 → 记名单，四步在一个原子脚本内完成。
   * MiniRedis 单线程同步执行，期间不可能插入其它请求 → 不可能超卖。
   */
  _luaSeckill(userId) {
    return this.redis.evalAtomic(() => {
      const stock = parseInt(this.redis.get(this.stockKey), 10);
      if (isNaN(stock) || stock <= 0) {
        return { code: 1001, msg: '已售罄' };
      }
      if (this.redis.sismember(this.boughtKey, userId)) {
        return { code: 1002, msg: '请勿重复抢购' };
      }
      this.redis.decrBy(this.stockKey, 1);
      this.redis.sadd(this.boughtKey, userId);
      return { code: 0, msg: '预扣成功' };
    }, 'seckill.lua');
  }

  /**
   * 【无锁对照模式】复现「先查后减」非原子写法的超卖竞态：
   * 第①步查库存与第②步减库存之间插入 await（模拟网络往返/业务处理），
   * 并发请求会在间隙中同时通过「库存>0」判断，随后一起扣减 → 超卖。
   */
  async _unsafeSeckill(userId) {
    const stock = parseInt(this.redis.get(this.stockKey), 10);  // 第①步：查库存
    await sleep(6);   // ★ 竞态窗口：期间其它请求也能读到同一库存值
    if (isNaN(stock) || stock <= 0) {
      return { code: 1001, msg: '已售罄' };
    }
    if (this.redis.sismember(this.boughtKey, userId)) {
      return { code: 1002, msg: '请勿重复抢购' };
    }
    await sleep(4);   // 继续放大竞态窗口
    const left = this.redis.decrBy(this.stockKey, 1);           // 第②步：减库存（此时可能已被扣穿）
    this.redis.sadd(this.boughtKey, userId);
    if (left < 0) {
      this.metrics.oversell++;
      this.log.push('LUA', 'error',
        `超卖告警！用户 ${userId} 扣减后库存=${left}（无锁模式：查-减两步间存在竞态窗口，多个请求同时通过了库存校验）`);
    }
    return { code: 0, msg: '预扣成功（无锁模式）' };
  }

  /* ---------------- 并发压测 ---------------- */

  /**
   * 模拟 count 个用户同时抢购：请求带 1ms 级到达间隔，全部并发执行。
   * locked 模式预期：成功数 == 初始库存，一件不超卖；
   * unsafe 模式预期：成功数远大于初始库存，直观看到超卖。
   */
  async stress(count = 100) {
    if (this.runningStress) return { code: 409, msg: '压测进行中' };
    this.runningStress = true;
    const t0 = Date.now();
    this.log.push('CHECK', 'info', `===== 压测开始：${count} 个用户并发抢购（模式：${this.mode === 'locked' ? 'Lua原子' : '无锁对照'}，库存 ${this.redis.get(this.stockKey)}）=====`);

    const tasks = [];
    for (let i = 0; i < count; i++) {
      tasks.push((async (idx) => {
        if (idx > 0) await sleep(1);           // 模拟用户陆续到达
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
      redisStock: parseInt(this.redis.get(this.stockKey) || '0', 10),
      boughtCount: this.redis.scard(this.boughtKey),
      elapsedMs: Date.now() - t0,
      mode: this.mode,
    };
    this.metrics.lastStress = summary;

    if (summary.mode === 'locked') {
      this.log.push('CHECK', 'success',
        `===== 压测结束：成功 ${summary.success} 件（= 初始库存，零超卖），售罄拦截 ${summary.soldOut}，Redis 剩余库存 ${summary.redisStock}，耗时 ${summary.elapsedMs}ms =====`);
    } else {
      this.log.push('CHECK', 'error',
        `===== 压测结束：成功 ${summary.success} 件 > 库存上限，超卖 ${summary.success - Math.max(0, this.initialStock)} 件！Redis 库存被扣至 ${summary.redisStock}（负数）====`);
    }
    this.runningStress = false;
    return { code: 0, summary };
  }

  /* ---------------- 消费者：MQ → MySQL 落库 ---------------- */

  start() {
    this.mq.start(async (order) => {
      // ④ 订单落库（模拟磁盘事务写入，60~150ms）
      await this.db.insertOrder({ ...order });
      await this.db.updateOrderStatus(order.orderId, '已落库');
      // ⑤ 扣减数据库库存（生产中应带乐观锁：WHERE stock > 0）
      const { stock } = await this.db.deductStock(order.goodsId);
      if (stock < 0) {
        this.log.push('MYSQL', 'error', `订单 ${order.orderId} 落库，但 DB 库存已被扣成 ${stock}（超卖证据：无锁模式下 Redis 放行了过多请求）`);
      } else {
        this.log.push('MYSQL', 'info', `订单 ${order.orderId} 已落库（INSERT orders + UPDATE goods），DB 剩余库存 ${stock}`);
      }
    });

    // 令牌桶按速率补充
    setInterval(() => {
      this.tokens = Math.min(this.tokenCapacity, this.tokens + 25);
    }, 1000);
  }

  /* ---------------- 状态快照 ---------------- */

  overview() {
    const redisStock = parseInt(this.redis.get(this.stockKey) || '0', 10);
    const bought = this.redis.scard(this.boughtKey);
    const goods = this.db.goods.get(this.goodsId);
    const rec = this.db.reconcile(this.goodsId, bought);
    return {
      engine: { type: 'MiniRedis', desc: '内置单线程内存库模拟器（与 Redis 命令级对齐）', uptime: this.redis.uptime(), ops: this.redis.stats.ops },
      mode: this.mode,
      goods: { id: this.goodsId, name: this.goodsName, price: this.price },
      redis: { stock: redisStock, bought, keys: this.redis.keys('stock:*').length + this.redis.keys('bought:*').length },
      db: { stock: goods ? goods.stock : null, orders: rec.dbOrders, avgWriteMs: this.db.stats.writes ? Math.round(this.db.stats.totalWriteMs / this.db.stats.writes) : 0 },
      mq: { size: this.mq.size(), published: this.mq.stats.published, consumed: this.mq.stats.consumed, paused: this.mq.paused },
      metrics: this.metrics,
      tokens: this.tokens,
      reconcile: rec,
      luaScript: LUA_SECKILL,
    };
  }
}

module.exports = { SeckillService, LUA_SECKILL };
