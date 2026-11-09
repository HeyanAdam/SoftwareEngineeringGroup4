'use strict';
/* 生成《内存数据库读写一致性 · 秒杀演示系统 技术说明文档》.docx */
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
  ShadingType, Footer, PageNumber,
} = require('docx');

const FONT = { ascii: 'Arial', hAnsi: 'Arial', eastAsia: 'Microsoft YaHei' };
const MONO = { ascii: 'Consolas', hAnsi: 'Consolas', eastAsia: 'Microsoft YaHei' };
const CONTENT_W = 9026; // A4 内容宽度 (DXA)

/* ---------- helpers ---------- */
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const h3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const p = (runs) => new Paragraph({
  children: (Array.isArray(runs) ? runs : [runs]).map((r) => (typeof r === 'string' ? new TextRun(r) : r)),
  spacing: { after: 120 },
});
const B = (t) => new TextRun({ text: t, bold: true });
const RED = (t) => new TextRun({ text: t, bold: true, color: 'C00000' });
const GREEN = (t) => new TextRun({ text: t, bold: true, color: '2E7D32' });
const bullet = (t) => new Paragraph({
  numbering: { reference: 'bullets', level: 0 },
  children: [new TextRun(t)],
});
const code = (lines) => lines.map((ln) => new Paragraph({
  shading: { fill: 'F4F4F4', type: ShadingType.CLEAR },
  spacing: { after: 0, line: 240 },
  children: [new TextRun({ text: ln.length ? ln : ' ', font: MONO, size: 18 })],
}));
const note = (t) => new Paragraph({
  children: [new TextRun({ text: t, size: 20, color: '666666' })],
  spacing: { after: 120 },
});

const bd = { style: BorderStyle.SINGLE, size: 1, color: 'BBBBBB' };
const borders = { top: bd, bottom: bd, left: bd, right: bd };
function cell(text, w, opts = {}) {
  return new TableCell({
    borders,
    width: { size: w, type: WidthType.DXA },
    shading: opts.head ? { fill: 'D9E7F5', type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      children: [new TextRun({ text, bold: !!opts.head, size: opts.size || 20 })],
    })],
  });
}
function table(widths, header, rows) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ cantSplit: true, children: header.map((t, i) => cell(t, widths[i], { head: true })) }),
      ...rows.map((r) => new TableRow({
        cantSplit: true,
        children: r.map((t, i) => cell(t, widths[i])),
      })),
    ],
  });
}
const gap = () => new Paragraph({ children: [], spacing: { after: 120 } });

/* ---------- 文档内容 ---------- */
const children = [
  /* 封面区 */
  new Paragraph({ spacing: { before: 2400, after: 240 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: '内存数据库读写一致性 · 秒杀演示系统', bold: true, size: 52 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new TextRun({ text: '技 术 说 明 文 档', size: 36 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 2400 },
    children: [new TextRun({ text: '选型对比 · 原理分析 · 编程技巧 · 实验操作指引', size: 24, color: '666666' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: '配套演示系统：miaosha-demo（真实 Redis 5.0.14 + 真实 MySQL 8.0.28 + Node.js，双击 start-all.bat 后访问 http://localhost:4000）', size: 20, color: '888888' })] }),
  new Paragraph({ children: [], pageBreakBefore: false }),
  new Paragraph({ children: [], spacing: { after: 200 } }),

  /* 引言 */
  h1('引言：为什么需要内存数据库'),
  p('为提高系统运行速度，业界普遍在磁盘数据库（MySQL 等）之外引入内存数据库作为辅助存储。本系统以"互联网秒杀"为场景，'
    + '通过一个可操作、可观察的对照实验，演示"没有 Redis 时的故障"与"配上 Redis 后的解决"，并配套说明内存数据库的选型对比与读写一致性的原理。'),
  p([B('本文档与系统的分工：'), '系统页面只负责"过程演示"（逐条请求的时间轴、可交互的实验台）；所有对比表、原理分析、生产级代码放在本文档中，避免演示页面信息过载。']),

  /* ============ 第一章 ============ */
  h1('一、当前成熟的内存数据库对比'),
  p('内存数据库把数据放在内存中，读写比磁盘数据库快 1~3 个数量级。当前主流产品的对比如下：'),
  table([1300, 2400, 2400, 2926],
    ['产品', '主要优点', '主要缺点', '典型适用场景'],
    [
      ['Redis', '数据结构丰富（String/Hash/List/Set/ZSet/Stream）；单线程命令执行天然原子；Lua 脚本、事务、发布订阅齐全；主从+哨兵+Cluster 高可用成熟；生态最大（几乎所有语言都有客户端）',
        '单实例内存容量受限于 RAM；大 key 与热 key 需要治理；纯缓存场景下持久化(RDB/AOF)会带来额外开销',
        '缓存、秒杀/计数器/排行榜、分布式锁、会话共享 —— 本系统选型'],
      ['Memcached', '多线程、极简单纯 KV，小对象吞吐高；实现简单稳定', '只有字符串 KV，无持久化、无复制、无原子脚本；数据结构匮乏', '纯缓存（页面片段、小对象）'],
      ['Hazelcast', 'Java 生态嵌入式部署；数据分片与计算同址；支持 Near-Cache', 'JVM 内存开销大；社区版功能受限；API 较重', 'Java 集群内数据网格、分布式计算'],
      ['Apache Ignite', '内存优先的分布式数据库，支持 SQL 与 ACID 事务；可穿透到磁盘', '组件复杂、学习成本高；资源占用大', '大规模计算与 HTAP 混合负载'],
      ['Aerospike', 'SSD 友好（内存索引+磁盘存储）；超大规模广告类场景验证充分', '社区版功能有限；Schema 与运维门槛高', '海量 KV、实时画像与风控'],
      ['VoltDB', '内存 OLTP，存储过程串行执行保证强一致，吞吐极高', 'SQL 子集受限；单库容量小；商用授权为主', '高频小事务（计费、风控决策）'],
      ['Dragonfly', '兼容 Redis 协议，多线程无共享架构，单机吞吐更高、内存更省', '较新，生态与高可用方案仍在完善', '大流量 Redis 兼容场景的替代'],
    ]),
  gap(),
  h2('1.1 为什么本演示选择 Redis'),
  bullet('原子性手段最全：Lua 脚本（EVAL）、MULTI/EXEC、WATCH 乐观锁、单命令原子操作（DECR/SETNX）一应俱全，是解决"查-判-扣"竞态最直接的武器；'),
  bullet('秒杀场景事实标准：库存预扣、请求限流（令牌桶）、分布式锁、排行榜均可由 Redis 一站完成，生产验证案例最多；'),
  bullet('协议开放生态最大：本系统直接运行真实 Redis 5.0.14（Windows 移植版），业务代码通过 ioredis 客户端访问，与生产环境完全同构，演示结论可直接平移。'),

  /* ============ 第二章 ============ */
  h1('二、读写一致性问题：从哪来，怎么解'),
  h2('2.1 问题从哪里来'),
  p('内存数据库通常不独立存在，而是与磁盘数据库组成"缓存 + 权威存储"架构。一致性风险就出在"同一份数据有两个副本"上，具体有三大来源：'),
  table([2200, 4200, 2626],
    ['来源', '发生过程', '典型后果'],
    [
      ['缓存-DB 双写时序', '先更新 DB 再更新/删除缓存时，两个并发的"读改写"穿插（如 A 删缓存 → B 读到旧值回填 → A 才写 DB 完成），缓存中留下脏数据',
        '读请求长期命中旧值（脏回填）'],
      ['主从复制延迟', 'Redis 主节点写成功即返回，从节点异步复制；读从节点可能读到旧库存', '刚扣减完再读，库存"回来了"'],
      ['并发"读改写"竞态', '应用层先 SELECT 查库存、再在内存判断、最后 UPDATE 扣减 —— 三步之间没有任何保护，多个请求同时通过判断',
        RED('超卖（库存扣成负数）') + '，这是秒杀最致命的故障'],
    ]),
  gap(),
  h2('2.2 解决方案矩阵'),
  table([1750, 2900, 2200, 2176],
    ['方案', '核心思想', '优点', '局限 / 适用'],
    [
      ['Cache-Aside + 过期时间', '读：先缓存后 DB 并回填；写：更新 DB 后删除缓存；兜底 TTL', '实现最简单，最终一致', '窗口期内仍可能短暂不一致；适合一般缓存'],
      ['Lua 脚本原子执行', '把"查-判-扣"写成一段 Lua，在 Redis 单线程内一口气执行（EVAL）', '彻底消除竞态，微秒级完成，实现简单', '脚本须保持短小；本系统秒杀预扣的核心方案'],
      ['延迟双删', '写：删缓存 → 更新 DB → 延迟几百毫秒再删一次，清掉延迟回填的脏数据', '大幅降低脏读窗口，改动小', '延迟值需按业务估计；系统实验台 ② 可交互演示'],
      ['Canal 订阅 binlog', '伪装成 MySQL 从库订阅 binlog，变更后异步删除/更新缓存', '业务代码零侵入，时序可靠', '引入中间件，有秒级延迟；大厂常用'],
      ['Redisson 分布式锁', '对同一商品加分布式互斥锁，串行化临界区', '通用、可保护跨资源操作', '有锁开销与死锁风险；扣库存场景 Lua 已够用'],
      ['MULTI/EXEC + WATCH', '事务前 WATCH 关键 key，提交时若被改过则整体重试（乐观锁）', '无需 Lua 也能原子更新', '高竞争下重试风暴；适合低冲突场景'],
      ['WAIT 强同步复制', '写后 WAIT N 等待至少 N 个从节点确认', '降低主从延迟丢数据风险', '增加写延迟；仅用于强一致要求点'],
    ]),
  gap(),
  p([B('组合拳（生产推荐）：'), '秒杀预扣用 ', B('Lua 原子脚本'), '；普通读写缓存用 ', B('Cache-Aside + TTL'),
    '；关键写路径叠加 ', B('延迟双删'), ' 或 ', B('Canal 订阅 binlog'), '；跨资源操作才上 ', B('分布式锁'), '。']),

  /* ============ 第三章 ============ */
  h1('三、互联网秒杀应用场景：难点与架构'),
  h2('3.1 秒杀难在哪'),
  bullet(RED('瞬时洪峰') + '：百万级请求在 1~2 秒内涌入，磁盘数据库每秒只能处理几十~几百笔行锁事务，排队雪崩、大面积超时；'),
  bullet(RED('超卖') + '："先查库存再扣减"两步分离，并发下判断形同虚设，100 个人抢 10 件可能成交几十单；'),
  bullet('少卖与重复下单：Redis 扣了 DB 没扣（宕机）、用户连点重复下单；'),
  bullet('黄牛/脚本：请求分布不均，需要限流与防刷。'),
  h2('3.2 标准架构：五层漏斗'),
  p('生产级秒杀把"能不能买"的判断尽量前移，数据库只做最终记账：'),
  code([
    '用户请求',
    '  │ ① 网关限流（令牌桶：每秒只放行 N 个，其余直接拒绝）',
    '  ▼',
    'Redis 原子预扣（Lua：查-判-扣一口气，微秒级） ──失败──▶ 直接返回"已抢完/重复"',
    '  │ 成功',
    '  ▼',
    '消息队列（把 5 万笔/秒 的写请求削峰成 数据库能承受的节奏）',
    '  │',
    '  ▼',
    'MySQL 异步落库（订单持久化，库存最终对齐）',
    '  │',
    '  ▼',
    '定时对账（Redis 与 DB 库存核对，兜底最终一致）',
  ]),
  note('本系统 Tab ③ 的架构图与日志总线实时展示这条链路；Tab ① 的对照实验则量化"没有这条链路时会发生什么"。'),
  h2('3.3 演示系统与生产方案的映射'),
  table([2600, 3100, 3326],
    ['演示系统模块', '对应生产方案', '代码位置（miaosha-demo/）'],
    [
      ['真实 Redis 数据访问层', '生产 Redis 客户端封装（连接复用、SCRIPT LOAD、独立消费连接）', 'lib/realStore.js + ioredis'],
      ['Lua 原子预扣（_luaSeckill）', 'EVAL/SCRIPT LOAD seckill.lua：SISMEMBER 判重 + GET 判库存 + DECR/SADD 扣减，原子完成', 'lua/seckill.lua + lib/seckill.js'],
      ['无锁对照模式（_unsafeSeckill）', '反例：应用层先查后改，人为制造竞态窗口复现超卖', 'lib/seckill.js'],
      ['令牌桶限流', 'nginx limit_req / Redis + Lua 令牌桶', 'lua/ratelimit.lua + lib/seckill.js'],
      ['Redis List 队列削峰', 'RocketMQ / Kafka 订单消息 + 消费落库（本系统用 LPUSH/BRPOP 等价演示）', 'lib/seckill.js 消费者'],
      ['真实 MySQL + 对账 reconcile', 'MySQL 8.0.28 订单表 + 事务落库 + 定时对账任务（T+0/T+1）', 'lib/realStore.js + lib/seckill.js'],
      ['Redis 原理可视化', '命令流水线动画 / 并发超卖复现（真实 EVAL 与 GET→DECR）', 'public/app.js · server.js'],
      ['对照实验 Duel', '同批流量分别打"MySQL 直打"与"Redis 预扣"的量化对比（真实行锁 + innodb_lock_wait_timeout）', 'lib/duel.js'],
    ]),

  /* ============ 第四章 ============ */
  h1('四、核心编程技巧与关键代码'),
  h2('4.1 秒杀 Lua 脚本（本系统实际使用）'),
  p('把"判重、查库存、扣减"三步放进一段脚本，Redis 单线程执行期间不会插入其他命令 —— 竞态从根上消失：'),
  code([
    '-- seckill.lua  KEYS[1]=库存key  KEYS[2]=用户去重set  ARGV[1]=用户ID',
    'if redis.call(\'SISMEMBER\', KEYS[2], ARGV[1]) == 1 then',
    '  return {2, \'duplicate\'}          -- 已抢过',
    'end',
    'local stock = tonumber(redis.call(\'GET\', KEYS[1]) or \'-1\')',
    'if stock <= 0 then',
    '  return {3, \'sold out\'}            -- 售罄',
    'end',
    'redis.call(\'DECR\', KEYS[1])',
    'redis.call(\'SADD\', KEYS[2], ARGV[1])',
    'return {0, \'ok\'}                    -- 抢购成功',
  ]),
  note('对应文件：lua/seckill.lua；Node 中用 redis.script(\'LOAD\', lua) 预加载后 EVALSHA 调用（未命中自动降级 EVAL）。脚本要短小，避免阻塞 Redis。'),
  h2('4.2 生产环境 Java 调用示例'),
  code([
    '// Jedis + Lua：预加载脚本后仅需传 SHA，网络开销最小',
    'String sha = jedis.scriptLoad(lua);',
    'Object r = jedis.evalsha(sha, 2, "stock:P001", "bought:P001", userId);',
    '',
    '// Redisson 分布式锁（保护跨资源操作时使用）',
    'RLock lock = redisson.getLock("lock:stock:P001");',
    'if (lock.tryLock(2, 5, TimeUnit.SECONDS)) {',
    '    try { /* 查库存 -> 判断 -> 扣减 -> 写订单 */ }',
    '    finally { lock.unlock(); }',
    '}',
  ]),
  h2('4.3 WATCH 乐观锁（不用 Lua 的原子扣减）'),
  code([
    'while (true) {',
    '  WATCH stock:P001',
    '  int s = GET stock:P001',
    '  if (s <= 0) break;                 // 售罄',
    '  MULTI;  DECR stock:P001;  EXEC;    // 若 key 被改过则 EXEC 返回 null -> 重试',
    '}',
  ]),
  note('高竞争下重试次数暴涨，因此秒杀首选 4.1 的 Lua 方案；WATCH 更适合低冲突场景。'),
  h2('4.4 延迟双删（缓存一致性兜底）'),
  code([
    'async function updateGoods(id, newVal) {',
    '  await redis.del(`cache:goods:${id}`);   // 第一次删：清旧值',
    '  await db.update(`goods SET price=${newVal} WHERE id=${id}`);',
    '  await sleep(500);                        // 等待并发的旧读完成回填',
    '  await redis.del(`cache:goods:${id}`);   // 第二次删：清脏回填',
    '}',
  ]),
  note('完整交互演示见系统 Tab ②「缓存一致性实验台」：可手动逐步执行，也可点"自动剧本"观看脏回填发生与被兜底的全过程。'),
  h2('4.5 本系统如何接入真实组件（Node/ioredis/mysql2）'),
  p([B('数据访问层 lib/realStore.js 的封装要点：')]),
  bullet('ioredis 客户端连接真实 Redis(6379)；BRPOP 等阻塞命令必须用 redis.duplicate() 的独立连接，否则会卡住主连接上的所有命令；'),
  bullet('mysql2/promise 连接池（connectionLimit 120）连接真实 MySQL(3306)，订单落库走显式事务（beginTransaction → INSERT → UPDATE → commit）；'),
  bullet('Lua 脚本启动时 SCRIPT LOAD 预加载，运行期 EVALSHA 调用（哈希未命中自动降级 EVAL），与生产做法一致；'),
  bullet('Node 侧代码（_luaSeckill 调 EVAL、消费者 BRPOP、事务落库）见 lib/seckill.js。'),
  code([
    '// Node 版 EVAL 调用（lib/seckill.js 实际代码）',
    'const [ret] = await this.redis.eval(',
    '    this.store.lua[\'seckill.lua\'],   // SCRIPT LOAD 预加载过的脚本原文',
    '    2, \'stock:P001\', \'bought:P001\', userId);',
    '// ret = [0,\'ok\'] 成功 | [2,\'duplicate\'] 重复 | [3,\'sold out\'] 售罄',
  ]),
  p([B('迁移到 Java 生产栈的方式：'), '业务语义不变，把 ioredis 换成 Jedis/Lettuce/Redisson、mysql2 换成 MyBatis/JPA 即可 —— 命令语义与 Lua 接口完全一致（见 4.2）。']),

  /* ============ 第五章 ============ */
  h1('五、对照实验操作指引'),
  h2('5.1 启动系统'),
  code([
    '方式一（推荐）：双击 start-all.bat',
    '    自动依次拉起 Redis(6379) -> MySQL(3306) -> 演示系统(4000)',
    '',
    '方式二（手动分步）：',
    '    bin\\redis\\redis-server.exe bin\\redis-demo.conf',
    '    bin\\mysql\\bin\\mysqld.exe --defaults-file=mysql-init.ini --console',
    '    npm install          # 仅首次',
    '    node server.js',
    '',
    '# 打开 http://localhost:4000（详细部署见第六章）',
  ]),
  note('演示系统启动时会自动等组件就绪（每秒重试，最多 30 秒），因此 MySQL 冷启动稍慢也不会失败。'),
  h2('5.2 实验一（Tab ①）：同批用户，无 Redis vs 有 Redis'),
  p([B('步骤：'), '① 填写"用户数 200、库存 10、网关超时 1000ms"，播放速度选 0.5x 慢放（推荐演示）或 1x 实时；'
    + '② 点击"开始对照实验"；③ 观察左右两条时间轴逐条播放每个请求的生命周期。']),
  p([B('观察要点（过程，而非结论）：')]),
  bullet('系统A 面板：每个请求一条横轴 —— ' + B('橙色段') + '是在 MySQL InnoDB 行锁上排队等待（innodb_lock_wait_timeout 到点被数据库掐断），' + B('蓝色段') + '是事务处理，'
    + '点颜色代表结果（绿=成功、灰=售罄、红=超时）；'),
  bullet('重点看：库存售罄之后，仍然不断有橙色长条变成"成功"—— 这些就是超卖订单；排在队尾的请求等锁超过网关超时直接变红；'),
  bullet('系统B 面板：同样的用户，全部在到达后几十毫秒内得到结果（密集绿点），售罄请求被原子脚本瞬间拦截；'),
  bullet('实验结束后系统B 下方出现"后台落库"进度条 —— 用户早已全部拿到响应，MySQL 在慢慢追平（削峰+最终一致）。'),
  p([B('真实实测数据（200 用户 / 10 库存 / 网关超时 1000ms，本系统实跑记录）：')]),
  table([2600, 3100, 3326],
    ['指标', '系统A · 无Redis（真实MySQL直打）', '系统B · 配备Redis（真实预扣）'],
    [
      ['成交订单', '25 笔（库存只有 10 件）', '10 笔（= 库存）'],
      ['超卖', '25 件（MySQL 库存扣成 -15）', '0'],
      ['排队超时', '95 人（行锁等待 1s 被 InnoDB 掐断）', '0'],
      ['售罄拦截', '80 人（后到用户）', '190 人（瞬时拦截）'],
      ['平均响应', '646 ms（最大 1272 ms）', '21 ms（最大 52 ms，快约 30 倍）'],
      ['落库方式', '事务内即时落库', 'BRPOP 异步落库 10/10，最终一致'],
    ]),
  note('随机波动下数值会有出入，但"A 超卖 + 超时、B 零超卖 + 毫秒级"的关系是确定性成立的（InnoDB 行锁串行 + 先查后改的必然结果）。'
    + '系统A 的超卖可在 mysql 客户端用 SELECT stock FROM miaosha.goods WHERE id=\'DUEL-A\' 看到真实负数；系统B 的库存用 redis-cli GET stock:DUEL-B 验证。'),
  h2('5.3 实验二（Tab ②）：读写一致性（脏回填与延迟双删）'),
  p([B('步骤：'), '① 点击"▶ 自动剧本"观看完整故事（商家改价 → 并发旧读回填 → 缓存与 DB 值分叉 → 延迟双删兜底恢复）；'
    + '② 再用左侧"线程A（写方）""线程B（读方）"按钮手动复现：先 A 更新 DB、B 立刻读缓存（拿到旧值回填），观察右侧两个存储的值分叉变红，最后执行"延迟双删"恢复一致。']),
  note('实验台 ② 的每一步都是真实的 Redis GET/SET/DEL 与 MySQL SELECT/UPDATE，可在 redis-cli 与 mysql 客户端同步观察。'),
  h2('5.4 实验三（Tab ③）：Redis 版秒杀内部细节'),
  p([B('步骤：'), '① 选择"Lua 原子模式"，点"开始压测"（100 并发抢 10 件）—— 成功数 = 库存、零超卖；'
    + '② 切换到"无锁对照模式"再压测 —— 成功数远超库存、库存扣成负数（超卖复现）；'
    + '③ 点"暂停 MQ 消费"观察队列堆积，再"立即对账"验证 Redis 与 DB 最终一致。']),
  h2('5.5 实验记录表（供演示时填写）'),
  table([2800, 2100, 2100, 2026],
    ['记录项', '第 1 次实验', '第 2 次实验', '第 3 次实验'],
    [
      ['实验参数（用户数/库存/超时）', '', '', ''],
      ['A 成交 / 超卖 / 超时', '', '', ''],
      ['A 平均响应 (ms)', '', '', ''],
      ['B 成交 / 超卖', '', '', ''],
      ['B 平均响应 (ms)', '', '', ''],
      ['B 后台落库完成情况', '', '', ''],
    ]),

  /* ============ 第六章 ============ */
  h1('六、部署篇：真实组件安装与启动'),
  h2('6.1 组件清单与目录结构'),
  table([2800, 3400, 2826],
    ['组件', '版本与获取方式', '本系统位置'],
    [
      ['Redis for Windows', '5.0.14.1（tporadowski 移植版，免安装 zip）', 'bin\\redis\\'],
      ['MySQL Community Server', '8.0.28（免安装 zip 版）', 'bin\\mysql\\'],
      ['Node.js', '18+（需已安装并加入 PATH）', '系统外'],
      ['npm 依赖', 'ioredis、mysql2、docx（仅文档生成用）', 'package.json'],
    ]),
  gap(),
  h2('6.2 首次部署步骤'),
  code([
    '① 解压 Redis 与 MySQL 的 zip 到 miaosha-demo\\bin\\ 下',
    '② 初始化 MySQL 数据目录（仅首次，root 无密码，仅监听本机）：',
    '   bin\\mysql\\bin\\mysqld.exe --initialize-insecure ^',
    '     --basedir=%cd%\\bin\\mysql --datadir=%cd%\\bin\\mysql\\data',
    '③ 安装 Node 依赖：',
    '   npm install',
    '④ 双击 start-all.bat（或按 5.1 方式二手动分步启动）',
  ]),
  h2('6.3 启动验证（演示前的检查清单）'),
  code([
    '# Redis 存活',
    'bin\\redis\\redis-cli.exe -h 127.0.0.1 -p 6379 ping     # 期望 PONG',
    '',
    '# MySQL 存活与数据',
    'bin\\mysql\\bin\\mysql.exe --host=127.0.0.1 -u root ^',
    '  -e "SELECT VERSION(); SHOW VARIABLES LIKE \'max_connections\';"',
    '',
    '# 演示系统（页面右上角徽章应显示真实版本号）',
    '#   ● Redis 5.0.14.1 + MySQL 8.0.28 · MQ消费中',
    '',
    '# 实验后核对真实数据（对照实验系统A/B）：',
    'mysql> SELECT stock FROM miaosha.goods WHERE id IN (\'DUEL-A\',\'DUEL-B\');',
    'redis-cli> MGET stock:DUEL-B stock:P001',
  ]),
  h2('6.4 关键配置说明（bin\\redis-demo.conf 与 mysql-init.ini）'),
  table([2600, 3400, 3026],
    ['配置项', '取值', '原因'],
    [
      ['Redis save / appendonly', 'save "" / appendonly no', '演示为纯内存模式，避免 RDB 落盘干扰（生产按需开启持久化）'],
      ['MySQL max_connections', '300（默认 151）', '200 并发实验的连接池(120)+管理连接余量；默认值会被瞬时打满报 errno 1040'],
      ['MySQL skip-log-bin', '开启', '演示无需复制/回档，免 binlog 磁盘增长'],
      ['MySQL character-set-server', 'utf8mb4', '中文商品名/订单状态正常存储'],
      ['port / bind-address', '3306 / 127.0.0.1、6379 / 127.0.0.1', '两个组件均只监听本机，root 无密码仅限演示环境'],
    ]),
  h2('6.5 测试脚本（回归验收）'),
  code([
    'node test-smoke.js   # 14 项全链路冒烟：环境自检/单发重复/Lua压测/最终一致/超卖复现/延迟双删/对账',
    'node test-duel.js    # 对照实验断言：A 超卖+超时、B 零超卖+毫秒级、异步落库 8 项',
  ]),
  h2('6.6 已知坑与排查（开发实录）'),
  table([2800, 6226],
    ['现象', '原因与解决'],
    [
      ['200 并发实验整体卡死，A 侧一个请求都不完成', 'MySQL 默认 max_connections=151 被连接池打满，errno 1040；mysql2 连接池对建连失败的处理会挂起等待方。解决：调大 max_connections=300、池上限降到 120'],
      ['innodb_lock_wait_timeout 报 Incorrect argument type', '该变量只接受整数秒，0.6 之类小数直接报错；低于 1s 的网关超时按 1s 生效'],
      ['BRPOP 期间其它 Redis 命令全部卡 2 秒', '阻塞命令占住了共享连接。解决：消费者用 redis.duplicate() 独立连接'],
      ['重置实验报 Table doesn\'t exist', 'TRUNCATE = DROP+CREATE 有瞬时"表不存在"窗口，并发落库会撞上。解决：演示重置改用 DELETE FROM'],
      ['服务启动报 ECONNREFUSED 但组件其实已起', '启动竞态。解决：server.js 初始化改为轮询重试（每秒 1 次，最多 30 次），并用 SELECT 1 做真实连通性检查'],
    ]),
];

/* ---------- 组装 ---------- */
const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, color: '1F4E79', font: FONT },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0, keepNext: false, keepLines: false } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, color: '2E5E8C', font: FONT },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1, keepNext: false, keepLines: false } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 23, bold: true, color: '333333', font: FONT },
        paragraph: { spacing: { before: 160, after: 100 }, outlineLevel: 2, keepNext: false, keepLines: false } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets',
        levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 620, hanging: 300 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: ['第 ', PageNumber.CURRENT, ' 页'], size: 18, color: '888888' })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = '内存数据库读写一致性-秒杀演示系统-技术说明文档.docx';
  fs.writeFileSync(out, buf);
  console.log('已生成:', out, `(${(buf.length / 1024).toFixed(1)} KB)`);
});
