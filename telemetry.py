import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrillokaTelemetry")


async def log_telemetry_async(
    domain: str,
    business_type: str,
    audit_data: Dict[str, Any],
    overall_score: float,
    execution_time_seconds: float
):
    """Logs audit metrics asynchronously in the background."""
    try:
        await asyncio.sleep(0.01)
        
        telemetry_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": domain,
            "business_type": business_type,
            "overall_score": overall_score,
            "total_checkpoints": audit_data.get("total_checkpoints_evaluated", 50),
            "execution_time_sec": round(execution_time_seconds, 2)
        }
        
        logger.info(f"AUDIT COMPLETED | Domain: {domain} | Score: {overall_score} | Exec Time: {execution_time_seconds:.2f}s")
    except Exception as e:
        logger.error(f"Telemetry logging failed for {domain}: {e}")