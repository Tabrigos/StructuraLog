import logging
from ..core import StructuraLogger


def api_request(
    logger: StructuraLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float = None,
    request_id: str = None,
    user_id: str = None,
    trace_id: str = None,
    **kwargs,
):
    """Log richiesta API con metriche."""
    logger.log(
        event="api_request",
        msg=f"{method} {path} -> {status_code}",
        status="success" if 200 <= status_code < 400 else "error",
        level=logging.INFO if status_code < 400 else logging.WARNING,
        request_id=request_id,
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        trace_id=trace_id,
        **kwargs,
    )


def db_query(
    logger: StructuraLogger,
    query_type: str,
    table: str = None,
    duration_ms: float = None,
    request_id: str = None,
    trace_id: str = None,
    **kwargs,
):
    """Log query database con performance."""
    msg = f"DB {query_type}"
    if table:
        msg += f" on {table}"

    level = logging.WARNING if duration_ms and duration_ms > 1000 else logging.DEBUG

    logger.log(
        event="db_query",
        msg=msg,
        status="slow" if duration_ms and duration_ms > 1000 else "ok",
        level=level,
        request_id=request_id,
        query_type=query_type,
        table=table,
        duration_ms=duration_ms,
        trace_id=trace_id,
        **kwargs,
    )


def auth_event(
    logger: StructuraLogger,
    event_type: str,
    username: str = None,
    success: bool = True,
    request_id: str = None,
    trace_id: str = None,
    **kwargs,
):
    """Log eventi di autenticazione."""
    logger.log(
        event=f"auth_{event_type}",
        msg=f"Authentication {event_type} for {username or 'unknown'}",
        status="success" if success else "failed",
        level=logging.INFO if success else logging.WARNING,
        request_id=request_id,
        username=username,
        trace_id=trace_id,
        **kwargs,
    )
