# StructuraLog

[![PyPI version](https://badge.fury.io/py/structuralog.svg)](https://badge.fury.io/py/structuralog)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**StructuraLog** è una libreria Python per il logging strutturato in formato **JSON**. È pensata per essere thread-safe, facile da configurare e ideale per applicazioni e servizi moderni, specialmente in ambienti containerizzati dove i log vengono raccolti da `stdout`.

## Caratteristiche Principali

*   **Logging Strutturato JSON:** Tutti i log sono emessi in formato JSON, pronti per essere processati da sistemi come Loki, Elasticsearch o Splunk.
*   **Configurazione Esplicita:** Nessun effetto collaterale all'import. La libreria si attiva solo con una chiamata esplicita a `configure()`.
*   **Thread-Safe:** Utilizza una coda (`Queue`) per gestire i log da thread multipli senza race condition, garantendo che l'I/O non blocchi l'applicazione.
*   **API Semantica:** Offre un'API intuitiva (`JobLogger`, `api_request`, etc.) per produrre log ricchi, consistenti e facili da analizzare.
*   **Ciclo di Vita Controllato:** Fornisce `configure()` e `shutdown()` per un controllo completo sul ciclo di vita del logger.

## Installazione

Puoi installare la libreria da PyPI:

```bash
pip install structuralog
```

Oppure, per lo sviluppo, clona il repository e installala in modalità "editable":

```bash
git clone https://github.com/your-username/StructuraLog.git
cd StructuraLog
pip install -e .[test]
```

## Quickstart

Ecco come iniziare a usare `StructuraLog` in pochi passaggi.

```python
from structura_log import configure, get_logger, shutdown

# 1. All'avvio della tua applicazione, configura il logger.
#    Questa operazione va fatta una sola volta.
configure(service_name="my-awesome-app", log_level="INFO")

# 2. Ottieni l'istanza del logger per usarla nel tuo codice.
logger = get_logger()

# 3. Inizia a loggare!
logger.info("Servizio avviato", component="main")
logger.warning("Connessione al database lenta", latency_ms=1200)

# Esempio con dati strutturati extra
user_data = {"username": "test-user", "ip": "192.168.1.100"}
logger.info("Login utente riuscito", event="user_login", **user_data)


# 4. Alla fine, chiama shutdown per assicurarti che tutti i log in coda
#    vengano scritti prima che il processo termini.
shutdown()
```

## Esempio di Utilizzo Avanzato (`JobLogger`)

Per operazioni complesse o processi di lunga durata, puoi usare il context manager `JobLogger`. Gestisce automaticamente `trace_id`, timing, stato (successo/fallimento) e log degli errori.

```python
import time
from structura_log import JobLogger, configure

configure(service_name="my-job-processor")

try:
    with JobLogger(event="process_file", file_name="data.csv") as job:
        # job.trace_id è generato automaticamente
        print(f"Processando job con trace_id: {job.trace_id}")
        
        time.sleep(1) # Simula lavoro
        job.progress(step="reading_file", progress_percent=50)

        time.sleep(1) # Simula altro lavoro
        
        # In caso di successo, puoi aggiungere dati finali al log
        job.set_final_data({"rows_processed": 1000})

except Exception:
    # L'errore viene loggato automaticamente dal context manager
    print("Errore catturato, il fallimento è già stato loggato.")
finally:
    shutdown()
```

## Modulo `contrib`

Il modulo `structura_log.contrib` contiene integrazioni e funzioni di utilità per framework e librerie comuni.

### `contrib.fastapi`

Fornisce funzioni helper per loggare eventi comuni in un'applicazione API, come richieste, query al database ed eventi di autenticazione.

**Esempio:**

```python
import uuid
from structura_log import configure, get_logger, shutdown
from structura_log.contrib.fastapi import api_request, db_query, auth_event

configure(service_name="my-fastapi-app")
logger = get_logger()

def handle_request():
    trace_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    user_id = "user-123"

    # Log di un evento di autenticazione
    auth_event(logger, "login", username=user_id, success=True, trace_id=trace_id)

    # Log di una query al database
    db_query(logger, "SELECT", table="products", duration_ms=75, trace_id=trace_id)

    # Log della richiesta API
    api_request(
        logger,
        method="GET",
        path="/products/42",
        status_code=200,
        duration_ms=120,
        request_id=request_id,
        user_id=user_id,
        trace_id=trace_id
    )

    shutdown()

handle_request()
```

## Esecuzione dell'Applicazione di Esempio

Nella cartella `examples/` troverai un'applicazione completa (`mock_producer.py`) che simula un generatore di log.

Per eseguirla, dopo aver installato le dipendenze, lancia questo comando dalla root del progetto:

```bash
python examples/mock_producer.py
```

Vedrai i log JSON stampati sulla console. Premi `Ctrl+C` per terminare.