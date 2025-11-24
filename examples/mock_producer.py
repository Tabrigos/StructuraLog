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
    print(
        f"\nReceived signal {signal.Signals(signum).name}. Triggering graceful shutdown..."
    )
    raise ShutdownException()


def simulate_work(logger: StructuraLogger):
    """Simula un job utilizzando il nuovo JobLogger context manager."""
    time.sleep(random.uniform(1, 2))

    # Il context manager ora riceve l'istanza del logger
    try:
        with JobLogger(logger, event="ingest_job", input="s3://bucket/demo") as job:
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
        print(f"(Caught business logic exception: {e}) - Job failure already logged.")


def simulate_api_call(logger: StructuraLogger, trace_id: str):
    """Simula una chiamata API e operazioni correlate usando le funzioni di `contrib.fastapi`."""
    logger.info("Simulating API call", trace_id=trace_id, component="api_simulator")

    request_id = str(uuid.uuid4())
    user_id = f"user_{random.randint(1, 100)}"
    auth_success = random.choice([True, False, True])

    # Esempio: evento di autenticazione
    auth_event(
        logger,
        event_type="login",
        username=user_id,
        success=auth_success,
        request_id=request_id,
        trace_id=trace_id,
    )

    # Esempio: query al database (solo se l'auth ha successo)
    if auth_success:
        db_query(
            logger,
            query_type="SELECT",
            table="users",
            duration_ms=random.uniform(10, 250),
            request_id=request_id,
            trace_id=trace_id,
        )

    # Esempio: log della richiesta API
    api_request(
        logger,
        method=random.choice(["GET", "POST"]),
        path=f"/api/v1/items/{random.randint(1, 100)}",
        status_code=random.choice([200, 201, 404, 500, 200]),
        duration_ms=random.uniform(50, 500),
        request_id=request_id,
        user_id=user_id,
        trace_id=trace_id,
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
        i = 0
        while True:
            i += 1
            print("-" * 50)  # Separatore per una migliore leggibilità dell'output
            if i % 2 == 0:
                logger.info("Next simulation: Background Job", component="main_loop")
                # Simulazione di un job di background
                simulate_work(logger)
            else:
                logger.info("Next simulation: API Call", component="main_loop")
                # Simulazione di chiamate API
                trace_id = str(uuid.uuid4())
                simulate_api_call(logger, trace_id=trace_id)

            time.sleep(random.uniform(2, 4))
    except ShutdownException:
        print("\nGraceful shutdown initiated...")
    except Exception as e:
        # 4. Usiamo i metodi del logger per la gestione degli errori
        print(f"\nUNEXPECTED ERROR: {e}. Shutting down...")
        logger.error(
            "unexpected_shutdown", f"Shutting down due to an unexpected error: {e}"
        )
    finally:
        # 5. Chiamiamo lo shutdown del logger, che ferma anche l'heartbeat
        logger.shutdown()
        print("Shutdown complete.")
