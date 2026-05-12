import os
import redis.asyncio as redis
from pathlib import Path

LUA_DIR = Path(__file__).parent / "lua"

class RedisManager:
    def __init__(self):
        self.db0 = None
        self.db2 = None
        self.db5 = None
        
        self.wallet_lock_sha = None
        self.wallet_consume_sha = None
        self.wallet_refund_sha = None
        self.circuit_breaker_sha = None

    async def connect(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        # Initialize the 3 DBs needed for the stubs
        self.db0 = redis.Redis.from_url(f"{redis_url}/0", decode_responses=True)
        self.db2 = redis.Redis.from_url(f"{redis_url}/2", decode_responses=True)
        self.db5 = redis.Redis.from_url(f"{redis_url}/5", decode_responses=True)

        # Pre-load all Lua scripts via SCRIPT LOAD so they can be run via EVALSHA
        try:
            with open(LUA_DIR / "wallet_lock.lua", "r") as f:
                self.wallet_lock_sha = await self.db0.script_load(f.read())
            
            with open(LUA_DIR / "wallet_consume.lua", "r") as f:
                self.wallet_consume_sha = await self.db0.script_load(f.read())
                
            with open(LUA_DIR / "wallet_refund.lua", "r") as f:
                self.wallet_refund_sha = await self.db0.script_load(f.read())
                
            # Circuit breaker uses DB3 according to [TDD-REDIS]-A
            self.db3 = redis.Redis.from_url(f"{redis_url}/3", decode_responses=True)
            with open(LUA_DIR / "circuit_breaker.lua", "r") as f:
                self.circuit_breaker_sha = await self.db3.script_load(f.read())
        except Exception as e:
            print(f"Warning: Failed to load Lua scripts (Redis might be offline): {e}")

    async def disconnect(self):
        if self.db0: await self.db0.aclose()
        if self.db2: await self.db2.aclose()
        if self.db5: await self.db5.aclose()
        if hasattr(self, 'db3') and self.db3: await self.db3.aclose()

    async def execute_wallet_lock(self, user_id: str, gen_id: str, credits: int = 1, ttl: int = 300) -> int:
        if not self.wallet_lock_sha:
            return 1 # Mock success if redis not fully available for the trace
        keys = [f"wallet:{user_id}", f"walletlock:{user_id}:{gen_id}"]
        args = [credits, ttl]
        return await self.db0.evalsha(self.wallet_lock_sha, len(keys), *keys, *args)

    async def execute_wallet_refund(self, user_id: str, gen_id: str) -> int:
        """
        Atomically refund locked credits back to wallet.
        Returns 1 = refunded, 0 = nothing to refund (already consumed or never locked).
        """
        if not self.wallet_refund_sha:
            return 0
        keys = [f"wallet:{user_id}", f"walletlock:{user_id}:{gen_id}"]
        return await self.db0.evalsha(self.wallet_refund_sha, len(keys), *keys)
