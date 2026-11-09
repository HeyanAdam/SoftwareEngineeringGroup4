'use strict';
/* 对照实验冒烟测试（真实组件版）：真实并发执行 → 校验超卖/超时/零超卖 → 校验真实落库 */
const BASE = 'http://localhost:4000';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  console.log('== 1. 启动对照实验 (200用户/10库存/网关超时1000ms/2x回放) ==');
  const startRes = await fetch(BASE + '/api/duel/start', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ users: 200, stock: 10, speed: 2, timeoutMs: 1000 }),
  }).then((r) => r.json());
  console.log('启动返回:', JSON.stringify(startRes));
  if (startRes.code !== 0) throw new Error('启动失败: ' + startRes.msg);

  console.log('== 2. 轮询实验状态直到结束（真实并发执行 + 真实时间轴回放） ==');
  let state = null;
  for (let i = 0; i < 60; i++) {
    await sleep(1000);
    const s = await fetch(BASE + '/api/duel/state').then((r) => r.json());
    state = s.data;
    if (state && state.summary) break;
    if (i % 5 === 4) console.log(`  执行/回放中 ...`);
  }
  if (!state || !state.summary) throw new Error('实验未在预期时间内结束');

  const { summary: sm } = state;
  console.log('== 3. 实验结果（全部来自真实 MySQL/Redis） ==');
  console.log('系统A(真实MySQL直打):', JSON.stringify(sm.A));
  console.log('系统B(真实Redis预扣):', JSON.stringify(sm.B));

  const checks = [
    ['A 成交数超过库存(真实超卖复现)', sm.A.success > sm.stock],
    ['A 超卖件数 > 0（MySQL 库存为负）', sm.A.oversell > 0],
    ['A 存在排队超时用户', sm.A.timeout > 0],
    ['A 平均响应明显高于B(行锁+磁盘事务)', sm.A.avgResp > sm.B.avgResp * 5],
    ['B 成交数 = 库存', sm.B.success === sm.stock],
    ['B 零超卖（Lua 原子脚本）', sm.B.oversell === 0],
    ['B 平均响应 ≤100ms（200并发单连接EVAL+LPUSH排队的真实水平，仍远低于A）', sm.B.avgResp <= 100],
    ['B 落库任务数 = 成交数', sm.B.persistTotal === sm.B.success],
  ];
  let fail = 0;
  for (const [name, ok] of checks) {
    console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}`);
    if (!ok) fail++;
  }

  console.log('== 4. 等待 B 真实后台落库（BRPOP → MySQL 事务） ==');
  for (let i = 0; i < 30; i++) {
    await sleep(1000);
    const s = await fetch(BASE + '/api/duel/state').then((r) => r.json());
    if (s.data.summary.B.persisted >= s.data.summary.B.persistTotal) {
      console.log(`  PASS  真实落库完成 ${s.data.summary.B.persisted}/${s.data.summary.B.persistTotal}`);
      break;
    }
    if (i === 29) { console.log('  FAIL  落库超时'); fail++; }
  }

  console.log(fail === 0 ? '\n全部通过 ✅' : `\n${fail} 项失败 ❌`);
  process.exit(fail === 0 ? 0 : 1);
}

main().catch((e) => { console.error('测试异常:', e.message); process.exit(1); });
