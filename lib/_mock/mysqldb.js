'use strict';
/**
 * FakeMySQL —— 模拟关系型数据库（磁盘持久层）
 *
 * 教学目的：演示「内存库(Redis) + 磁盘库(MySQL)」的读写性能差距，
 * 以及秒杀流量通过消息队列异步落库后的「最终一致」过程。
 *
 * 每次写入随机延迟 60~150ms，模拟磁盘事务 + fsync + 锁竞争的开销；
 * 与 Redis 的微秒级响应形成鲜明对比 —— 这正是库存预扣必须放在 Redis 的原因。
 */
const { sleep } = require('./miniredis');
const rand = (a, b) => a + Math.floor(Math.random() * (b - a));

class FakeMySQL {
  constructor() {
    this.goods = new Map();   // goodsId -> { id, name, price, stock }
    this.orders = new Map();  // orderId -> { orderId, userId, goodsId, status, createdAt, paidAt }
    this.stats = { writes: 0, reads: 0, totalWriteMs: 0 };
  }

  /** 模拟一次磁盘写入的耗时（事务提交 + fsync） */
  async _write() {
    const ms = rand(60, 150);
    this.stats.writes++;
    this.stats.totalWriteMs += ms;
    await sleep(ms);
    return ms;
  }
  async _read() { this.stats.reads++; await sleep(rand(5, 15)); }

  /** 初始化商品（对应真实系统：INSERT INTO goods） */
  async initGoods(goodsId, name, price, stock) {
    this.goods.set(goodsId, { id: goodsId, name, price, stock });
  }

  /**
   * 扣减数据库库存 —— 消息队列消费者在订单落库时调用。
   * 注意：真实生产中这里会带乐观锁：
   *   UPDATE goods SET stock = stock - 1 WHERE id = ? AND stock > 0
   */
  async deductStock(goodsId, qty = 1) {
    const ms = await this._write();
    const g = this.goods.get(goodsId);
    if (!g) throw new Error('商品不存在');
    g.stock -= qty;
    return { ms, stock: g.stock };
  }

  /** 订单落库（对应真实系统：INSERT INTO orders） */
  async insertOrder(order) {
    const ms = await this._write();
    this.orders.set(order.orderId, order);
    return { ms };
  }

  /** 订单状态更新（排队中 -> 已落库 / 已支付 / 已取消） */
  async updateOrderStatus(orderId, status) {
    const ms = await this._write();
    const o = this.orders.get(orderId);
    if (o) o.status = status;
    return { ms };
  }

  async getStock(goodsId) { await this._read(); const g = this.goods.get(goodsId); return g ? g.stock : null; }
  async getOrder(orderId) { await this._read(); return this.orders.get(orderId) || null; }

  listOrders(limit = 50) {
    return [...this.orders.values()].sort((a, b) => b.createdAt - a.createdAt).slice(0, limit);
  }
  countOrders() { return this.orders.size; }

  /** 对账：比较 Redis 已扣库存与 DB 订单数是否一致（最终一致性验收） */
  reconcile(goodsId, redisBoughtCount) {
    const g = this.goods.get(goodsId);
    const dbOrders = this.countOrders();
    return {
      redisBought: redisBoughtCount,
      dbOrders,
      dbStock: g ? g.stock : null,
      consistent: redisBoughtCount === dbOrders,
    };
  }
}

module.exports = { FakeMySQL };
