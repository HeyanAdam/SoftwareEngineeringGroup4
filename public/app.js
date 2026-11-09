'use strict';
/* 前端逻辑：Tab 切换 / SSE 日志 / 轮询指标 / 秒杀操作 / 一致性实验台 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

async function api(path, body) {
  const opt = body !== undefined
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
    : {};
  // 加超时兜底：浏览器连接被占满时请求可能永远排队，宁可报错也不要一直卡着
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const res = await fetch(path, { ...opt, signal: ctrl.signal });
    return res.json();
  } catch (e) {
    throw new Error(e.name === 'AbortError' ? '请求超时，请刷新页面重试' : e.message);
  } finally {
    clearTimeout(timer);
  }
}
const fmtTime = (ts) => new Date(ts).toLocaleTimeString('zh-CN', { hour12: false });

/* ================= Tab 切换 ================= */
$$('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    $$('.tab-btn').forEach((b) => b.classList.remove('active'));
    $$('.tab').forEach((t) => t.classList.remove('active'));
    btn.classList.add('active');
    $('#' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'tab-hot') refreshHotSnap();
  });
});

/* ================= SSE 实时日志 ================= */
const logConsole = $('#log-console');
let logCount = 0;
function appendLog(item) {
  const div = document.createElement('div');
  div.className = 'log-line ' + (item.level || 'info');
  div.innerHTML =
    `<span class="log-time">${fmtTime(item.ts)}</span>` +
    `<span class="log-src ${item.source}">[${item.source}]</span>` +
    `<span class="log-msg">${escapeHtml(item.msg)}</span>`;
  logConsole.appendChild(div);
  if (++logCount > 300) { logConsole.removeChild(logConsole.firstChild); logCount--; }
  logConsole.scrollTop = logConsole.scrollHeight;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
const es = new EventSource('/api/events');
es.onmessage = (e) => {
  let item;
  try { item = JSON.parse(e.data); } catch (_) { return; }
  // 对照实验的时间线事件也走这条通道，按 source 分流，避免额外占用一条长连接
  if (item.source === 'DUEL') handleDuelEvent(item);
  else appendLog(item);
};
es.onerror = () => { /* 断线自动重连由浏览器处理 */ };

/* 初始化：拉取最近日志 */
api('/api/logs').then((r) => (r.data || []).forEach(appendLog));

/* ================= 指标轮询 ================= */
let lastStressKey = '';
async function refreshOverview() {
  try {
    const r = await api('/api/overview');
    const d = r.data;
    $('#m-redis-stock').textContent = d.redis.stock;
    $('#m-redis-bought').textContent = d.redis.bought;
    $('#m-db-stock').textContent = d.db.stock;
    $('#m-db-orders').textContent = d.db.orders;
    $('#m-success').textContent = d.metrics.success;
    $('#m-soldout').textContent = d.metrics.failSoldOut;
    $('#m-dup').textContent = d.metrics.failDuplicate;
    $('#m-limited').textContent = d.metrics.limited;
    $('#m-mq-size').textContent = d.mq.size;
    $('#m-oversell').textContent = d.metrics.oversell;
    $('#m-tokens').textContent = d.tokens;
    $('#m-avg-write').textContent = d.db.avgWriteMs || '-';
    $('#engine-badge').textContent = `● ${d.engine.type} + ${d.engine.versions.mysql} · MQ${d.mq.paused ? '已暂停' : '消费中'}`;
    $('#engine-badge').style.color = d.mq.paused ? 'var(--orange)' : 'var(--green)';

    // 模式按钮状态
    $$('.mode-btn[data-mode]').forEach((b) => b.classList.toggle('active', b.dataset.mode === d.mode));

    // 压测结果横幅
    if (d.metrics.lastStress) {
      const s = d.metrics.lastStress;
      const key = `${s.mode}-${s.total}-${s.elapsedMs}`;
      if (key !== lastStressKey) {
        lastStressKey = key;
        showStressBanner(s, d);
      }
    }
  } catch (_) { /* 服务未就绪时静默 */ }
}
setInterval(refreshOverview, 700);
refreshOverview();

function showStressBanner(s, d) {
  const el = $('#stress-banner');
  el.style.display = 'block';
  if (s.mode === 'locked') {
    el.className = 'stress-banner good';
    el.innerHTML = `<b style="color:var(--green)">✅ Lua 原子模式压测结果</b><br>
      发起 ${s.total} 并发 → 成功 <b>${s.success}</b> 件（= 初始库存，<b>零超卖</b>），售罄拦截 ${s.soldOut}，限流 ${s.limited}，耗时 ${s.elapsedMs}ms。<br>
      <span class="muted">Redis 预扣与 DB 落库通过 MQ 异步对齐，点击「立即对账」验证最终一致性。</span>`;
  } else {
    const overN = Math.max(0, s.success - (parseInt($('#input-stock').value, 10) || 10));
    el.className = 'stress-banner bad';
    el.innerHTML = `<b style="color:var(--red)">⚠️ 无锁模式压测结果（超卖已复现）</b><br>
      发起 ${s.total} 并发 → 成功 <b>${s.success}</b> 件，远超库存上限 ${$('#input-stock').value} 件，<b>超卖 ${overN} 件</b>！Redis 库存被扣至 <b>${s.redisStock}</b>（负数），耗时 ${s.elapsedMs}ms。<br>
      <span class="muted">根因：先查库存再减库存的两步之间存在竞态窗口，多个请求同时通过校验。切回「Lua 原子模式」再压测即可对比。</span>`;
  }
}

/* ================= 订单表轮询 ================= */
async function refreshOrders() {
  if (!$('#tab-seckill').classList.contains('active')) return;
  try {
    const r = await api('/api/orders');
    const tb = $('#orders-tbody');
    if (!r.data || r.data.length === 0) { tb.innerHTML = '<tr><td colspan="5" class="muted">暂无订单</td></tr>'; return; }
    tb.innerHTML = r.data.map((o) => {
      const done = o.status !== '排队中';
      return `<tr>
        <td>${escapeHtml(o.order_id)}</td>
        <td>${escapeHtml(o.user_id)}</td>
        <td>${escapeHtml(o.goods_id)}</td>
        <td><span class="order-status ${done ? 'done' : 'queued'}">${o.status}</span></td>
        <td>${fmtTime(o.created_at)}</td>
      </tr>`;
    }).join('');
  } catch (_) {}
}
setInterval(refreshOrders, 1200);

/* ================= 秒杀操作 ================= */
$('#btn-reset').addEventListener('click', async () => {
  const stock = parseInt($('#input-stock').value, 10) || 10;
  const r = await api('/api/reset', { stock });
  hideBanners();
  appendLog({ ts: Date.now(), source: 'SYS', level: 'info', msg: r.msg });
});

$$('.mode-btn[data-mode]').forEach((btn) => {
  btn.addEventListener('click', async () => {
    await api('/api/mode', { mode: btn.dataset.mode });
    $('#mode-desc').textContent = btn.dataset.mode === 'locked'
      ? '查库存→判重复→扣减 三步在一段 Lua 脚本内原子完成，杜绝超卖（对应生产 EVAL seckill.lua）。'
      : '⚠ 对照模式：先查库存、再减库存，两步之间人为插入竞态窗口 —— 用于复现超卖，请勿在真实系统这样写。';
  });
});

$('#btn-seckill').addEventListener('click', async () => {
  const userId = $('#input-userid').value.trim() || undefined;
  const r = await api('/api/seckill', userId ? { userId } : {});
  const el = $('#seckill-result');
  el.style.display = 'block';
  const res = r.result;
  if (res.code === 0) {
    el.className = 'result-banner ok';
    el.innerHTML = `🎉 用户 <b>${res.userId}</b> ${res.msg}，订单号 <b>${res.orderId}</b>（稍后将异步落库，可在订单列表查看状态变化）`;
  } else {
    el.className = 'result-banner err';
    el.innerHTML = `🚫 用户 <b>${res.userId}</b> 抢购失败：${res.msg}`;
  }
});

$('#btn-stress').addEventListener('click', async () => {
  const btn = $('#btn-stress');
  const count = parseInt($('#input-stress').value, 10) || 100;
  btn.disabled = true; btn.textContent = '压测中...';
  try {
    await api('/api/stress', { count });
  } finally {
    btn.disabled = false; btn.textContent = '开始压测';
  }
});

$('#btn-mq-toggle').addEventListener('click', () => api('/api/mq/toggle', {}));
$('#btn-reconcile').addEventListener('click', () => api('/api/reconcile', {}));

function hideBanners() {
  $('#seckill-result').style.display = 'none';
  $('#stress-banner').style.display = 'none';
  lastStressKey = '';
}

/* ================= 对照实验（无Redis vs 有Redis） ================= */
const duelState = { window: 1000, rows: { A: new Map(), B: new Map() }, stats: { A: null, B: null } };

function resetDuelUI(cfg) {
  duelState.window = (cfg.arriveSpan || 80) + cfg.timeoutMs + 500;
  duelState.rows.A.clear(); duelState.rows.B.clear();
  $('#tl-A').innerHTML = '<div class="tl-empty">请求即将到达…</div>';
  $('#tl-B').innerHTML = '<div class="tl-empty">请求即将到达…</div>';
  $('#duel-banner').style.display = 'none';
  $('#persist-B').textContent = '后台落库：0 / -';
  ['A', 'B'].forEach((sys) => {
    duelState.stats[sys] = { done: 0, success: 0, soldout: 0, timeout: 0, sum: 0, max: 0, stock: cfg.stock };
    renderDuelStats(sys);
  });
  renderRulers();
}

function renderRulers() {
  ['A', 'B'].forEach((sys) => {
    const el = $('#ruler-' + sys);
    let html = '';
    for (let i = 0; i <= 4; i++) {
      html += `<span style="left:${i * 25}%">${Math.round(duelState.window * i / 4)}ms</span>`;
    }
    el.innerHTML = html;
  });
}

function renderDuelStats(sys) {
  const s = duelState.stats[sys]; if (!s) return;
  const avg = s.done ? Math.round(s.sum / s.done) : '-';
  const stockColor = s.stock < 0 ? 'var(--red)' : 'inherit';
  let html = `<span>已响应 <b>${s.done}</b></span><span class="ok">成功 <b>${s.success}</b></span><span>售罄 <b>${s.soldout}</b></span>`;
  if (sys === 'A') html += `<span class="bad">超时 <b>${s.timeout}</b></span>`;
  html += `<span>平均响应 <b>${avg}</b> ms</span><span>最大 <b>${s.max}</b> ms</span><span>库存剩 <b style="color:${stockColor}">${s.stock}</b></span>`;
  $('#stats-' + sys).innerHTML = html;
}

function addDuelRow(e) {
  const box = $('#tl-' + e.sys);
  const empty = box.querySelector('.tl-empty');
  if (empty) empty.remove();
  const row = document.createElement('div');
  row.className = 'tl-row';
  row.innerHTML = `<span class="tl-uid">${e.uid}</span><div class="tl-track"></div><span class="tl-ms">${e.respMs}ms</span>`;
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;
  const track = row.querySelector('.tl-track');
  const pct = (v) => (v / duelState.window) * 100;
  let html = '';
  if (e.wait > 0) html += `<div class="tl-seg wait" style="left:${pct(e.at)}%;width:${Math.max(0.6, pct(e.wait))}%"></div>`;
  if (e.dur > 0) html += `<div class="tl-seg proc" style="left:${pct(e.at + e.wait)}%;width:${Math.max(0.6, pct(e.dur))}%"></div>`;
  const dot = e.outcome === 'success' ? 'ok' : e.outcome === 'soldout' ? 'so' : 'to';
  html += `<span class="tl-dot ${dot}" style="left:${pct(e.at + e.wait + e.dur)}%"></span>`;
  track.innerHTML = html;
}

function showDuelBanner(s) {
  const el = $('#duel-banner');
  el.style.display = 'block';
  const speedup = Math.max(1, Math.round(s.A.avgResp / Math.max(1, s.B.avgResp)));
  const aOver = s.A.oversell > 0
    ? ` → <b style="color:var(--red)">超卖 ${s.A.oversell} 件</b>（库存被扣穿）`
    : '';
  el.innerHTML = `<h3>实验结论（同批 ${s.users} 个用户抢 ${s.stock} 件）</h3>
    <div class="table-wrap"><table class="cmp-table">
      <thead><tr><th>指标</th><th>系统A · 无Redis</th><th>系统B · 配备Redis</th></tr></thead>
      <tbody>
        <tr><td>成交订单</td><td style="color:var(--orange)">${s.A.success} 笔（库存只有 ${s.stock} 件）${aOver}</td><td style="color:var(--green)">${s.B.success} 笔（= 库存，零超卖）</td></tr>
        <tr><td>平均响应</td><td style="color:var(--orange)">${s.A.avgResp} ms</td><td style="color:var(--green)">${s.B.avgResp} ms（快约 ${speedup} 倍）</td></tr>
        <tr><td>最大响应</td><td style="color:var(--orange)">${s.A.maxResp} ms</td><td style="color:var(--green)">${s.B.maxResp} ms</td></tr>
        <tr><td>超时（用户看到报错页）</td><td style="color:var(--red)">${s.A.timeout} 人</td><td style="color:var(--green)">0 人</td></tr>
        <tr><td>数据库压力</td><td style="color:var(--orange)">${s.users} 个请求同时涌入，行锁串行排队</td><td style="color:var(--green)">仅 ${s.B.persistTotal} 笔订单按节奏落库（削峰）</td></tr>
      </tbody>
    </table></div>
    <p class="muted small" style="margin-top:10px">结论：没有 Redis 时，磁盘库的行锁让请求排成长队（橙色长条），排在后面的用户等到超时报错，而先排队的人却把库存扣成了负数；配上 Redis 后，判断与扣减在内存中原子完成，每个人毫秒级拿到结果，数据库只在后台安静地记账。</p>`;
}

function handleDuelEvent(evt) {
  if (evt.type === 'begin') resetDuelUI(evt.config);
  else if (evt.type === 'req') {
    const s = duelState.stats[evt.sys]; if (!s) return;
    s.done++;
    if (evt.outcome === 'success') { s.success++; s.stock--; }
    else if (evt.outcome === 'soldout') s.soldout++;
    else if (evt.outcome === 'timeout') s.timeout++;
    s.sum += evt.respMs; s.max = Math.max(s.max, evt.respMs);
    addDuelRow(evt);
    renderDuelStats(evt.sys);
  } else if (evt.type === 'persist') {
    $('#persist-B').textContent = `后台落库：${evt.persisted} / ${evt.total} 笔 —— 用户早已全部拿到响应，MySQL 正在按自己的节奏追平（削峰 + 最终一致）`;
  } else if (evt.type === 'end') {
    showDuelBanner(evt.summary);
    const btn = $('#btn-duel-start');
    btn.disabled = false; btn.textContent = '▶ 再来一次对照实验';
  }
}

$('#btn-duel-start').addEventListener('click', async () => {
  const btn = $('#btn-duel-start');
  btn.disabled = true; btn.textContent = '实验进行中，观察下方时间轴…';
  try {
    await api('/api/duel/start', {
      users: parseInt($('#duel-users').value, 10) || 50,
      stock: parseInt($('#duel-stock').value, 10) || 10,
      speed: parseFloat($('#duel-speed').value) || 1,
      timeoutMs: parseInt($('#duel-timeout').value, 10) || 2500,
    });
  } catch (_) {
    btn.disabled = false; btn.textContent = '▶ 开始对照实验';
  }
});

/* 初始化 Redis 原理面板 */
(async () => {
  await api('/api/redis-demo/reset', { stock: parseInt($('#how-stock').value, 10) || 5 });
  await refreshRedisSnap();
})();

/* ================= Tab③ Redis 工作原理可视化 ================= */

let howMode = 'lua';

$$('.mode-btn[data-how-mode]').forEach((btn) => {
  btn.addEventListener('click', () => {
    $$('.mode-btn[data-how-mode]').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    howMode = btn.dataset.howMode;
    $('#how-mode-desc').innerHTML = howMode === 'lua'
      ? '<b>不安全模式</b>：先发 GET 查库存，再发 DECR 扣减 —— 两条命令之间有竞态窗口，必超卖。<br><b>Lua 原子</b>：判重+查库存+扣减+记账 四步在一条脚本内完成，零超卖。'
      : '<b>不安全模式</b>：先发 GET 查库存，再发 DECR 扣减 —— 两条命令之间有竞态窗口，必超卖。<br><b>Lua 原子</b>：判重+查库存+扣减+记账 四步在一条脚本内完成，零超卖。';
  });
});

$('#how-reset').addEventListener('click', async () => {
  const stock = parseInt($('#how-stock').value, 10) || 5;
  await api('/api/redis-demo/reset', { stock });
  $('#how-demo-stats').style.display = 'none';
  $('#how-pipeline').innerHTML = '<div class="tl-empty">等待发射…（点右下方按钮开始）</div>';
  await refreshRedisSnap();
});

$('#how-go').addEventListener('click', async () => {
  const btn = $('#how-go');
  btn.disabled = true; btn.textContent = '⚡ 发射中…';
  $('#how-pipeline').innerHTML = '<div class="tl-empty">命令正在 Redis 单线程队列里排队…</div>';
  $('#how-demo-stats').style.display = 'none';
  try {
    const count = parseInt($('#how-count').value, 10) || 20;
    const r = await api('/api/redis-demo/burst', { count, mode: howMode });
    if (r.code === 0) renderHowResults(r.data);
  } catch (e) {
    $('#how-pipeline').innerHTML = `<div class="tl-empty" style="color:var(--red)">请求失败：${e.message}</div>`;
  }
  btn.disabled = false; btn.textContent = '🚀 发射并发请求';
  await refreshRedisSnap();
});

function renderHowResults(data) {
  // 统计
  $('#ds-total').textContent = data.totalMs;
  $('#ds-ok').textContent = data.ok;
  $('#ds-soldout').textContent = data.soldout;
  $('#ds-oversell').textContent = data.oversell;
  $('#how-demo-stats').style.display = 'block';

  // 流水线动画：按 elapsedUs 排序（到达先后被 Redis 排队）
  const sorted = [...data.results].sort((a, b) => a.elapsedUs - b.elapsedUs);
  const container = $('#how-pipeline');
  container.innerHTML = '';

  // 逐步出现动画
  sorted.forEach((r, idx) => {
    setTimeout(() => {
      const row = buildPipelineRow(r, howMode);
      container.appendChild(row);
    }, idx * 25);
  });
}

function buildPipelineRow(r, mode) {
  const div = document.createElement('div');
  div.className = 'pipeline-row';

  const code = Array.isArray(r.result) ? r.result[0] : r.result.code;
  const msg = Array.isArray(r.result) ? r.result[1] : r.result.msg;

  let resultCls = 'ok';
  let resultText = 'ok';
  if (code === 2) { resultCls = 'dup'; resultText = 'duplicate'; }
  else if (code === 3) { resultCls = 'soldout'; resultText = 'sold out'; }
  else if (code === 4) { resultCls = 'oversell'; resultText = 'oversell!'; }

  const cmdHtml = mode === 'lua'
    ? `<div class="ph-queue lua"><span class="ph-cmd exec">EVAL seckill.lua</span></div>`
    : `<div class="ph-queue"><span class="ph-cmd">GET stock</span><span class="ph-cmd exec">DECR stock</span></div>`;

  const elapsedCls = r.elapsedUs < 1000 ? 'fast' : (r.elapsedUs < 5000 ? '' : 'slow');
  const elapsedText = r.elapsedUs >= 1000
    ? `${(r.elapsedUs / 1000).toFixed(1)}ms`
    : `${r.elapsedUs}μs`;

  div.innerHTML =
    `<span class="ph-uid">${r.userId}</span>` +
    cmdHtml +
    `<span class="ph-result ${resultCls}">${resultText}</span>` +
    `<span class="ph-elapsed ${elapsedCls}">${elapsedText}</span>`;

  return div;
}

async function refreshRedisSnap() {
  try {
    const r = await api('/api/redis-demo/snapshot');
    if (r.code !== 0) return;
    const d = r.data;
    $('#snap-stock').textContent = d.stock;
    $('#snap-bought-count').textContent = `${d.boughtCount} 人`;
    $('#snap-cmds').textContent = d.totalCommands;
    const list = $('#snap-bought-list');
    list.innerHTML = d.bought.length
      ? d.bought.slice(0, 50).map((u) => `<span>${escapeHtml(u)}</span>`).join('')
      : '<span style="color:#5b6a8f;font-size:10px">(empty)</span>';
  } catch (_) {}
}

/* ================= Tab④ 热点数据缓存 ================= */
let hotState = null;

$('#hot-goods').addEventListener('click', async (e) => {
  const card = e.target.closest('.goods-card');
  if (!card) return;
  const id = card.dataset.id;
  const r = await api('/api/hot/query', { id }).catch((err) => ({ code: 1, msg: err.message }));
  if (r.code !== 0) {
    $('#hot-detail').innerHTML = `<span style="color:var(--red)">打开失败：${escapeHtml(r.msg || '未知错误')}</span>`;
    return;
  }
  renderHotResult(r.data);
  renderHotState(r.data.state);
});

$('#hot-reset').addEventListener('click', async () => {
  const r = await api('/api/hot/reset', {});
  if (r.code === 0) {
    renderHotState(r.data);
    $('#hot-result').style.display = 'none';
    $('#hot-detail').className = 'hot-detail-empty';
    $('#hot-detail').textContent = '点左边任意一个商品，打开它的详情页';
  }
});

function renderHotResult(d) {
  const g = d.row;
  $('#hot-detail').className = 'hot-detail-card';
  $('#hot-detail').innerHTML =
    `<div class="hd-name">${escapeHtml(g.name)}</div>` +
    `<div class="hd-price">¥${g.price}</div>` +
    `<div class="hd-meta">商品编号 ${escapeHtml(g.id)} · 库存 ${g.stock} · 累计访问 ${d.access} 次` +
    `${d.hot ? ' · <b class="hl-red">🔥 热点商品</b>' : ''}</div>`;

  const src = $('#hot-source');
  if (d.source === 'cache') {
    src.textContent = '⚡ 本次来自 Redis 缓存';
    src.className = 'hot-source cache';
    $('#hot-explain').textContent = `Redis 里有这个商品的副本（TTL ${d.ttl}s），直接读内存，全程没有碰 MySQL。`;
  } else {
    src.textContent = '🗄️ 本次来自 MySQL（已写入 Redis）';
    src.className = 'hot-source db';
    $('#hot-explain').textContent = d.hot
      ? `Redis 里没有，去 MySQL 查了一行。这次访问累计已达 ${d.access} 次，判定为热点，写进 Redis 并把缓存时间延长到 ${d.ttl} 秒。`
      : `Redis 里没有，去 MySQL 查了一行，顺手写进 Redis（缓存 ${d.ttl} 秒），60 秒内再打开就快了。`;
  }
  $('#hot-ms').textContent = d.ms >= 10 ? d.ms.toFixed(1) : d.ms.toFixed(2);
  $('#hot-result').style.display = 'block';
}

function renderHotState(s) {
  if (!s || !s.goods) return;
  hotState = s;
  const box = $('#hot-goods');
  box.innerHTML = s.goods.map((g) => {
    const cls = ['goods-card'];
    if (g.cached) cls.push('cached');
    if (g.hot) cls.push('hot');
    const badge = g.cached
      ? `<span class="gc-badge cache">🟢 Redis · ${g.ttl}s</span>`
      : '<span class="gc-badge db">⚪ 只在 MySQL</span>';
    const note = (!g.cached && g.hot)
      ? '<div class="gc-note">🔥 是热点商品，但缓存已过期（TTL 到点被 Redis 自动删除）—— 点一次会重新写入 300s</div>'
      : '';
    return `<div class="${cls.join(' ')}" data-id="${g.id}">
      <div class="gc-top">
        <span class="gc-name">${escapeHtml(g.name)}</span>
        ${g.hot && g.cached ? '<span class="gc-fire">🔥 热点</span>' : ''}
      </div>
      <div class="gc-meta">¥${g.price} · 库存 ${g.stock}</div>
      <div class="gc-foot">
        ${badge}
        <span class="gc-access">访问 ${g.access} 次</span>
      </div>
      ${note}
    </div>`;
  }).join('');

  const cachedGoods = s.goods.filter((g) => g.cached);
  $('#hot-redis-list').innerHTML = cachedGoods.length
    ? cachedGoods.map((g) => `<div class="rk-row">
        <span class="rk-key">cache:hot:${g.id}</span>
        <span class="rk-val">${escapeHtml(g.name)} · TTL ${g.ttl}s${g.hot ? ' 🔥' : ''}</span>
      </div>`).join('')
    : '<div class="tl-empty">(空) —— Redis 里还没有商品缓存</div>';
}

async function refreshHotSnap() {
  try {
    const r = await api('/api/hot/state');
    if (r.code === 0) renderHotState(r.data);
  } catch (_) {}
}

// 在这个 Tab 停留期间每秒刷新，实时看到 TTL 倒计时和热点标记变化
setInterval(() => {
  if ($('#tab-hot').classList.contains('active')) refreshHotSnap();
}, 1000);
refreshHotSnap();
