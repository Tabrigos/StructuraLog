import pytest
import json
import io
import logging
from unittest.mock import patch
from structura_log import StructuraLogger, JobLogger


# Helper function to configure a logger for testing with StringIO
@pytest.fixture
def test_logger():
    log_output = io.StringIO()
    # Unique service name for each logger to ensure isolation
    test_handler = logging.StreamHandler(log_output)
    logger = StructuraLogger(
        service_name="test-job-service",
        log_level="INFO",
        worker_id="test-job-worker",
        handlers=[test_handler],
    )

    try:
        yield logger, log_output
    finally:
        # Cleanup: stop the listener.
        logger.shutdown()


@patch("socket.gethostname", return_value="test-host")
def test_job_logger_success(mock_gethostname, test_logger):
    """
    Verifica il comportamento di JobLogger per un job che completa con successo.
    """
    logger, log_output = test_logger

    with JobLogger(logger, event="data_processing", custom_param="value") as job:
        job.info("step_start", "Starting processing step A")
        job.progress(step="step_A", progress=50)
        job.info("step_end", "Finished processing step A")
        job.set_final_data({"records_processed": 100})

    logged_lines = log_output.getvalue().strip().split("\n")

    assert (
        len(logged_lines) == 5
    )  # job_started, step_start, job_progress, step_end, job_completed

    started_log = json.loads(logged_lines[0])
    assert started_log["event"] == "data_processing"  # MODIFIED
    assert started_log["status"] == "running"
    assert started_log["custom_param"] == "value"
    assert "job_id" in started_log
    assert "trace_id" in started_log
    assert started_log["service"] == "test-job-service"

    progress_log = json.loads(logged_lines[2])
    assert progress_log["event"] == "job_progress"
    assert progress_log["status"] == "running"
    assert progress_log["step"] == "step_A"
    assert progress_log["progress"] == 50
    assert progress_log["job_id"] == started_log["job_id"]
    assert progress_log["trace_id"] == started_log["trace_id"]
    assert progress_log["service"] == "test-job-service"

    completed_log = json.loads(logged_lines[4])
    assert completed_log["event"] == "job_completed"
    assert completed_log["status"] == "success"
    assert completed_log["job_id"] == started_log["job_id"]
    assert completed_log["trace_id"] == started_log["trace_id"]
    assert "duration_ms" in completed_log
    assert completed_log["records_processed"] == 100
    assert completed_log["service"] == "test-job-service"


@patch("socket.gethostname", return_value="test-host")
def test_job_logger_failure(mock_gethostname, test_logger):
    """
    Verifica il comportamento di JobLogger per un job che fallisce a causa di un'eccezione.
    """
    logger, log_output = test_logger

    with pytest.raises(ValueError):
        with JobLogger(logger, event="data_processing_failure") as job:
            job.info("step_start", "Starting processing that will fail")
            raise ValueError("Simulated processing error")
            # This should not be reached/logged after the exception
            job.info("this_should_not_be_logged", "This step is skipped")

    logged_lines = log_output.getvalue().strip().split("\n")

    # Expected logs: job_started, step_start, job_failed (error from __exit__)
    assert len(logged_lines) == 3

    started_log = json.loads(logged_lines[0])
    assert started_log["event"] == "data_processing_failure"  # MODIFIED
    assert started_log["status"] == "running"
    assert started_log["service"] == "test-job-service"

    failed_log = json.loads(logged_lines[2])
    assert failed_log["event"] == "job_failed"
    assert failed_log["status"] == "failed"
    assert failed_log["levelname"] == "ERROR"  # MODIFIED
    assert failed_log["message"] == "Simulated processing error"
    assert failed_log["error_type"] == "ValueError"
    assert failed_log["job_id"] == started_log["job_id"]
    assert failed_log["trace_id"] == started_log["trace_id"]
    assert "duration_ms" in failed_log
    assert failed_log["service"] == "test-job-service"


@patch("socket.gethostname", return_value="test-host")
def test_job_logger_custom_job_trace_id(mock_gethostname, test_logger):
    """
    Verifica che JobLogger utilizzi job_id e trace_id forniti.
    """
    logger, log_output = test_logger
    custom_job_id = "my-custom-job-id-123"
    custom_trace_id = "my-custom-trace-id-abc"

    with JobLogger(
        logger, event="custom_ids_test", job_id=custom_job_id, trace_id=custom_trace_id
    ) as job:
        job.info("progress", "Doing work with custom IDs")
        assert job.job_id == custom_job_id
        assert job.trace_id == custom_trace_id

    logged_lines = log_output.getvalue().strip().split("\n")

    assert len(logged_lines) == 3  # job_started, info, job_completed

    started_log = json.loads(logged_lines[0])
    assert started_log["event"] == "custom_ids_test"  # MODIFIED
    assert started_log["job_id"] == custom_job_id
    assert started_log["trace_id"] == custom_trace_id
    assert started_log["service"] == "test-job-service"

    info_log = json.loads(logged_lines[1])
    assert info_log["event"] == "progress"
    assert info_log["job_id"] == custom_job_id
    assert info_log["trace_id"] == custom_trace_id
    assert info_log["service"] == "test-job-service"

    completed_log = json.loads(logged_lines[2])
    assert completed_log["event"] == "job_completed"
    assert completed_log["job_id"] == custom_job_id
    assert completed_log["trace_id"] == custom_trace_id
    assert completed_log["service"] == "test-job-service"
    assert "duration_ms" in completed_log
