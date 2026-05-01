-- =====================================================================
-- SCRIPT: wallet_consume.lua
-- PURPOSE: Finalize a transaction after successful video generation.
-- KEYS[1]: wallet:{user_id}
-- KEYS[2]: walletlock:{user_id}:{gen_id}
-- RETURNS: 1 on success, 0 if no active lock exists.
-- =====================================================================

-- 1. Verify the lock still exists
local locked = redis.call('GET', KEYS[2])
if locked == false then
    -- Lock expired or was already consumed/refunded
    return 0
end

-- 2. Consume the lock
-- Delete the temporary lock key
redis.call('DEL', KEYS[2])
-- Increment the lifetime consumed tracking metric
redis.call('HINCRBY', KEYS[1], 'consumed_total', tonumber(locked))

return 1
