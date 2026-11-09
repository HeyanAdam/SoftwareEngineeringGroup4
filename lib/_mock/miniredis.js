'use strict';
/**
 * MiniRedis —— 内置内存数据库模拟器（教学演示核心）
 *
 * 复刻了 Redis 最关键的三个特性：
 *   1) 数据全部驻留内存（Map 结构），读写 O(1)，微秒级响应；
 *   2) 命令在单线程事件循环中「同步、逐条」执行 —— 天然原子，无并发竞争；
 *      （这正是 Redis 采用单线程模型解决读写一致性的根基）
 *   3) 提供与 Redis 同名的核心命令：GET / SET / DECR / SADD / SISMEMBER / HSET / EXPIRE ...
 *
 * 生产环境接入真实 Redis 的方式见前端「原理与代码」板块（ioredis + EVAL 执行 Lua 脚本）。
 */
class MiniRedis {
  constructor() {
    this.strings = new Map();   // String 类型：库存计数、缓存值
    this.sets = new Map();      // Set 类型：已购用户名单（防重复购买）
    this.hashes = new Map();    // Hash 类型：商品详情缓存
    this.expireAt = new Map();  // Key 过期时间（TTL）
    this.stats = { ops: 0 };
    this.startedAt = Date.now();
  }

  _touch(k) { this.stats.ops++; this._expireCheck(k); }
  _expireCheck(k) {
    const t = this.expireAt.get(k);
    if (t && Date.now() > t) {
      this.strings.delete(k); this.sets.delete(k); this.hashes.delete(k); this.expireAt.delete(k);
    }
  }

  /* ---------------- String ---------------- */
  set(k, v) { this._touch(k); this.strings.set(k, String(v)); return 'OK'; }
  get(k) { this._touch(k); const v = this.strings.get(k); return v === undefined ? null : v; }
  setnx(k, v) { this._touch(k); if (this.strings.has(k)) return 0; this.strings.set(k, String(v)); return 1; }
  del(k) {
    this._touch(k);
    let n = 0;
    if (this.strings.delete(k)) n = 1;
    if (this.sets.delete(k)) n = 1;
    if (this.hashes.delete(k)) n = 1;
    this.expireAt.delete(k);
    return n;
  }
  exists(k) { this._touch(k); return (this.strings.has(k) || this.sets.has(k) || this.hashes.has(k)) ? 1 : 0; }
  incr(k) { return this.incrBy(k, 1); }
  decr(k) { return this.incrBy(k, -1); }
  incrBy(k, n) {
    this._touch(k);
    const cur = parseInt(this.strings.get(k) || '0', 10) || 0;
    const v = cur + Number(n);
    this.strings.set(k, String(v));
    return v;
  }
  decrBy(k, n) { return this.incrBy(k, -Number(n)); }

  /* ---------------- Set ---------------- */
  sadd(k, m) {
    this._touch(k);
    let s = this.sets.get(k);
    if (!s) { s = new Set(); this.sets.set(k, s); }
    const before = s.size;
    s.add(String(m));
    return s.size - before;
  }
  sismember(k, m) { this._touch(k); const s = this.sets.get(k); return s && s.has(String(m)) ? 1 : 0; }
  scard(k) { this._touch(k); const s = this.sets.get(k); return s ? s.size : 0; }
  smembers(k) { this._touch(k); const s = this.sets.get(k); return s ? [...s] : []; }

  /* ---------------- Hash ---------------- */
  hset(k, f, v) {
    this._touch(k);
    let h = this.hashes.get(k);
    if (!h) { h = new Map(); this.hashes.set(k, h); }
    h.set(String(f), String(v));
    return 1;
  }
  hget(k, f) { this._touch(k); const h = this.hashes.get(k); return h && h.has(String(f)) ? h.get(String(f)) : null; }
  hgetall(k) {
    this._touch(k);
    const h = this.hashes.get(k); const o = {};
    if (h) for (const [f, v] of h) o[f] = v;
    return o;
  }

  /* ---------------- 通用 ---------------- */
  expire(k, sec) { this.expireAt.set(k, Date.now() + sec * 1000); return 1; }
  ttl(k) {
    this._touch(k);
    const t = this.expireAt.get(k);
    return t ? Math.max(0, Math.round((t - Date.now()) / 1000)) : -1;
  }
  keys(pattern = '*') {
    const all = new Set([...this.strings.keys(), ...this.sets.keys(), ...this.hashes.keys()]);
    const re = new RegExp('^' + pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$');
    return [...all].filter((k) => {
      this._expireCheck(k);
      return re.test(k) && (this.strings.has(k) || this.sets.has(k) || this.hashes.has(k));
    });
  }
  flushdb() {
    this.strings.clear(); this.sets.clear(); this.hashes.clear(); this.expireAt.clear();
    return 'OK';
  }

  /**
   * 原子脚本执行 —— 模拟 Redis 执行 Lua 脚本的语义（EVAL）。
   *
   * 原子性来源：Node.js 事件循环是单线程，fn 内不含任何 await，
   * 因此整段脚本会「一口气」同步执行完毕，期间不会插入其它请求 ——
   * 与 Redis 阻塞式执行 Lua 脚本、保证串行原子性的行为完全一致。
   */
  evalAtomic(fn, desc = 'LuaScript') {
    this.stats.ops++;
    return fn(); // 同步执行 = 原子
  }

  uptime() { return Math.round((Date.now() - this.startedAt) / 1000); }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

module.exports = { MiniRedis, sleep };
