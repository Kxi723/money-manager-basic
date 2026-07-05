import logging
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import uvicorn
import config
from logging_config import setup_logging

if __name__ == "__main__":
    log_file = setup_logging()
    logger = logging.getLogger("run.py")

    url = f"http://{config.HOST}:{config.PORT}"
    logger.info(f"Starting Money Manager on {url}")

    # Activate a background thread to open the browser after 1.5s
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(
        "main:app",
        app_dir="backend",
        host=config.HOST,
        port=config.PORT,
        log_config=None, #Ensure uvicorn logs are handled by our logging setup
    )
