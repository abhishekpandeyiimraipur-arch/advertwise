-- =====================================================================
-- SCRIPT: wallet_refund.lua
-- PURPOSE: Return locked credits back to the user's balance on error.
-- KEYS[1]: wallet:{user_id}
-- KEYS[2]: walletlock:{user_id}:{gen_id}
-- RETURNS: 1 on refund applied, 0 if nothing to refund.
-- =====================================================================

-- 1. Find the active lock
local locked = redis.call('GET', KEYS[2])
if locked == false then
    -- Nothing is locked, so there is nothing to refund
    return 0
end

local credits = tonumber(locked)

-- 2. Execute Refund
-- Give the credits back to the main balance
redis.call('HINCRBY', KEYS[1], 'balance', credits)
-- Destroy the lock
redis.call('DEL', KEYS[2])

return 1
