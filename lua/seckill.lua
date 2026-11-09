-- seckill.lua —— 秒杀原子预扣（查-判-扣一口气，Redis 单线程执行期间不会插入其他命令）
-- KEYS[1] = 库存 key（stock:P001）
-- KEYS[2] = 用户去重 set（bought:P001）
-- ARGV[1] = 用户ID
-- 返回: {0,'ok'} 成功 | {1,'rate limited'} 不会出现 | {2,'duplicate'} 重复 | {3,'sold out'} 售罄
if redis.call('SISMEMBER', KEYS[2], ARGV[1]) == 1 then
  return {2, 'duplicate'}
end
local stock = tonumber(redis.call('GET', KEYS[1]) or '-1')
if stock == nil or stock <= 0 then
  return {3, 'sold out'}
end
redis.call('DECR', KEYS[1])
redis.call('SADD', KEYS[2], ARGV[1])
return {0, 'ok'}
