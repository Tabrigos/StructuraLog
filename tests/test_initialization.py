import logging
import os
import json
import io
from unittest.mock import patch

import pytest

from structura_log.core import StructuraLogger


@pytest.fixture
def string_io_handler():
    """Fixture to create an in-memory log output stream."""
    log_output = io.StringIO()
    handler = logging.StreamHandler(log_output)
    return handler, log_output


def test_logger_uses_environment_variables_as_fallback(string_io_handler):
    """
    Verifica che StructuraLogger utilizzi le variabili d'ambiente SERVICE e POD_NAME
    quando i parametri non sono forniti esplicitamente.
    """
    handler, log_output = string_io_handler
    env_vars = {"SERVICE": "my-env-service", "POD_NAME": "my-env-pod"}

    with patch.dict(os.environ, env_vars, clear=True):
        # Inizializza il logger senza passare service_name e worker_id
        logger = StructuraLogger(handlers=[handler])
        assert logger.service_name == "my-env-service"
        assert logger.worker_id == "my-env-pod"

        # Esegui un log per verificare che i valori siano usati nell'output
        logger.info("test_event", "Test message")

    log_content = log_output.getvalue()
    log_json = json.loads(log_content)

    assert log_json["service"] == "my-env-service"
    assert log_json["worker_id"] == "my-env-pod"


def test_constructor_arguments_override_environment_variables(string_io_handler):
    """
    Verifica che gli argomenti passati al costruttore abbiano la precedenza
    sulle variabili d'ambiente.
    """
    handler, log_output = string_io_handler
    env_vars = {"SERVICE": "my-env-service", "POD_NAME": "my-env-pod"}

    with patch.dict(os.environ, env_vars, clear=True):
        # Inizializza il logger passando valori espliciti
        logger = StructuraLogger(
            service_name="explicit-service",
            worker_id="explicit-worker",
            handlers=[handler],
        )
        assert logger.service_name == "explicit-service"
        assert logger.worker_id == "explicit-worker"

        # Esegui un log per verificare che i valori espliciti siano usati
        logger.info("test_event", "Test message")

    log_content = log_output.getvalue()
    log_json = json.loads(log_content)

    assert log_json["service"] == "explicit-service"
    assert log_json["worker_id"] == "explicit-worker"


def test_default_values_are_used_when_no_args_or_env_vars(string_io_handler):
    """
    Verifica che i valori di default ("my-service" e l'hostname) siano usati
    quando non vengono forniti né argomenti né variabili d'ambiente.
    """
    handler, log_output = string_io_handler
    
    # Assicurati che le variabili d'ambiente siano pulite
    with patch.dict(os.environ, {}, clear=True):
        with patch("socket.gethostname", return_value="test-hostname") as mock_hostname:
            logger = StructuraLogger(handlers=[handler])
            
            assert logger.service_name == "my-service"
            assert logger.worker_id == "test-hostname"
            mock_hostname.assert_called_once()
            
            # Esegui un log per verificare i valori di default nell'output
            logger.info("test_event", "Test message")

    log_content = log_output.getvalue()
    log_json = json.loads(log_content)

    assert log_json["service"] == "my-service"
    assert log_json["worker_id"] == "test-hostname"


def test_shutdown_is_idempotent():
    """
    Verifica che chiamare shutdown() più volte non causi errori.
    """
    # Usa il logger di default (asincrono)
    logger = StructuraLogger()
    try:
        logger.shutdown()
        logger.shutdown()
        # La seconda chiamata non deve sollevare eccezioni
    except Exception as e:
        pytest.fail(f"La seconda chiamata a shutdown() ha sollevato un'eccezione: {e}")

    # Test anche con un logger sincrono (con handler custom)
    logger_sync = StructuraLogger(handlers=[logging.NullHandler()])
    try:
        logger_sync.shutdown()
        logger_sync.shutdown()
    except Exception as e:
        pytest.fail(
            f"La seconda chiamata a shutdown() su un logger sincrono ha sollevato un'eccezione: {e}"
        )
