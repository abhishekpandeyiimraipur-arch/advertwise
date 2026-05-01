-- =====================================================================
-- SCRIPT: circuit_breaker.lua
-- PURPOSE: State machine for API provider health routing.
-- KEYS[1]: cb:{provider} (e.g., cb:groq, cb:fal)
-- ARGV[1]: action ('check' | 'record_success' | 'record_failure')
-- ARGV[2]: failure_threshold (e.g., 5 errors)
-- ARGV[3]: window_seconds (e.g., 60s cooldown)
-- ARGV[4]: half_open_probe_count (e.g., 3 test requests)
-- RETURNS: 'closed' (healthy), 'open' (failing), 'half_open' (testing)
-- =====================================================================

local state = redis.call('HGET', KEYS[1], 'state') or 'closed'
local failures = tonumber(redis.call('HGET', KEYS[1], 'failures')) or 0
local opened_at = tonumber(redis.call('HGET', KEYS[1], 'opened_at')) or 0
local now = tonumber(redis.call('TIME')[1])

-- ACTION: CHECK BEFORE ROUTING
if ARGV[1] == 'check' then
    -- If open, see if the cooldown window has expired
    if state == 'open' and (now - opened_at) > tonumber(ARGV[3]) then
        -- Transition to half-open to test the provider
        redis.call('HSET', KEYS[1], 'state', 'half_open', 'probes_remaining', ARGV[4])
        return 'half_open'
    end
    return state

-- ACTION: RECORD SUCCESSFUL API CALL
elseif ARGV[1] == 'record_success' then
    if state == 'half_open' then
        -- Subtract one from the test probe count
        local remaining = tonumber(redis.call('HINCRBY', KEYS[1], 'probes_remaining', -1))
        if remaining <= 0 then
            -- Tests passed. Close the breaker (healthy again).
            redis.call('HMSET', KEYS[1], 'state', 'closed', 'failures', 0, 'opened_at', 0)
            return 'closed'
        end
    elseif state == 'closed' then
        -- Reset failure count on a successful call
        redis.call('HSET', KEYS[1], 'failures', 0)
    end
    return state

-- ACTION: RECORD API TIMEOUT OR 5xx ERROR
elseif ARGV[1] == 'record_failure' then
    local new_failures = tonumber(redis.call('HINCRBY', KEYS[1], 'failures', 1))
    
    -- If we hit the threshold, open the breaker
    if new_failures >= tonumber(ARGV[2]) and state ~= 'open' then
        redis.call('HMSET', KEYS[1], 'state', 'open', 'opened_at', now)
        return 'open'
    end
    return state
end
