'use strict';
/**
 * CacheLab —— 「缓存与数据库读写一致性」交互实验台
 *
 * 演示经典不一致场景与「延迟双删」修复方案：
 *   线程B：读缓存 → 未命中 → 读 DB 旧值 → 回填缓存（回填动作存在耗时）
 *   线程A：更新 DB → 删除缓存
 *   若「回填」发生在「删除」之后，脏数据将长期驻留 → 需要延迟双删兜底。
 *
 * 实验台提供手动操作按钮 + 一键自动剧本两种玩法。
 */
const { sleep } = require('./miniredis');

class CacheLab {
  constructor(redis, mysql, log) {
    this.redis = redis;
    this.db = mysql;
    this.log = log;
    this.goodsId = 'LAB001';      // 独立商品记录，与秒杀 Demo（P001）互不干扰
    this.cacheKey = 'cache:goods:P001';
    this.delayMs = 500;           // 延迟双删的「延迟」时长
    this.backfillMs = 300;        // 线程B 回填缓存的耗时
    this.events = [];             // 时间线
    this._pendingBackfill = null; // 线程B 的延迟回填定时器
    this._autoRunning = false;
  }

  _event(who, action, detail, level = 'info') {
    const e = {
      seq: this.events.length + 1, ts: Date.now(),
      who, action, detail, level,
      snapshot: { dbStock: this._dbStock(), cacheVal: this.redis.get(this.cacheKey) },
    };
    this.events.push(e);
    if (this.events.length > 60) this.events.shift();
    this.log.push('LAB', level, `[一致性实验] ${who}：${action} —— ${detail}`);
    return e;
  }

  _dbStock() {
    const g = this.db.goods.get(this.goodsId);
    return g ? g.stock : null;
  }

  snapshot() {
    return {
      cacheKey: this.cacheKey,
      dbStock: this._dbStock(),
      cacheVal: this.redis.get(this.cacheKey),
      pendingBackfill: !!this._pendingBackfill,
      delayMs: this.delayMs,
      backfillMs: this.backfillMs,
      events: this.events,
      autoRunning: this._autoRunning,
    };
  }

  reset() {
    if (this._pendingBackfill) { clearTimeout(this._pendingBackfill); this._pendingBackfill = null; }
    let g = this.db.goods.get(this.goodsId);
    if (!g) {
      g = { id: this.goodsId, name: '实验商品（一致性沙盘）', price: 199, stock: 100 };
      this.db.goods.set(this.goodsId, g);
    }
    g.stock = 100;                             // DB 权威值
    this.redis.set(this.cacheKey, 100);        // 缓存旧值（本实验从「缓存有旧值100、DB即将被改为99」开始）
    this.events = [];
    this._autoRunning = false;
    this._event('系统', '重置实验', 'DB=100，缓存=100（初始一致）', 'info');
    return this.snapshot();
  }

  /** 线程B：读缓存 */
  threadB_readCache() {
    const v = this.redis.get(this.cacheKey);
    if (v === null) {
      this._event('线程B', '读缓存', `未命中（key=${this.cacheKey} 不存在），需要回源读 DB`, 'warn');
    } else {
      this._event('线程B', '读缓存', `命中！返回旧值 ${v}${String(v) !== String(this._dbStock()) ? '（注意：这是脏数据，DB 已是 ' + this._dbStock() + '）' : '（与 DB 一致）'}`,
        String(v) !== String(this._dbStock()) ? 'error' : 'success');
    }
    return this.snapshot();
  }

  /** 线程A：更新 DB（模拟扣减库存 100 → 99） */
  threadA_updateDb() {
    const g = this.db.goods.get(this.goodsId);
    const old = g.stock;
    g.stock = old - 1;
    this._event('线程A', '更新 DB', `stock: ${old} → ${g.stock}（事务已提交，磁盘层为权威值）`, 'info');
    return this.snapshot();
  }

  /** 线程A：删除缓存（Cache-Aside 标准动作） */
  threadA_delCache() {
    const existed = this.redis.del(this.cacheKey);
    this._event('线程A', '删除缓存', existed ? `DEL ${this.cacheKey} 成功` : `DEL ${this.cacheKey}（缓存本已为空，空删无害）`, 'info');
    return this.snapshot();
  }

  /**
   * 线程B：读 DB 旧值并「延迟回填」缓存
   * 关键：B 先把旧值读进内存，过 backfillMs 才写回缓存 —— 这段时间差是不一致的根源。
   */
  threadB_readDbBackfill() {
    const old = this._dbStock();
    this._event('线程B', '回源读 DB', `读到 stock=${old}（注意：可能是更新前的旧值），${this.backfillMs}ms 后将回填缓存`, 'warn');
    if (this._pendingBackfill) clearTimeout(this._pendingBackfill);
    this._pendingBackfill = setTimeout(() => {
      this._pendingBackfill = null;
      this.redis.set(this.cacheKey, old);
      const dbNow = this._dbStock();
      const dirty = String(old) !== String(dbNow);
      this._event('线程B', '回填缓存', `SET ${this.cacheKey} = ${old}${dirty ? ` —— 脏数据写入！缓存(${old}) ≠ DB(${dbNow})，不一致已发生且将长期存在` : ' —— 与 DB 一致，缓存恢复'}`,
        dirty ? 'error' : 'success');
    }, this.backfillMs);
    return this.snapshot();
  }

  /** 线程A：延迟双删 = 删一次 → 延迟 delayMs → 再删一次（兜底清除期间回填的脏数据） */
  threadA_delayedDoubleDelete() {
    this.redis.del(this.cacheKey);
    this._event('线程A', '延迟双删·第一次删除', `DEL ${this.cacheKey}（若此刻缓存已是脏值，先删掉）`, 'info');
    setTimeout(() => {
      const existed = this.redis.del(this.cacheKey);
      this._event('线程A', '延迟双删·第二次删除', existed
        ? `延迟 ${this.delayMs}ms 后再次 DEL —— 把「第一次删除之后」回填进来的脏数据清掉，兜底成功，最终一致`
        : `延迟 ${this.delayMs}ms 后再次 DEL —— 缓存为空（期间没有脏回填），下次读取将回源 DB 拿到最新值，最终一致`,
        'success');
    }, this.delayMs);
    return this.snapshot();
  }

  /** 线程B：读缓存，未命中则回源 DB 并立即回填（正常回填，拿到的就是新值） */
  threadB_recover() {
    const v = this.redis.get(this.cacheKey);
    if (v !== null) {
      this._event('线程B', '读缓存', `命中，值=${v}，无需回源`, 'info');
    } else {
      const dbv = this._dbStock();
      this.redis.set(this.cacheKey, dbv);
      this._event('线程B', '回源回填', `未命中 → 读 DB=${dbv} → SET 缓存=${dbv}，缓存与 DB 恢复一致`, 'success');
    }
    return this.snapshot();
  }

  /**
   * 一键自动剧本：完整演绎「不一致如何产生 → 延迟双删如何兜底」
   * 时间线（ms）：
   *   t0      B 回源读 DB（拿到旧值 100，回填定时器 300ms 后触发）
   *   t+100   A 更新 DB → 99
   *   t+150   A 删除缓存（空删）
   *   t+300   B 回填旧值 100 → 缓存脏了（不一致出现，且不会被后续读修复）
   *   t+800   A 延迟双删·第一次删除（清掉脏值 100）
   *   t+1300  A 延迟双删·第二次删除（兜底：即使第一次删除晚于回填也能清掉）
   *   t+1400  B 再次读缓存 → 未命中 → 回源 DB=99 → 一致恢复
   */
  async autoScript() {
    if (this._autoRunning) return { code: 409, msg: '剧本运行中' };
    this._autoRunning = true;
    this.reset();
    this._event('系统', '自动剧本开始', '将依次演示：脏回填 → 不一致出现 → 延迟双删兜底 → 一致恢复', 'info');

    this.threadB_readDbBackfill();               // t0：B 读到旧值，300ms 后回填
    await sleep(100);
    this.threadA_updateDb();                     // t+100：A 更新 DB
    await sleep(50);
    this.threadA_delCache();                     // t+150：A 删缓存（此时缓存还空）
    this._event('系统', '观察点①', '此时缓存为空、DB=99 —— 看起来一致？但线程B手里还攥着旧值 100！', 'warn');
    await sleep(200);                            // t+350：B 的回填定时器触发 → 脏数据写入
    this._event('系统', '观察点②', '回填发生！缓存=100(旧) 而 DB=99(新)，且 Cache-Aside 的「先更库再删缓存」已经执行完，无人再修正缓存 → 不一致长期存在', 'error');
    await sleep(450);                            // t+800
    this.threadA_delayedDoubleDelete();          // 第一次删除（清脏值）+ 500ms 后第二次删除
    await sleep(this.delayMs + 150);             // 等第二次删除完成 → t+1450
    this.threadB_recover();                      // B 读缓存 → 未命中 → 回源 DB 新值 → 恢复一致
    this._event('系统', '剧本结束', '结论：延迟双删用「第二次删除」兜底清除了并发窗口内的脏回填，保障最终一致', 'success');
    this._autoRunning = false;
    return this.snapshot();
  }
}

module.exports = { CacheLab };
