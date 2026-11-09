'use strict';
/**
 * LogBus —— 全链路日志总线
 * 汇聚 [限流] [Redis] [Lua] [MQ] [MySQL] [对账] 各环节日志，
 * 通过 SSE 实时推送到前端日志控制台，让整个秒杀链路「可见」。
 */
class LogBus {
  constructor(max = 600) {
    this.ring = [];
    this.max = max;
    this.subs = new Set();
    this.seq = 0;
  }

  /**
   * @param {string} source 日志来源：LIMIT | REDIS | LUA | MQ | MYSQL | CHECK | LAB
   * @param {string} level  info | warn | error | success
   */
  push(source, level, msg, extra = null) {
    const item = { id: ++this.seq, ts: Date.now(), source, level, msg, extra };
    this.ring.push(item);
    if (this.ring.length > this.max) this.ring.shift();
    for (const fn of this.subs) {
      try { fn(item); } catch (_) { /* 订阅者异常不影响主流程 */ }
    }
    return item;
  }

  subscribe(fn) { this.subs.add(fn); return () => this.subs.delete(fn); }
  recent(n = 200) { return this.ring.slice(-n); }
}

module.exports = { LogBus };
