'use strict';
/**
 * FakeMQ —— 模拟消息队列（RocketMQ / Kafka 的教学替身）
 *
 * 在秒杀架构中的职责：
 *   1) 削峰填谷：把瞬时 10 万级请求「拉平」成 MySQL 可承受的写入曲线；
 *   2) 异步解耦：Redis 预扣成功即返回「抢购成功」，落库由消费者异步完成；
 *   3) 最终一致：消费失败自动重回队列，直到落库成功 —— 保证订单不丢。
 */
class FakeMQ {
  constructor(name = 'order-create-queue', consumeInterval = 220) {
    this.name = name;
    this.queue = [];
    this.paused = false;
    this.consumeInterval = consumeInterval;
    this.stats = { published: 0, consumed: 0, retry: 0 };
    this._handler = null;
    this._timer = null;
  }

  /** 生产者投递消息（秒杀预扣成功后调用） */
  publish(msg) {
    this.queue.push(msg);
    this.stats.published++;
    return this.stats.published;
  }

  size() { return this.queue.length; }

  /** 启动消费者循环：按固定速率消费，模拟真实的消费端限速 */
  start(handler) {
    this._handler = handler;
    this._timer = setInterval(async () => {
      if (this.paused || this.queue.length === 0) return;
      const msg = this.queue.shift();
      try {
        await this._handler(msg);
        this.stats.consumed++;
      } catch (err) {
        // 消费失败重回队头，保证最终一致（生产中对应 MQ 的重试机制）
        this.stats.retry++;
        this.queue.unshift(msg);
      }
    }, this.consumeInterval);
  }

  pause() { this.paused = true; return this.paused; }
  resume() { this.paused = false; return this.paused; }
  clear() { this.queue = []; }
}

module.exports = { FakeMQ };
