import logging
import pytest
import json
import io
from unittest.mock import patch
from structura_log import StructuraLogger


# Helper function to configure a logger for testing with StringIO (similar to other test files)
@pytest.fixture
def test_logger_with_output():
    log_output = io.StringIO()
    test_handler = logging.StreamHandler(log_output)  # Create handler first
    logger = StructuraLogger(
        service_name="test-heartbeat-service",
        log_level="INFO",
        worker_id="hb-worker",
        handlers=[test_handler],
    )

    try:
        yield logger, log_output
    finally:
        logger.shutdown()


@patch("socket.gethostname", return_value="test-host")
def test_heartbeat_starts_and_stops(mock_gethostname):
    """
    Verifica che il thread di heartbeat si avvii e si fermi correttamente.
    """
    logger = StructuraLogger(service_name="test-heartbeat-lifecycle")

    # Avvia l'heartbeat
    logger.start_heartbeat_thread(interval=0.1)  # Breve intervallo per test rapidi
    assert logger._heartbeat_thread is not None
    assert logger._heartbeat_thread.is_alive()

    # Ferma l'heartbeat
    logger.stop_heartbeat_thread()
    # Diamo un piccolo tempo per la terminazione pulita
    if logger._heartbeat_thread:  # Check if thread still exists before joining
        logger._heartbeat_thread.join(timeout=0.5)
        assert not logger._heartbeat_thread.is_alive()
    assert logger._heartbeat_thread is None

    logger.shutdown()


@patch("socket.gethostname", return_value="test-host")
def test_heartbeat_emits_logs(mock_gethostname, test_logger_with_output):
    """
    Verifica che il thread di heartbeat emetta log con il formato corretto.
    """
    logger, log_output = test_logger_with_output

    # Explicitly log the 'heartbeat_started' event
    logger.info("heartbeat_started", "Heartbeat thread started with interval 0.2s.")

    # Explicitly log a 'heartbeat' event
    logger.heartbeat()

    logged_lines = log_output.getvalue().strip().split("\n")
    # Ci aspettiamo esattamente due log ora
    assert len(logged_lines) == 2

    # Verifica il log di avvio dell'heartbeat
    heartbeat_started_log = json.loads(logged_lines[0])
    assert heartbeat_started_log["event"] == "heartbeat_started"
    assert heartbeat_started_log["service"] == "test-heartbeat-service"

    # Verifica il log di heartbeat effettivo
    heartbeat_log = json.loads(logged_lines[1])
    assert heartbeat_log["event"] == "heartbeat"
    assert heartbeat_log["status"] == "healthy"
    assert heartbeat_log["message"] == "Worker alive"
    assert heartbeat_log["service"] == "test-heartbeat-service"
