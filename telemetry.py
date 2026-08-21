import logging
import asyncio
import json
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
    """Log audit metrics asynchronously in the background."""
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
        
        # Fix: Now properly dumping the constructed payload into the log output
        logger.info(
            f"AUDIT COMPLETED | Domain: {domain} | Score: {overall_score} "
            f"| Exec Time: {execution_time_seconds:.2f}s | Payload: {json.dumps(telemetry_payload)}"
        )
    except Exception as e:
        logger.error(f"Telemetry logging failed for {domain}: {e}")