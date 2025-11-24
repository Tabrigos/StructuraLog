import json
import io
import logging
from unittest.mock import patch
from structura_log import StructuraLogger


@patch("socket.gethostname", return_value="test-host")
def test_log_output_format_and_fields(mock_gethostname):
    """
    Verifica che il logger generi un output JSON valido e contenga
    i campi essenziali, inclusi i campi custom.
    """
    log_output = io.StringIO()
    test_handler = logging.StreamHandler(log_output)
    logger = StructuraLogger(
        service_name="test-service",
        log_level="INFO",
        worker_id="test-worker",
        handlers=[test_handler],
    )

    # The formatter will be set by StructuraLogger's __init__
    try:
        # Emette vari tipi di log per testare formattazione e filtraggio
        logger.info(
            "user_login", "User logged in", user_id="user-123", session_id="abc-xyz"
        )
        logger.warning("data_integrity", "Checksum mismatch", file_name="data.csv")
        logger.debug(
            "internal_debug", "Debug message", detail="verbose info"
        )  # Non dovrebbe apparire con INFO level

        # Leggi e verifica l'output
        logged_lines = log_output.getvalue().strip().split("\n")
        # Ci aspettiamo 2 log (INFO e WARNING), il DEBUG dovrebbe essere filtrato
        assert len(logged_lines) == 2

        # Verifica il log INFO
        info_log = json.loads(logged_lines[0])
        assert info_log["levelname"] == "INFO"  # MODIFIED
        assert info_log["message"] == "User logged in"
        assert info_log["service"] == "test-service"
        assert info_log["worker_id"] == "test-worker"
        assert info_log["event"] == "user_login"
        assert info_log["status"] == "info"
        assert info_log["user_id"] == "user-123"
        assert info_log["session_id"] == "abc-xyz"
        assert "asctime" in info_log

        # Verifica il log WARNING
        warning_log = json.loads(logged_lines[1])
        assert warning_log["levelname"] == "WARNING"  # MODIFIED
        assert warning_log["message"] == "Checksum mismatch"
        assert warning_log["event"] == "data_integrity"
        assert warning_log["file_name"] == "data.csv"

    finally:
        logger.shutdown()
