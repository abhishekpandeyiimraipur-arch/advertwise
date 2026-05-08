from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class PreCheckResult:
    def __init__(self, ok: bool, current_cogs: Decimal, projected: Decimal):
        self.ok = ok
        self.current_cogs = current_cogs
        self.projected = projected

class CostGuard:
    """
    The Financial Firewall.
    Ensures the 15-second rendering logic and AI chat loops never bankrupt the system.
    """
    
    # Strict PRD unit economic ceilings in INR
    CEILING = {
        "starter": Decimal("2.00"),    # Highly bounded
        "essential": Decimal("10.00"), # Standard 15s fractional render allowance
        "pro": Decimal("14.00")        # Buffer for premium Wan2.2 models
    }

    def __init__(self, redis_db2, db_pool):
        self.redis_db2 = redis_db2
        self.db = db_pool

    # ── BLOCK 1: PREDICTIVE GATE (Before execution) ──
    async def pre_check(self, gen_id: str, est_cost: float, plan_tier: str) -> PreCheckResult:
        """
        Circuit breaker for user actions.
        Prevents API dispatch if the estimated cost will push the total over the ceiling.
        """
        key = f"cogs:{gen_id}"
        # Fetch current accumulated spend from fast cache
        current_val = await self.redis_db2.hget(key, "total")
        current = Decimal(current_val or "0")
        ceiling = self.CEILING.get(plan_tier, Decimal("0.0"))
        
        projected = current + Decimal(str(est_cost))
        ok = projected <= ceiling
        
        return PreCheckResult(ok=ok, current_cogs=current, projected=projected)

    # ── BLOCK 2: IMMUTABLE LEDGER (After execution) ──
    async def record(self, gen_id: str, cost_inr: float, worker: str, model_used: str) -> None:
        """
        Records the actual API cost. 
        MUST fire regardless of safety/output validation so we don't bleed hidden tokens.
        """
        key = f"cogs:{gen_id}"
        
        # 1. Update Redis (Fast path for subsequent pre_checks)
        await self.redis_db2.hincrbyfloat(key, "total", float(cost_inr))
        await self.redis_db2.expire(key, 24 * 3600)
        
        # 2. Update Postgres (Immutable Audit Log for Billing/Analytics)
        async with self.db.acquire() as conn:
            await conn.execute(
                """INSERT INTO agent_traces (gen_id, worker, model_used, cost_inr, selection_reason) 
                   VALUES ($1, $2, $3, $4, $5)""", 
                gen_id, worker, model_used, Decimal(str(cost_inr)), f"{worker} via {model_used}"
            )

    # ── BLOCK 3: POST-HOC AUDIT (End of lifecycle) ──
    async def check_post_hoc(self, gen_id: str) -> None:
        """
        Called by phase4_coordinator after the final 15s video preview is ready. 
        Graceful Degradation: If COGS overshoots due to fallbacks, we DO NOT block 
        the user. We emit an alert for engineering to tune the routing weights.
        """
        async with self.db.acquire() as conn:
            gen = await conn.fetchrow("SELECT cogs_total, plan_tier FROM generations WHERE gen_id=$1", gen_id)
        if not gen: return
            
        ceiling = self.CEILING.get(gen["plan_tier"], Decimal("0.0"))
        actual_cost = Decimal(str(gen["cogs_total"]))
        
        if actual_cost > ceiling:
            # In a real system, we'd emit to Prometheus here
            logger.warning(
                f"COGS OVERSHOOT | gen={gen_id} | actual={actual_cost} INR | ceiling={ceiling} INR"
            )
