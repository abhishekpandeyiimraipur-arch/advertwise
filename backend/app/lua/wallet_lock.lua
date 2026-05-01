-- =====================================================================
-- SCRIPT: wallet_lock.lua
-- PURPOSE: Atomically check balance and reserve 1 credit for a generation.
-- KEYS[1]: wallet:{user_id}               (The user's main wallet hash)
-- KEYS[2]: walletlock:{user_id}:{gen_id}  (The temporary lock key)
-- ARGV[1]: credits_to_lock                (Int, usually 1)
-- ARGV[2]: ttl_seconds                    (Int, usually 300)
-- RETURNS: 1 on success, 0 on insufficient funds.
-- =====================================================================

-- 1. Fetch current balance
local balance = tonumber(redis.call('HGET', KEYS[1], 'balance')) or 0
local credits = tonumber(ARGV[1])

-- 2. Guard: Ensure user can afford the operation
if balance < credits then
    return 0
end

-- 3. Idempotency Check: Is this generation already locked?
local existing = redis.call('EXISTS', KEYS[2])
if existing == 1 then
    -- Existing active lock found (e.g., network retry). Treat as success.
    return 1
end

-- 4. Atomic Deduct & Lock
-- Decrement the balance hash
redis.call('HINCRBY', KEYS[1], 'balance', -credits)
-- Create an expiring lock key to represent the reserved funds
redis.call('SET', KEYS[2], credits, 'EX', tonumber(ARGV[2]))

return 1
