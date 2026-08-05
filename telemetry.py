import os
import logging
from fastapi import APIRouter, Header, HTTPException, status

logger = logging.getLogger(__name__)

telemetry_router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


def _verify_admin_access(auth_header: str | None):
    """
    Verifies that the incoming Authorization header matches the expected secret admin token.
    Raises HTTPException 401 if missing or invalid.
    """
    expected_token = os.getenv("ADMIN_TOKEN_ENV_VAR")

    if not expected_token:
        logger.error("ADMIN_TOKEN_ENV_VAR is not configured in the environment.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin access is disabled due to missing server configuration."
        )

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header."
        )

    token = auth_header.replace("Bearer ", "").strip()
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrative credentials."
        )


def log_telemetry_async(domain: str, biz_type: str, audit_data: dict, score: float, synthetic_index: float):
    """
    Asynchronously records audit telemetry metrics for backend tracking.
    """
    try:
        logger.info(f"[TELEMETRY] Domain: {domain} | BizType: {biz_type} | Score: {score} | AI Index: {synthetic_index}")
    except Exception as e:
        logger.error(f"[TELEMETRY ERROR] Failed to record telemetry: {str(e)}")


@telemetry_router.get("/health")
async def telemetry_health_check(authorization: str | None = Header(None)):
    """
    Protected endpoint to verify system telemetry and administrative access status.
    """
    _verify_admin_access(authorization)
    return {
        "status": "healthy",
        "telemetry_active": True,
        "access": "granted"
    }