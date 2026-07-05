"""
Set up logging: print to console and also write to logs/app.log
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Configure only once, even if called from several places
_CONFIGURED = False

# logs folder lives in the project root
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(log_name: str = "app.log", level: int = logging.INFO) -> Path:
    """Attach console + file handlers to the root logger. Returns the log file path."""
    global _CONFIGURED
    # Create logs path if missing
    LOG_DIR.mkdir(exist_ok=True)      
    log_file = LOG_DIR / log_name
    # If set up already, do nothing
    if _CONFIGURED:
        return log_file

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set logger at root level, so all loggers inherit this configuration
    root = logging.getLogger()
    root.setLevel(level)

    # Print output in console
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # Write output in file but it will rotate at 1MB, max 2 files
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    _CONFIGURED = True
    return log_file
