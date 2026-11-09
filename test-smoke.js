'use strict';
/* 真实组件版冒烟测试：单发/重复/Lua零超卖/MQ最终一致/无锁超卖复现/延迟双删/对账 */
const BASE = 'http://localhost:4000';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const api = async (path, body) => {
  const opt = body !== undefined
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
    : {};
  return fetch(BASE + path, opt).then((r) => r.json());
};
let pass = 0, fail = 0;
const check = (name, ok, detail = '') => {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  —— ' + detail : ''}`);
  ok ? pass++ : fail++;
};
async function waitDrain(timeoutMs = 15000) {
  for (let i = 0; i < timeoutMs / 500; i++) {
    await sleep(500);
    const r = await api('/api/reconcile', {});
    if (r.data.consistent) return r.data;
  }
  return api('/api/reconcile', {}).then((r) => r.data);
}

async function main() {
  console.log('== 0. 环境自检 ==');
  const ov0 = (await api('/api/overview')).data;
  check('真实 Redis 已连接', ov0.engine.versions.redis.startsWith('Redis'), ov0.engine.versions.redis);
  check('真实 MySQL 已连接', ov0.engine.versions.mysql.startsWith('MySQL'), ov0.engine.versions.mysql);

  console.log('== 1. 单发抢购 + 重复拦截 ==');
  await api('/api/reset', { stock: 10 });
  const r1 = await api('/api/seckill', { userId: 'U-TEST-1' });
  check('单发抢购成功', r1.result.code === 0, r1.result.msg);
  const r2 = await api('/api/seckill', { userId: 'U-TEST-1' });
  check('重复购买被拦截', r2.result.code === 1002, r2.result.msg);
  const dr1 = await waitDrain();
  check('订单已异步落库（Redis→MySQL）', dr1.dbOrders >= 1, `DB订单=${dr1.dbOrders}`);

  console.log('== 2. Lua 原子模式压测（100并发抢10件） ==');
  await api('/api/reset', { stock: 10 });
  await api('/api/mode', { mode: 'locked' });
  const rs1 = (await api('/api/stress', { count: 100 })).summary;
  check('成功数 = 库存（10）', rs1.success === 10, `成功${rs1.success}`);
  check('Redis 零超卖', rs1.redisStock === 0, `Redis库存=${rs1.redisStock}`);
  const dr2 = await waitDrain();
  check('MQ 削峰后最终一致', dr2.consistent, `Redis已购=${dr2.redisBought} DB订单=${dr2.dbOrders} 积压=${dr2.backlog}`);
  check('DB 库存与 Redis 对齐（均为0）', dr2.dbStock === 0, `DB库存=${dr2.dbStock}`);

  console.log('== 3. 无锁对照模式压测（真实竞态复现超卖） ==');
  await api('/api/reset', { stock: 10 });
  await api('/api/mode', { mode: 'unsafe' });
  const rs2 = (await api('/api/stress', { count: 100 })).summary;
  check('成功数远超库存（超卖复现）', rs2.success > 10, `成功${rs2.success}件`);
  check('Redis 库存被扣成负数', rs2.redisStock < 0, `Redis库存=${rs2.redisStock}`);

  console.log('== 4. 对账接口 ==');
  await api('/api/mode', { mode: 'locked' });
  await api('/api/reset', { stock: 10 });
  await api('/api/seckill', { userId: 'U-TEST-2' });
  const rec = await waitDrain();
  check('对账最终一致', rec.consistent, `diff=${rec.diff}`);

  console.log(`\n结果: ${pass} 通过, ${fail} 失败 ${fail === 0 ? '✅' : '❌'}`);
  process.exit(fail === 0 ? 0 : 1);
}

main().catch((e) => { console.error('测试异常:', e.message); process.exit(1); });
