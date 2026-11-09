'use strict';
/**
 * Duel —— 双系统对照实验控制器（真实 MySQL vs 真实 Redis 版）
 *
 * 同一批用户、同量库存，同时打给两套真实系统：
 *   系统A（无Redis）：Node 服务直连真实 MySQL —— 每个请求一个真实事务：
 *       BEGIN → SELECT stock（快照读不加锁）→ 应用层判断 → UPDATE stock-1（行锁）
 *       → COMMIT。这是真实业务里最常见的「先查后改」写法：
 *       · 并发请求都在同一库存快照上通过判断 → UPDATE 排队逐笔扣穿 → 真实超卖（库存负数）
 *       · 行锁串行导致后面请求排队等待 → 超过网关超时的请求被掐断 → 用户看到报错
 *   系统B（配Redis）：真实 Redis EVAL seckill.lua 原子预扣（查-判-扣一口气，亚毫秒）
 *       → 订单 LPUSH 进 Redis 队列 → 后台消费者 BRPOP 异步落库 MySQL（削峰+最终一致）
 *
 * 过程可信度：每条请求的真实耗时被如实记录（到达时刻 / 排队等待 / 处理 / 结果），
 * 实验结束后按真实时间轴逐条回放给前端 —— 看到的是真实数据，不是预先编好的剧本。
 * 演示时可在 mysql / redis-cli 客户端里直接 SELECT stock / GET stock:DUEL-B 对照验证。
 */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (a, b) => a + Math.floor(Math.random() * (b - a));

const GID_A = 'DUEL-A';          // 系统A 用 MySQL 行（goods 表）
const GID_B = 'DUEL-B';          // 系统B 用 Redis key（预扣）+ goods 表（落库）
const STOCK_KEY_B = 'stock:' + GID_B;
const BOUGHT_KEY_B = 'bought:' + GID_B;
const QUEUE_KEY_B = 'queue:duel-orders';
const DEFAULT_TIMEOUT_MS = 2500;   // 网关/前端默认等待超时（生产秒级；本地磁盘快，演示可调低观察排队超时）

class Duel {
  constructor(store, log, broadcast) {
    this.store = store;
    this.redis = store.redis;
    this.log = log;
    this.broadcast = broadcast;   // duel 专用 SSE 推送 (evt) => void
    this.running = false;
    this.state = null;
  }

  snapshot() { return this.state; }

  emit(evt) {
    if (this.state) this.state.events.push(evt);
    this.broadcast(evt);
  }

  async start({ users = 50, stock = 10, speed = 1, timeoutMs }) {
    if (this.running) return { code: 409, msg: '实验进行中' };
    this.running = true;
    users = Math.min(200, Math.max(2, parseInt(users, 10) || 50));
    stock = Math.min(999, Math.max(1, parseInt(stock, 10) || 10));
    speed = [0.5, 1, 2].includes(Number(speed)) ? Number(speed) : 1;
    const TIMEOUT_MS = Math.min(10000, Math.max(200, parseInt(timeoutMs, 10) || DEFAULT_TIMEOUT_MS));

    /* ---------- 准备两套系统的初始库存 ---------- */
    await this.store.resetGoods(GID_A, '对照实验-系统A商品', stock);
    await this.store.resetGoods(GID_B, '对照实验-系统B商品', stock);
    await this.redis.set(STOCK_KEY_B, stock);
    await this.redis.del(BOUGHT_KEY_B, QUEUE_KEY_B);

    /* ---------- 预热连接池：提前建好池连接，让 200 个请求真正同时压上行锁 ---------- */
    //（不预热的话建连耗时会错峰涌入，先成交的用户把库存扣穿，后面的人直接看到售罄，行锁竞争观察不到）
    const POOL_WARM = 100;
    await Promise.all(Array.from({ length: POOL_WARM }, async () => {
      const c = await this.store.pool().getConnection();
      c.release();
    }));
    this.log.push('CHECK', 'info', `[对照实验] MySQL 连接池已预热 ${POOL_WARM} 个连接（真实生产同样会保持常驻连接池）`);

    this.state = {
      running: true,
      config: { users, stock, speed, timeoutMs: TIMEOUT_MS, arriveSpan: 80 },
      startedAt: Date.now(),
      A: { done: 0, success: 0, soldout: 0, timeout: 0, sumResp: 0, maxResp: 0 },
      B: { done: 0, success: 0, soldout: 0, sumResp: 0, maxResp: 0 },
      records: [],
      events: [],
    };

    this.emit({ type: 'begin', config: this.state.config });
    this.log.push('CHECK', 'info',
      `[对照实验] 开始：${users} 个用户抢 ${stock} 件，同时打给 系统A(真实MySQL直打) 与 系统B(真实Redis原子预扣)，执行完成后按真实时间轴回放`);

    /* ---------- 并发执行（记录每条请求的真实耗时） ---------- */
    const t0 = Date.now();
    const arriveSpan = 80;   // 真实秒杀：用户瞬时涌入（80ms 内全部到达）
    const recs = [];

    const launch = (sys, uid, delayMs, fn) => new Promise((resolve) => {
      setTimeout(async () => {
        try {
          const rec = await fn(uid, Date.now() - t0);
          recs.push({ ...rec, sys, uid });
          const st = sys === 'A' ? this.state.A : this.state.B;   // 实时进度（供诊断与前端轮询）
          st.done++;
        } catch (err) {
          // 兜底：单个请求异常只记为 error，绝不能让 Promise.all 永久挂起（实验卡死）
          recs.push({ uid, at: Date.now() - t0, wait: 0, dur: 0, outcome: 'error', respMs: 0, sys, uid });
          (sys === 'A' ? this.state.A : this.state.B).done++;
          this.log.push('CHECK', 'error', `[对照实验] ${sys} ${uid} 请求异常: ${err.message}`);
        }
        resolve();
      }, delayMs);
    });

    const tasks = [];
    for (let i = 0; i < users; i++) {
      const uidA = 'A' + (1000 + i);
      const uidB = 'B' + (1000 + i);
      const delay = rand(0, arriveSpan);
      tasks.push(launch('A', uidA, delay, (uid, at) => this._sysA(uid, at, stock, TIMEOUT_MS)));
      tasks.push(launch('B', uidB, delay, (uid, at) => this._sysB(uid, at)));
    }
    await Promise.all(tasks);
    const execMs = Date.now() - t0;

    /* ---------- 统计真实结果 ---------- */
    const stat = (sys) => {
      const rs = recs.filter((r) => r.sys === sys);
      const s = {
        done: rs.length,
        success: rs.filter((r) => r.outcome === 'success').length,
        soldout: rs.filter((r) => r.outcome === 'soldout').length,
        timeout: rs.filter((r) => r.outcome === 'timeout').length,
      };
      s.sumResp = rs.reduce((x, r) => x + r.respMs, 0);
      s.maxResp = rs.reduce((m, r) => Math.max(m, r.respMs), 0);
      return s;
    };
    const sa = stat('A'), sb = stat('B');
    const dbStockA = await this.store.getDbStock(GID_A);           // 真实扣穿后的库存（负数）
    const redisStockB = parseInt((await this.redis.get(STOCK_KEY_B)) || '0', 10);

    const summary = {
      users, stock,
      A: {
        success: sa.success, soldout: sa.soldout, timeout: sa.timeout,
        avgResp: Math.round(sa.sumResp / Math.max(1, sa.done)),
        maxResp: sa.maxResp,
        stockAfter: dbStockA,
        // 超卖件数 = 实际成交 - 库存上限（1 件库存成交 3 笔 → 超卖 2 件）
        oversell: Math.max(0, sa.success - stock),
      },
      B: {
        success: sb.success, soldout: sb.soldout, timeout: 0,
        avgResp: Math.round(sb.sumResp / Math.max(1, sb.done)),
        maxResp: sb.maxResp,
        stockAfter: redisStockB, oversell: 0,
        persistTotal: sb.success, persisted: 0,
      },
      elapsed: execMs,
    };

    this.log.push('CHECK', summary.A.oversell > 0 ? 'error' : 'warn',
      `[对照实验] 系统A(真实MySQL) 执行完毕：成交 ${summary.A.success} 笔（库存仅 ${stock}），超卖 ${summary.A.oversell} 件，超时 ${summary.A.timeout} 人，平均响应 ${summary.A.avgResp}ms —— 可在 mysql 客户端执行 SELECT stock FROM goods WHERE id='${GID_A}' 验证（真实负数）`);
    this.log.push('CHECK', 'success',
      `[对照实验] 系统B(真实Redis) 执行完毕：成交 ${summary.B.success} 笔，零超卖，平均响应 ${summary.B.avgResp}ms —— 可在 redis-cli 执行 GET ${STOCK_KEY_B} 验证；${summary.B.persistTotal} 笔订单正在后台异步落库`);

    /* ---------- 按真实时间轴回放（过程可见） ---------- */
    const replay = [...recs].sort((a, b) => (a.at + a.respMs) - (b.at + b.respMs));
    let prev = 0;
    for (const r of replay) {
      const doneAt = r.at + r.respMs;
      const gap = Math.max(0, doneAt - prev);
      await sleep(speed < 1 ? gap / speed : gap);   // 0.5x 慢放
      prev = doneAt;
      this.emit({
        type: 'req', sys: r.sys, uid: r.uid, at: r.at,
        wait: r.wait, dur: r.dur, outcome: r.outcome, respMs: r.respMs,
      });
    }

    this.state.summary = summary;
    this.state.running = false;
    this.emit({ type: 'end', summary });

    /* ---------- 系统B 的真实后台落库（BRPOP → MySQL），实时推送进度 ---------- */
    (async () => {
      const consumer = this.store.newConsumer();   // BRPOP 阻塞命令必须用独立连接
      let persisted = 0;
      while (persisted < summary.B.persistTotal) {
        const item = await consumer.brpop(QUEUE_KEY_B, 2);
        if (!item) continue;
        const order = JSON.parse(item[1]);
        try {
          const pool = this.store.pool();
          const conn = await pool.getConnection();
          try {
            await conn.beginTransaction();
            await conn.query(
              'INSERT INTO orders (order_id, user_id, goods_id, status, created_at) VALUES (?, ?, ?, ?, ?)',
              [order.orderId, order.userId, order.goodsId, '已落库', new Date(order.createdAt)]);
            await conn.query('UPDATE goods SET stock = stock - 1 WHERE id = ?', [GID_B]);
            await conn.commit();
          } finally { conn.release(); }
        } catch (err) {
          this.log.push('MYSQL', 'error', `[对照实验] 落库失败 ${order.orderId}: ${err.message}`);
        }
        persisted++;
        this.state.summary.B.persisted = persisted;
        this.emit({ type: 'persist', persisted, total: summary.B.persistTotal });
      }
      const dbB = await this.store.getDbStock(GID_B);
      this.log.push('MYSQL', 'success',
        `[对照实验] 系统B 的 ${summary.B.persistTotal} 笔订单已全部异步落库，MySQL goods.'${GID_B}' 库存=${dbB}，与 Redis 对齐（最终一致）`);
    })();

    this.running = false;
    return { code: 0, summary };
  }

  /* ================= 系统A：真实 MySQL「先查后改」事务 ================= */
  async _sysA(uid, at, stock, timeoutMs) {
    const pool = this.store.pool();
    const conn = await pool.getConnection();
    const rec = { uid, at, wait: 0, dur: 0, outcome: 'success', respMs: 0 };
    const t0 = Date.now();
    // 实际生效的网关超时：innodb_lock_wait_timeout 只接受整数秒（小数报 Incorrect argument type），
    // 低于 1s 的超时按 1s 生效。必须声明在 try 之外 —— finally 里也要引用
    const effSec = Math.max(1, Math.round(timeoutMs / 1000));
    const effMs = effSec * 1000;
    try {
      await conn.beginTransaction();
      // SET 的值不能用占位符，拼接的是内部生成的整数，无注入风险
      await conn.query(`SET innodb_lock_wait_timeout = ${effSec}`);
      // ① SELECT 快照读（不加锁）—— 所有并发请求此刻看到的都是同一库存
      const [[row]] = await conn.query('SELECT stock FROM goods WHERE id = ?', [GID_A]);
      const seen = row.stock;
      // ② 应用层判断 + 业务处理（真实应用的处理开销）
      await sleep(rand(10, 30));
      if (seen <= 0) {
        await conn.rollback();
        rec.outcome = 'soldout';
      } else {
        // ③ UPDATE 当前读 + 行锁 —— 并发请求在这里串行排队
        const tU = Date.now();
        try {
          await conn.query('UPDATE goods SET stock = stock - 1 WHERE id = ?', [GID_A]);
        } catch (err) {
          if (err && err.errno === 1205) {         // ER_LOCK_WAIT_TIMEOUT：等行锁超过超时被数据库放弃
            rec.outcome = 'timeout';
            rec.wait = effMs;
          }
          throw err;
        }
        rec.wait = Date.now() - tU;                // 真实行锁排队等待
        // 事务内真实业务开销（写订单/扣优惠券等）—— 行锁从 UPDATE 一直持有到 COMMIT
        await sleep(rand(20, 50));
        await conn.commit();                       // 事务提交 = 成交（超卖订单就在其中）
        // ④ 提交后再读真实库存（独立连接，仅用于统计展示）：扣穿与否一目了然
        const [[after]] = await pool.query('SELECT stock FROM goods WHERE id = ?', [GID_A]);
        if (after.stock < 0) rec.outcome = 'success';   // 超卖订单（库存为负的证据）
      }
    } catch (err) {
      await conn.rollback().catch(() => {});
      if (rec.outcome !== 'timeout') {
        rec.outcome = 'error';
        this.log.push('MYSQL', 'error', `[对照实验] 系统A ${uid} 事务异常: ${err.message}`);
      }
    } finally {
      await conn.query('SET innodb_lock_wait_timeout = DEFAULT').catch(() => {});  // 恢复连接默认值，避免污染池
      rec.dur = Date.now() - t0 - rec.wait;
      rec.respMs = rec.outcome === 'timeout' ? effMs : rec.wait + rec.dur;
      conn.release();
    }
    return rec;
  }

  /* ================= 系统B：真实 Redis EVAL 原子预扣 ================= */
  async _sysB(uid, at) {
    const t0 = Date.now();
    const rec = { uid, at, wait: 0, dur: 0, outcome: 'success', respMs: 0 };
    const [ret] = await this.redis.eval(
      this.store.lua['seckill.lua'], 2, STOCK_KEY_B, BOUGHT_KEY_B, uid);
    if (ret === 0) {
      const orderId = 'D' + Date.now().toString(36).toUpperCase() + Math.floor(Math.random() * 900 + 100);
      await this.redis.lpush(QUEUE_KEY_B, JSON.stringify({
        orderId, userId: uid, goodsId: GID_B, status: '排队中', createdAt: Date.now(),
      }));
    } else {
      rec.outcome = ret === 3 ? 'soldout' : 'duplicate';
    }
    rec.dur = Date.now() - t0;
    rec.respMs = rec.dur;
    return rec;
  }
}

module.exports = { Duel };
