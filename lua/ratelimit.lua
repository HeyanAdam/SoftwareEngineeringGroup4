-- ratelimit.lua —— Redis 令牌桶限流（网关层常用写法）
-- KEYS[1] = 桶 key   ARGV: [1]容量 [2]每秒补充 [3]当前毫秒时间戳 [4]本次申请数量
-- 返回: 剩余令牌数（-1 表示被限流）
local capacity   = tonumber(ARGV[1])
local refillRate = tonumber(ARGV[2])
local now        = tonumber(ARGV[3]) / 1000
local want       = tonumber(ARGV[4])

local state = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1])
local lastTs = tonumber(state[2])
if tokens == nil then
  tokens = capacity
  lastTs = now
end

-- 按流逝时间补充令牌
local delta = math.max(0, now - lastTs)
tokens = math.min(capacity, tokens + delta * refillRate)

if tokens < want then
  redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
  return -1
end

tokens = tokens - want
redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], 60)
return tokens
