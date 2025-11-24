import pytest
import json
import io
import logging
from unittest.mock import patch
from structura_log import StructuraLogger
from structura_log.contrib import fastapi


# Helper function to configure a logger for testing with StringIO
@pytest.fixture
def test_logger():
    log_output = io.StringIO()
    # Unique service name for each logger to ensure isolation
    test_handler = logging.StreamHandler(log_output)
    logger = StructuraLogger(
        service_name="test-fastapi-service",
        log_level="DEBUG",
        worker_id="test-fastapi-worker",
        handlers=[test_handler],
    )

    try:
        yield logger, log_output
    finally:
        # Cleanup: stop the listener.
        logger.shutdown()


@patch("socket.gethostname", return_value="test-host")
def test_api_request_log(mock_gethostname, test_logger):
    """
    Verifica che fastapi.api_request logghi correttamente le richieste API.
    """
    logger, log_output = test_logger

    fastapi.api_request(
        logger,
        method="GET",
        path="/users/123",
        status_code=200,
        duration_ms=150.5,
        request_id="req-1",
        user_id="user-456",
        trace_id="trace-789",
        extra_data="some_value",
    )

    logged_line = log_output.getvalue().strip()
    log_data = json.loads(logged_line)

    assert log_data["event"] == "api_request"
    assert log_data["message"] == "GET /users/123 -> 200"
    assert log_data["status"] == "success"
    assert log_data["levelname"] == "INFO"
    assert log_data["method"] == "GET"
    assert log_data["path"] == "/users/123"
    assert log_data["status_code"] == 200
    assert log_data["duration_ms"] == 150.5
    assert log_data["request_id"] == "req-1"
    assert log_data["user_id"] == "user-456"
    assert log_data["trace_id"] == "trace-789"
    assert log_data["extra_data"] == "some_value"
    assert log_data["service"] == "test-fastapi-service"


@patch("socket.gethostname", return_value="test-host")
def test_api_request_error_log(mock_gethostname, test_logger):
    """
    Verifica che fastapi.api_request logghi correttamente le richieste API con errori.
    """
    logger, log_output = test_logger

    fastapi.api_request(
        logger,
        method="POST",
        path="/items",
        status_code=500,
        request_id="req-2",
        trace_id="trace-abc",
    )

    logged_line = log_output.getvalue().strip()
    log_data = json.loads(logged_line)

    assert log_data["event"] == "api_request"
    assert log_data["message"] == "POST /items -> 500"
    assert log_data["status"] == "error"
    assert log_data["levelname"] == "WARNING"  # 500 should be WARNING
    assert log_data["status_code"] == 500
    assert log_data["request_id"] == "req-2"
    assert log_data["trace_id"] == "trace-abc"


@patch("socket.gethostname", return_value="test-host")
def test_db_query_log(mock_gethostname, test_logger):
    """
    Verifica che fastapi.db_query logghi correttamente le query database.
    """
    logger, log_output = test_logger

    fastapi.db_query(
        logger,
        query_type="SELECT",
        table="users",
        duration_ms=25.0,
        request_id="req-3",
        trace_id="trace-def",
    )
    logger.force_flush()
    logged_line = log_output.getvalue().strip()
    log_data = json.loads(logged_line)

    assert log_data["event"] == "db_query"
    assert log_data["message"] == "DB SELECT on users"
    assert log_data["status"] == "ok"
    assert log_data["levelname"] == "DEBUG"
    assert log_data["query_type"] == "SELECT"
    assert log_data["table"] == "users"
    assert log_data["duration_ms"] == 25.0
    assert log_data["request_id"] == "req-3"
    assert log_data["trace_id"] == "trace-def"


@patch("socket.gethostname", return_value="test-host")
def test_db_query_slow_log(mock_gethostname, test_logger):
    """
    Verifica che fastapi.db_query logghi correttamente le query lente.
    """
    logger, log_output = test_logger

    fastapi.db_query(
        logger,
        query_type="UPDATE",
        table="products",
        duration_ms=1200.0,  # Slow query
        request_id="req-4",
        trace_id="trace-ghi",
    )

    logged_line = log_output.getvalue().strip()
    log_data = json.loads(logged_line)

    assert log_data["event"] == "db_query"
    assert log_data["message"] == "DB UPDATE on products"
    assert log_data["status"] == "slow"
    assert log_data["levelname"] == "WARNING"  # Slow query should be WARNING
    assert log_data["duration_ms"] == 1200.0
    assert log_data["trace_id"] == "trace-ghi"


@patch("socket.gethostname", return_value="test-host")
def test_auth_event_success_log(mock_gethostname, test_logger):
    """
    Verifica che fastapi.auth_event logghi correttamente gli eventi di autenticazione riusciti.
    """
    logger, log_output = test_logger

    fastapi.auth_event(
        logger,
        event_type="login",
        username="testuser",
        success=True,
        request_id="req-5",
        trace_id="trace-jkl",
    )

    logged_line = log_output.getvalue().strip()
    log_data = json.loads(logged_line)

    assert log_data["event"] == "auth_login"
    assert log_data["message"] == "Authentication login for testuser"
    assert log_data["status"] == "success"
    assert log_data["levelname"] == "INFO"
    assert log_data["username"] == "testuser"
    assert log_data["trace_id"] == "trace-jkl"


@patch("socket.gethostname", return_value="test-host")
def test_auth_event_failure_log(mock_gethostname, test_logger):
    """
    Verifica che fastapi.auth_event logghi correttamente gli eventi di autenticazione falliti.
    """
    logger, log_output = test_logger

    fastapi.auth_event(
        logger,
        event_type="login",
        username="failed_user",
        success=False,
        request_id="req-6",
        trace_id="trace-mno",
    )

    logged_line = log_output.getvalue().strip()
    log_data = json.loads(logged_line)

    assert log_data["event"] == "auth_login"
    assert log_data["message"] == "Authentication login for failed_user"
    assert log_data["status"] == "failed"
    assert log_data["levelname"] == "WARNING"  # Failed login should be WARNING
    assert log_data["username"] == "failed_user"
    assert log_data["trace_id"] == "trace-mno"
