import time
import random
import signal
import uuid
from structura_log import StructuraLogger, JobLogger
from structura_log.contrib.fastapi import api_request, db_query, auth_event


# Definiamo un'eccezione custom per gestire la chiusura in modo pulita
class ShutdownException(Exception):
    pass


def graceful_shutdown_handler(signum, frame):
    """
    Questo handler viene chiamato quando il processo riceve un segnale di
    terminazione. Solleva un'eccezione per interrompere il loop principale.
    """
    # Usa il logger per segnalare la ricezione del segnale
    # NOTA: In un'app reale, il logger dovrebbe essere accessibile globalmente
    # o passato all'handler in qualche modo. Per questo esempio, lo saltiamo.
    raise ShutdownException(f"Received signal {signal.Signals(signum).name}")


def simulate_work(logger: StructuraLogger):
    """Simula un job utilizzando il nuovo JobLogger context manager."""
    time.sleep(random.uniform(1, 2))

    # Il context manager ora riceve l'istanza del logger
    try:
        with JobLogger(logger, event="ingest_job", input="s3://bucket/demo") as job:
            # === ESEMPI DI LOGGING CON CONTRIB.FASTAPI ===
            # Simuliamo che questo job sia stato triggerato da una richiesta API

            # 1. Log di autenticazione
            auth_event(
                logger,
                "jwt_validated",
                username="user-123",
                success=True,
                trace_id=job.trace_id,
            )

            # 2. Log di una query al DB
            db_query(
                logger, "SELECT", table="users", duration_ms=75, trace_id=job.trace_id
            )

            # 3. Log della richiesta API che ha avviato il job (simulata)
            api_request(
                logger,
                method="POST",
                path="/api/v1/ingest",
                status_code=202,  # Accepted
                duration_ms=150,
                request_id=str(uuid.uuid4()),
                user_id="user-123",
                trace_id=job.trace_id,
            )
            # ===============================================

            # finto progresso
            for p in (10, 40, 70, 100):
                time.sleep(0.8)
                job.progress(step="ingest", progress=p)

            # Logica di business...
            time.sleep(0.5)
            if random.choice([False, True, False]):  # ogni tanto genera errore
                raise ValueError("Simulated ingest error")

            # Se il job ha successo, possiamo aggiungere dati al log finale
            job.set_final_data(
                {"records_processed": 1234, "status_detail": "all clear"}
            )

    except ValueError as e:
        # La logica di business può ancora catturare eccezioni se necessario,
        # ma il fallimento del job è già stato loggato da JobLogger.
        # Logghiamo che abbiamo gestito l'eccezione a livello di business.
        logger.info(
            "business_logic_exception_handled",
            f"Caught business logic exception: {e}",
        )


if __name__ == "__main__":
    # 1. Invece di 'configure', istanziamo il logger
    logger = StructuraLogger(service_name="mock-log-producer", log_level="INFO")

    # Registriamo il nostro gestore per i segnali di terminazione
    signal.signal(signal.SIGINT, graceful_shutdown_handler)
    signal.signal(signal.SIGTERM, graceful_shutdown_handler)

    # 2. Avviamo l'heartbeat tramite il metodo della classe
    logger.start_heartbeat_thread(interval=30)

    try:
        logger.info("service_started", "Mock log producer service starting up.")
        while True:
            # 3. Passiamo l'istanza del logger dove serve
            simulate_work(logger)
            time.sleep(5)
    except ShutdownException as se:
        logger.info("graceful_shutdown", f"Graceful shutdown initiated: {se}")
    except Exception as e:
        # 4. Usiamo i metodi del logger per la gestione degli errori
        logger.error(
            "unexpected_shutdown", f"Shutting down due to an unexpected error: {e}"
        )
    finally:
        # 5. Chiamiamo lo shutdown del logger, che ferma anche l'heartbeat
        logger.shutdown()
        # Log finale allo stderr o a un file, dato che il logger è spento
        # In questo caso, un print finale è accettabile.
        print("Shutdown complete.")
