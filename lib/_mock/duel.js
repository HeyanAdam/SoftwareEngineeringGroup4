'use strict';
/**
 * Duel —— 双系统对照实验控制器（演示的核心）
 *
 * 同一批用户、同一份库存，同时打给两个系统，逐条请求实时推送时间线：
 *   系统A（无Redis）：请求直打 MySQL 磁盘库 —— 每笔写 60~150ms + 行锁串行排队
 *                     + 应用层「先查后改」（真实业务最常见的错误写法）
 *                     → 复现：超卖 + 排队雪崩 + 大面积响应超时
 *   系统B（配Redis）：Lua 原子预扣微秒级返回 + 消息队列异步落库
 *                     → 零超卖、响应恒定毫秒级、DB 按自身节奏慢慢追平
 *
 * 过程可信度设计：不是"点按钮出结果"，而是每个请求都有确定的
 * 到达时刻 → 排队等待 → 处理 → 结果，按真实时间轴逐条回放给前端。
 */
const { MiniRedis, sleep } = require('./miniredis');
const rand = (a, b) => a + Math.floor(Math.random() * (b - a));

class Duel {
  constructor(log, broadcast) {
    this.log = log;               // 主日志总线
    this.broadcast = broadcast;   // duel 专用 SSE 推送 (evt) => void
    this.running = false;
    this.state = null;
  }

  snapshot() { return this.state; }

  emit(evt) {
    if (this.state) this.state.events.push(evt);
    this.broadcast(evt);
  }

  /**
   * 启动一次对照实验
   * @param users    用户数（每个用户同时向 A/B 发起一次抢购）
   * @param stock    初始库存（两个系统相同）
   * @param speed    播放速度：1=实时，0.5=慢放一倍（模拟耗时 ×2）
   */
  async start({ users = 50, stock = 10, speed = 1 }) {
    if (this.running) return { code: 409, msg: '实验进行中' };
    this.running = true;
    users = Math.min(200, Math.max(2, parseInt(users, 10) || 50));
    stock = Math.min(999, Math.max(1, parseInt(stock, 10) || 10));
    speed = [0.5, 1, 2].includes(Number(speed)) ? Number(speed) : 1;
    const k = 1 / speed;                                   // 慢放系数
    const writeBase = Math.round(100 * k);                 // 系统A每笔事务基准耗时
    const timeoutMs = Math.round(2500 * k);                // 网关/前端等待超时
    const arriveSpan = Math.round(1200 * k);               // 用户在 0~1200ms 内陆续到达（覆盖库存提交全过程）

    this.state = {
      running: true,
      config: { users, stock, speed, timeoutMs, writeBase, arriveSpan },
      startedAt: Date.now(),
      A: { label: '系统A · 无Redis（请求直打 MySQL）', done: 0, success: 0, soldout: 0, timeout: 0, sumResp: 0, maxResp: 0, stockAfter: stock },
      B: { label: '系统B · 配备Redis（原子预扣 + 异步落库）', done: 0, success: 0, soldout: 0, sumResp: 0, maxResp: 0, stockAfter: stock, persistTotal: 0, persisted: 0 },
      events: [],
    };

    // ---- 生成同一批用户（到达时刻完全相同） ----
    const arrivals = [];
    for (let i = 0; i < users; i++) arrivals.push({ uid: 'U' + (1000 + i), at: rand(0, arriveSpan) });
    arrivals.sort((a, b) => a.at - b.at);

    // ================= 系统A 排队模型（确定性推演） =================
    // ① SELECT 快照读：不排队、瞬时返回（此刻已提交的扣减对后来者可见）
    // ② 应用层判断 seen>0 通过 → 进「行锁队列」排队做 UPDATE（每笔写独占磁盘事务）
    // ③ 等待超过 timeoutMs → 网关掐断，用户看到报错（该笔事务作废）
    const planA = [];
    {
      let nextFree = 0;            // 柜台（行锁）下一个空闲时刻
      const commits = [];          // 每笔事务的提交时刻（严格递增）
      let p = 0;                   // 提交指针
      for (const r of arrivals) {
        while (p < commits.length && commits[p] <= r.at) p++;
        const seen = stock - p;    // SELECT 看到的库存（快照）
        if (seen <= 0) {
          planA.push({ uid: r.uid, at: r.at, wait: 0, dur: rand(2, 6), outcome: 'soldout', doneAt: r.at + 5 });
          continue;
        }
        const start = Math.max(r.at, nextFree);
        const wait = start - r.at;
        if (wait > timeoutMs) {
          planA.push({ uid: r.uid, at: r.at, wait, dur: 0, outcome: 'timeout', doneAt: r.at + wait });
          continue;
        }
        const dur = rand(Math.round(writeBase * 0.6), Math.round(writeBase * 1.5));
        const doneAt = start + dur;
        planA.push({ uid: r.uid, at: r.at, wait, dur, outcome: 'success', doneAt });
        nextFree = doneAt;
        commits.push(doneAt);
      }
    }

    // ================= 系统B 执行模型（Redis 原子预扣） =================
    // 每条请求只有一次原子操作（~1ms）：查-判-扣一口气完成，不存在排队与超时
    const planB = [];
    {
      const redisB = new MiniRedis();
      redisB.set('stock', stock);
      for (const r of arrivals) {
        const stockBefore = parseInt(redisB.get('stock'), 10);
        let outcome;
        if (isNaN(stockBefore) || stockBefore <= 0) outcome = 'soldout';
        else { redisB.decr('stock'); outcome = 'success'; }
        planB.push({ uid: r.uid, at: r.at, wait: 0, dur: 1, outcome, doneAt: r.at + 1, stockBefore });
      }
    }

    // ================= 按真实时间轴回放（过程可见） =================
    const all = [
      ...planA.map((e) => ({ ...e, sys: 'A' })),
      ...planB.map((e) => ({ ...e, sys: 'B' })),
    ].sort((a, b) => a.doneAt - b.doneAt);

    this.emit({ type: 'begin', config: { users, stock, speed, timeoutMs, writeBase, arriveSpan } });
    this.log.push('CHECK', 'info',
      `[对照实验] 开始：${users} 个用户抢 ${stock} 件，同时打给 系统A(无Redis) 与 系统B(有Redis)，速度 ${speed}x`);

    let prev = 0;
    for (const e of all) {
      await sleep(Math.max(0, e.doneAt - prev));   // 按真实节奏逐条推送
      prev = e.doneAt;
      const st = this.state[e.sys];
      st.done++;
      const resp = e.wait + e.dur;
      st.sumResp += resp;
      st.maxResp = Math.max(st.maxResp, resp);
      if (e.outcome === 'success') {
        st.success++;
        st.stockAfter = stock - st.success;
      } else if (e.outcome === 'soldout') st.soldout++;
      else if (e.outcome === 'timeout') st.timeout++;
      this.emit({ type: 'req', sys: e.sys, uid: e.uid, at: e.at, wait: e.wait, dur: e.dur, outcome: e.outcome, respMs: resp });
    }

    // ---- 实验结束：此时 B 的用户早已全部拿到响应，DB 落库仍在后台继续 ----
    const a = this.state.A, b = this.state.B;
    a.stockAfter = stock - a.success;
    b.stockAfter = stock - b.success;
    b.persistTotal = b.success;
    const summary = {
      users, stock,
      A: {
        success: a.success, soldout: a.soldout, timeout: a.timeout,
        avgResp: Math.round(a.sumResp / Math.max(1, a.done)),
        maxResp: a.maxResp,
        stockAfter: a.stockAfter, oversell: Math.max(0, stock - a.stockAfter),
      },
      B: {
        success: b.success, soldout: b.soldout,
        avgResp: Math.round(b.sumResp / Math.max(1, b.done)),
        maxResp: b.maxResp,
        stockAfter: b.stockAfter, oversell: 0,
        persistTotal: b.persistTotal, persisted: 0,
      },
      elapsed: prev,
    };
    this.state.summary = summary;
    this.state.running = false;
    this.emit({ type: 'end', summary });

    this.log.push('CHECK', a.oversell > 0 ? 'error' : 'info',
      `[对照实验] 系统A 结果：成交 ${a.success} 笔（库存仅 ${stock}），超卖 ${summary.A.oversell} 件，超时 ${a.timeout} 人，平均响应 ${summary.A.avgResp}ms —— 先查后改 + 行锁串行的后果`);
    this.log.push('CHECK', 'success',
      `[对照实验] 系统B 结果：成交 ${b.success} 笔，零超卖，平均响应 ${summary.B.avgResp}ms，${b.persistTotal} 笔订单正在后台异步落库 —— Redis 原子预扣 + 削峰`);

    // ---- B 的后台落库（不阻塞、不影响用户已拿到的响应） ----
    (async () => {
      const step = Math.max(60, Math.round(180 * k));
      for (let i = 0; i < summary.B.persistTotal; i++) {
        await sleep(step);
        this.state.B.persisted++;
        this.emit({ type: 'persist', persisted: this.state.B.persisted, total: summary.B.persistTotal });
      }
      this.log.push('MYSQL', 'info', `[对照实验] 系统B 的 ${summary.B.persistTotal} 笔订单已全部异步落库完成，DB 库存与 Redis 对齐（最终一致）`);
    })();

    this.running = false;
    return { code: 0, summary };
  }
}

module.exports = { Duel };
