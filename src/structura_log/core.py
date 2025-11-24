import logging
import os
import queue
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import QueueHandler, QueueListener
from pythonjsonlogger.json import JsonFormatter

# ========== CLASSE PRINCIPALE DEL LOGGER ==========


class StructuraLogger:
    def __init__(
        self,
        service_name: str = None,
        worker_id: str = None,
        log_level: str = "INFO",
        log_format: str = "%(asctime)s %(levelname)s %(message)s %(service)s %(worker_id)s %(job_id)s %(event)s %(status)s %(trace_id)s",
        handlers: list[logging.Handler] | None = None,
    ):
        """
        Inizializza un'istanza del logger strutturato.

        :param service_name: Nome del servizio (default: letto da env SERVICE o "my-service").
        :param worker_id: ID del worker/istanza (default: letto da env POD_NAME o hostname).
        :param log_level: Livello minimo di logging (es. "INFO", "DEBUG", "WARNING").
        :param log_format: Formato della stringa JSON per il logger.
        """
        self.service_name = service_name or os.getenv("SERVICE", "my-service")
        self.worker_id = worker_id or os.getenv("POD_NAME", socket.gethostname())

        self.logger = logging.getLogger(f"{self.service_name}-{uuid.uuid4().hex[:6]}")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.propagate = False

        # Define the default list of fields for JSON output
        default_json_fields = [
            "asctime",
            "levelname",
            "message",
            "service",
            "worker_id",
            "job_id",
            "event",
            "status",
            "trace_id",
        ]
        # Allow overriding/extending with custom format from log_format string
        # if log_format is not the default, this indicates customisation
        if (
            log_format
            != "%(asctime)s %(levelname)s %(message)s %(service)s %(worker_id)s %(job_id)s %(event)s %(status)s %(trace_id)s"
        ):
            _formatter = JsonFormatter(log_format)
        else:
            _formatter = JsonFormatter(default_json_fields)

        if handlers is None:
            # Default production setup with asynchronous QueueHandler and QueueListener
            self._log_queue = queue.Queue(-1)
            self._queue_handler = QueueHandler(self._log_queue)
            self.logger.addHandler(self._queue_handler)

            _handler = logging.StreamHandler(sys.stdout)
            _handler.setFormatter(_formatter)
            self._queue_listener = QueueListener(self._log_queue, _handler)
            self._queue_listener.start()
        else:
            # Test setup: For synchronous logging in tests, bypass QueueHandler/Listener
            # Clear any existing handlers to ensure only test handlers are active
            if self.logger.handlers:
                for h in self.logger.handlers[
                    :
                ]:  # Iterate over a slice to safely modify list
                    self.logger.removeHandler(h)

            self._log_queue = None  # Not used in this mode
            self._queue_handler = None  # Not used in this mode
            self._queue_listener = None  # Not used in this mode (logger is synchronous)

            for h in handlers:
                if h.formatter is None:
                    h.setFormatter(_formatter)
                self.logger.addHandler(h)

        # Attributi per il thread di heartbeat
        self._heartbeat_thread = None
        self._heartbeat_stop_event = None

    def shutdown(self):
        """
        Ferma il listener della coda di logging e il thread di heartbeat, se attivo.
        """
        self.stop_heartbeat_thread()
        if self._queue_listener:  # Only stop if QueueListener was initialized
            self._queue_listener.stop()

    def force_flush(self):
        """
        Force flushes the QueueListener, ensuring all queued logs are processed.
        Useful for synchronous testing of asynchronous logging.
        """
        if self._queue_listener:
            self._queue_listener.flush()

    # ========== GESTIONE HEARTBEAT ==========

    def _emit_heartbeat(self, interval: float):
        """Funzione eseguita dal thread in background per inviare heartbeat."""
        while not self._heartbeat_stop_event.wait(interval):
            self.heartbeat()

    def start_heartbeat_thread(self, interval: int = 30):
        """
        Avvia un thread in background che invia un log di heartbeat a intervalli regolari.
        """
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return  # Evita di avviare più thread

        self._heartbeat_stop_event = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._emit_heartbeat, args=(interval,), daemon=True
        )
        self._heartbeat_thread.start()
        self.info(
            "heartbeat_started", f"Heartbeat thread started with interval {interval}s."
        )

    def stop_heartbeat_thread(self):
        """Ferma il thread di heartbeat in modo pulito."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            if self._heartbeat_stop_event:
                self._heartbeat_stop_event.set()
            self.info("heartbeat_stopped", "Heartbeat thread stopped.")
            self._heartbeat_thread.join(timeout=1.0)  # Ensure thread has time to finish
            self._heartbeat_thread = None

    # ========== METODI BASE ==========

    def log(
        self,
        event,
        msg,
        status=None,
        job_id=None,
        trace_id=None,
        level=logging.INFO,
        **kwargs,
    ):
        """
        Scrive un log JSON con i campi standard.
        """
        extra_fields = {
            "service": self.service_name,
            "worker_id": self.worker_id,
            "job_id": job_id,
            "event": event,
            "status": status,
            **kwargs,
        }
        if trace_id:
            extra_fields["trace_id"] = trace_id

        self.logger.log(
            level,
            msg,
            extra=extra_fields,
        )

    # ========== METODI SEMANTICI ==========

    def heartbeat(self, status="healthy", trace_id=None, **kwargs):
        """Log di heartbeat periodico del worker."""
        self.log(
            "heartbeat", "Worker alive", status=status, trace_id=trace_id, **kwargs
        )

    def job_started(self, job_id=None, trace_id=None, **kwargs):
        """Log avvio job con ID (generato se non passato)."""
        event_name = kwargs.pop("event", "job_started")
        if job_id is None:
            job_id = (
                f"job-{datetime.now(timezone.utc).isoformat()}-{uuid.uuid4().hex[:6]}"
            )
        if trace_id is None:
            trace_id = uuid.uuid4().hex
        self.log(
            event_name,
            "Job started",
            status="running",
            job_id=job_id,
            trace_id=trace_id,
            **kwargs,
        )
        return job_id, trace_id

    def job_progress(self, job_id, step=None, progress=None, trace_id=None, **kwargs):
        """Log progresso job."""
        msg = (
            f"Job progress: {progress}%" if progress is not None else "Job in progress"
        )
        self.log(
            "job_progress",
            msg,
            status="running",
            job_id=job_id,
            step=step,
            progress=progress,
            trace_id=trace_id,
            **kwargs,
        )

    def job_completed(self, job_id, duration_ms=None, trace_id=None, **kwargs):
        """Log completamento job."""
        self.log(
            "job_completed",
            "Job completed",
            status="success",
            job_id=job_id,
            duration_ms=duration_ms,
            trace_id=trace_id,
            **kwargs,
        )

    def job_failed(self, job_id, error: Exception, trace_id=None, **kwargs):
        """Log fallimento job con stacktrace minimale."""
        self.log(
            "job_failed",
            str(error),
            status="failed",
            job_id=job_id,
            level=logging.ERROR,
            error_type=type(error).__name__,
            trace_id=trace_id,
            **kwargs,
        )

    # ========== ALTRI METODI UTILI ==========

    def info(self, event, msg, job_id=None, trace_id=None, **kwargs):
        """Log informativo generico."""
        self.log(
            event,
            msg,
            status="info",
            job_id=job_id,
            level=logging.INFO,
            trace_id=trace_id,
            **kwargs,
        )

    def warning(self, event, msg, job_id=None, trace_id=None, **kwargs):
        """Log warning generico."""
        self.log(
            event,
            msg,
            status="warning",
            job_id=job_id,
            level=logging.WARNING,
            trace_id=trace_id,
            **kwargs,
        )

    def error(self, event, msg, job_id=None, trace_id=None, **kwargs):
        """Log errore generico."""
        self.log(
            event,
            msg,
            status="error",
            job_id=job_id,
            level=logging.ERROR,
            trace_id=trace_id,
            **kwargs,
        )

    def debug(self, event, msg, job_id=None, trace_id=None, **kwargs):
        """Log di debug."""
        self.log(
            event,
            msg,
            status="debug",
            job_id=job_id,
            level=logging.DEBUG,
            trace_id=trace_id,
            **kwargs,
        )


# ========== CONTEXT MANAGER PER I JOB ==========


class JobLogger:
    """
    Context manager per un logging di job semplice e robusto.
    Richiede un'istanza di StructuraLogger.
    """

    def __init__(self, logger: StructuraLogger, event: str, **kwargs):
        self.logger = logger
        self.event = event
        self.initial_data = kwargs
        self.job_id = None
        self.trace_id = None
        self.start_time = None
        self._final_data = {}

    def __enter__(self):
        self.start_time = time.monotonic()
        self.job_id, self.trace_id = self.logger.job_started(
            event=self.event, **self.initial_data
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.monotonic() - self.start_time) * 1000

        if exc_type:
            self.logger.job_failed(
                self.job_id, exc_val, trace_id=self.trace_id, duration_ms=duration_ms
            )
        else:
            self.logger.job_completed(
                self.job_id,
                duration_ms=duration_ms,
                trace_id=self.trace_id,
                **self._final_data,
            )
        return False

    def set_final_data(self, data: dict):
        """Aggiunge dati custom al log finale di 'job_completed'."""
        self._final_data.update(data)

    # Metodi di logging contestualizzati
    def progress(self, **kwargs):
        """Logga il progresso del job, aggiungendo automaticamente gli ID."""
        self.logger.job_progress(self.job_id, trace_id=self.trace_id, **kwargs)

    def info(self, event: str, msg: str, **kwargs):
        """Logga un messaggio informativo relativo al job."""
        self.logger.info(
            event, msg, job_id=self.job_id, trace_id=self.trace_id, **kwargs
        )

    def warning(self, event: str, msg: str, **kwargs):
        """Logga un warning relativo al job."""
        self.logger.warning(
            event, msg, job_id=self.job_id, trace_id=self.trace_id, **kwargs
        )

    def debug(self, event: str, msg: str, **kwargs):
        """Logga un messaggio di debug relativo al job."""
        self.logger.debug(
            event, msg, job_id=self.job_id, trace_id=self.trace_id, **kwargs
        )
