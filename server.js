'use strict';
/**
 * 内存数据库读写一致性 · 秒杀演示系统 —— HTTP 服务
 * 真实组件版：Redis（bin/redis，端口6379）+ MySQL（bin/mysql，端口3306）
 * 启动：node server.js   （默认 http://localhost:4000，需先启动 Redis 与 MySQL）
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const store = require('./lib/realStore');
const { LogBus } = require('./lib/logbus');
const { SeckillService } = require('./lib/seckill');
const { Duel } = require('./lib/duel');
const HotCache = require('./lib/hotcache');

/* ---------------- 初始化组件 ---------------- */
const log = new LogBus();
const seckill = new SeckillService(store, log);
const hot = new HotCache(store, log);
// 对照实验事件复用同一条 SSE 通道（source = DUEL），避免页面开两条长连接把
// 浏览器的 6 连接上限占满，导致后续普通请求全部排队
const duel = new Duel(store, log, (evt) => {
  const data = `data: ${JSON.stringify({ ...evt, source: 'DUEL' })}\n\n`;
  for (const res of sseClients) {
    try { res.write(data); } catch (_) { sseClients.delete(res); }
  }
});

const PORT = process.env.PORT || 4000;
const PUBLIC_DIR = path.join(__dirname, 'public');
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.ico': 'image/x-icon', '.json': 'application/json; charset=utf-8',
};

/* ---------------- SSE 订阅管理 ---------------- */
const sseClients = new Set();
log.subscribe((item) => {
  const data = `data: ${JSON.stringify(item)}\n\n`;
  for (const res of sseClients) {
    try { res.write(data); } catch (_) { sseClients.delete(res); }
  }
});

/* ---------------- 工具函数 ---------------- */
function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

async function readBody(req) {
  return new Promise((resolve) => {
    let raw = '';
    req.on('data', (c) => { raw += c; if (raw.length > 1e6) req.destroy(); });
    req.on('end', () => {
      try { resolve(raw ? JSON.parse(raw) : {}); } catch (_) { resolve({}); }
    });
  });
}

function serveStatic(req, res, pathname) {
  let rel = pathname === '/' ? '/index.html' : pathname;
  const file = path.normalize(path.join(PUBLIC_DIR, rel));
  if (!file.startsWith(PUBLIC_DIR)) { res.writeHead(403); res.end('Forbidden'); return; }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }); res.end('404 Not Found'); return; }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file)] || 'application/octet-stream',
      // 禁止缓存，避免浏览器拿旧的 app.js / index.html 跑新页面
      'Cache-Control': 'no-store, no-cache, must-revalidate',
    });
    res.end(buf);
  });
}

/* ---------------- Redis 演示快照 ---------------- */
async function redisDemoSnapshot() {
  const r = await Promise.all([
    store.redis.get('demo:stock'),
    store.redis.smembers('demo:bought'),
    store.redis.llen('demo:queue'),
    store.redis.get('demo:counter'),
    store.redis.info('stats'),
  ]);
  let totalCmds = '-';
  try {
    const section = r[4] || '';
    const m = section.match(/total_commands_processed:(\d+)/);
    if (m) totalCmds = parseInt(m[1], 10).toLocaleString();
  } catch (_) {}
  return {
    stock: r[0] == null ? '-' : parseInt(r[0], 10),
    bought: r[1] || [],
    boughtCount: (r[1] || []).length,
    queueLen: r[2] || 0,
    counter: r[3] == null ? 0 : parseInt(r[3], 10),
    totalCommands: totalCmds,
  };
}

/* ---------------- API 路由 ---------------- */
async function handleApi(req, res, url) {
  const route = `${req.method} ${url.pathname}`;

  switch (route) {
    /* ---- 全局状态 ---- */
    case 'GET /api/overview':
      return sendJson(res, 200, { code: 0, data: await seckill.overview() });

    /* ---- 秒杀控制 ---- */
    case 'POST /api/reset': {
      const body = await readBody(req);
      const stock = Math.min(999, Math.max(1, parseInt(body.stock, 10) || 10));
      const r = await seckill.reset(stock);
      return sendJson(res, 200, { code: 0, msg: `已重置：库存 ${r.stock} 件，Redis 预热完成`, data: await seckill.overview() });
    }

    case 'POST /api/mode': {
      const body = await readBody(req);
      const mode = body.mode === 'unsafe' ? 'unsafe' : 'locked';
      seckill.mode = mode;
      log.push('CHECK', mode === 'locked' ? 'info' : 'warn',
        mode === 'locked'
          ? '已切换到「Lua 原子模式」：查-判-扣三步在原子脚本内完成，杜绝超卖'
          : '已切换到「无锁对照模式」：先查后减两步分离（人为插入竞态窗口），用于复现超卖');
      return sendJson(res, 200, { code: 0, mode });
    }

    case 'POST /api/seckill': {
      const body = await readBody(req);
      const r = await seckill.handleRequest(body.userId);
      return sendJson(res, 200, { code: 0, result: r });
    }

    case 'POST /api/stress': {
      const body = await readBody(req);
      const count = Math.min(500, Math.max(1, parseInt(body.count, 10) || 100));
      const r = await seckill.stress(count);
      return sendJson(res, 200, r);
    }

    case 'POST /api/mq/toggle': {
      const paused = seckill.toggleConsume();
      log.push('MQ', paused ? 'warn' : 'info', paused
        ? '消费者已暂停 —— 观察 Redis 队列积压（削峰填谷：上游秒杀不受影响，仍在毫秒级返回）'
        : '消费者已恢复 —— 积压订单将陆续落库（BRPOP → MySQL）');
      return sendJson(res, 200, { code: 0, paused });
    }

    case 'GET /api/orders':
      return sendJson(res, 200, { code: 0, data: await store.recentOrders(30) });

    case 'POST /api/reconcile': {
      const rec = await seckill.reconcile();
      log.push('CHECK', rec.consistent ? 'success' : 'warn',
        `对账完成：Redis 已购名单 ${rec.redisBought} 人 ≈ DB 订单 ${rec.dbOrders} 单，队列积压 ${rec.backlog} ${rec.consistent ? '—— 一致 ✓（MQ 消费完成，最终一致达成）' : '（存在积压/差异，等待消费者追平）'}`);
      return sendJson(res, 200, { code: 0, data: rec });
    }

    /* ---- 对照实验（无Redis vs 有Redis） ---- */
    case 'POST /api/duel/start': {
      const body = await readBody(req);
      // 异步执行：SSE 逐条推送过程，接口立即返回
      duel.start(body).catch((err) => log.push('CHECK', 'error', `对照实验异常: ${err.message}`));
      return sendJson(res, 200, { code: 0, msg: '对照实验已启动，请通过 /api/duel/events 观察过程' });
    }

    case 'GET /api/duel/state':
      return sendJson(res, 200, { code: 0, data: duel.snapshot() });

    /* ---- Redis 原理可视化 ---- */
    case 'POST /api/redis-demo/reset': {
      const body = await readBody(req);
      const stock = Math.min(99, Math.max(1, parseInt(body.stock, 10) || 5));
      const r = await Promise.all([
        store.redis.set('demo:stock', stock),
        store.redis.del('demo:bought'),
        store.redis.del('demo:queue'),
        store.redis.set('demo:counter', 0),
      ]);
      return sendJson(res, 200, { code: 0, stock });
    }

    case 'POST /api/redis-demo/burst': {
      const body = await readBody(req);
      const count = Math.min(200, Math.max(1, parseInt(body.count, 10) || 20));
      const mode = body.mode === 'lua' ? 'lua' : 'unsafe';
      /*
        核心：Promise.all 并发发 N 条命令到 Redis，
        Redis 单线程把它们排队执行 —— 每条返回真实 elapsed（微秒级）
      */
      const startedAt = process.hrtime.bigint();
      const promises = [];
      for (let i = 0; i < count; i++) {
        const userId = `u${String(i).padStart(3, '0')}`;
        const fireAt = process.hrtime.bigint();
        const p = mode === 'lua'
          ? store.redis.eval(store.lua['seckill.lua'], 2, 'demo:stock', 'demo:bought', userId)
          : (async () => {
              /* 不安全模式：先 GET 查库存，再 DECR 扣减 —— 中间有竞态窗口，必超卖 */
              const s = await store.redis.get('demo:stock');
              const seen = s == null ? 0 : parseInt(s, 10);
              if (seen <= 0) return { code: 3, msg: 'sold out' };
              // 故意插 1ms 模拟应用层开销 —— 让更多请求一起 GET 到相同值
              await new Promise((r) => setTimeout(r, 1));
              // 此时 seen 可能早已被其他请求 DECR 过了，但我们不知道
              const after = await store.redis.decr('demo:stock');
              if (after < 0) return { code: 5, msg: 'OVERSOLD!' };
              return { code: 0, msg: 'ok' };
            })();
        promises.push(p.then((result) => ({ userId, fireAt, result })));
      }
      const raw = await Promise.allSettled(promises);
      const totalNs = Number(process.hrtime.bigint() - startedAt);
      const results = [];
      for (const r of raw) {
        if (r.status === 'fulfilled') {
          const elapsedNs = Number(process.hrtime.bigint() - r.value.fireAt);
          results.push({
            userId: r.value.userId,
            result: r.value.result,
            waitMs: 0, // 同一 Node 进程发，基本同时到达，wait 接近 0
            elapsedUs: Math.round(elapsedNs / 1000),
          });
        }
      }
      // 统计
      let ok = 0, dup = 0, soldout = 0, oversell = 0;
      for (const r of results) {
        const v = Array.isArray(r.result) ? r.result[0] : r.result.code;
        if (v === 0) ok++;
        else if (v === 2) dup++;
        else if (v === 3) soldout++;
        else oversell++;
      }
      const snap = await redisDemoSnapshot();
      return sendJson(res, 200, {
        code: 0,
        data: {
          mode, count, results,
          totalMs: Math.round(totalNs / 1e6),
          ok, dup, soldout, oversell,
          snapshot: snap,
        },
      });
    }

    case 'GET /api/redis-demo/snapshot':
      return sendJson(res, 200, { code: 0, data: await redisDemoSnapshot() });

    /* ---- 热点数据缓存实验（真实 Redis Cache-Aside + 真实 MySQL 回源） ---- */
    case 'POST /api/hot/query': {
      const body = await readBody(req);
      const r = await hot.queryOne(body.id);
      return sendJson(res, 200, { code: 0, data: { ...r, state: await hot.state() } });
    }

    case 'POST /api/hot/reset':
      return sendJson(res, 200, { code: 0, msg: '已恢复初始状态（3 个热点商品在 Redis，3 个只在 MySQL）', data: await hot.reset() });

    case 'GET /api/hot/state':
      return sendJson(res, 200, { code: 0, data: await hot.state() });

    /* ---- 日志 ---- */
    case 'GET /api/logs':
      return sendJson(res, 200, { code: 0, data: log.recent(200) });

    default:
      return sendJson(res, 404, { code: 404, msg: 'not found' });
  }
}

/* ---------------- 服务器 ---------------- */
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname === '/api/events') {
    // SSE：实时日志流
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-store',
      'Connection': 'keep-alive',
    });
    res.write('data: {"id":0,"ts":' + Date.now() + ',"source":"SYS","level":"info","msg":"日志通道已连接"}\n\n');
    sseClients.add(res);
    req.on('close', () => sseClients.delete(res));
    return;
  }
  if (url.pathname.startsWith('/api/')) {
    try { await handleApi(req, res, url); }
    catch (err) {
      console.error(err);
      sendJson(res, 500, { code: 500, msg: err.message });
    }
    return;
  }
  serveStatic(req, res, url.pathname);
});

server.listen(PORT, async () => {
  console.log('==============================================');
  console.log('  内存数据库读写一致性 · 秒杀演示系统');
  console.log(`  地址: http://localhost:${PORT}`);
  console.log('  引擎: 真实 Redis (6379) + 真实 MySQL (3306)');
  console.log('==============================================');
  // 一键启动场景下 mysqld 冷启动（InnoDB 恢复）可能超过 bat 里的 4 秒等待，这里轮询重试而不是直接失败
  for (let attempt = 1; attempt <= 30; attempt++) {
    try {
      await store.init();
      break;
    } catch (err) {
      if (attempt === 30) {
        log.push('SYS', 'error', `组件初始化失败：${err.message} —— 请确认 Redis(6379) 与 MySQL(3306) 已启动后重启本系统`);
        console.error(err);
        break;
      }
      if (attempt === 1) console.log('组件尚未就绪，等待重试中（每秒一次，最多 30 秒）...');
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  try {
    seckill.start();
    await seckill.reset(10);
    await hot.init();
    await hot.reset();
    log.push('SYS', 'success', `组件就绪：${store.versions.redis} + ${store.versions.mysql}，商品已预热（库存 10 件），Redis 队列消费者已启动`);
  } catch (err) {
    log.push('SYS', 'error', `业务预热失败：${err.message}`);
    console.error(err);
  }
});
