"""
Central configuration. Everything is read from environment variables with same
local defaults so the same code runs locally and on cloud.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

def _load_dotenv() -> None:
    """Environment variables loader"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

# --- App mode -------------------------------------------------------------
# The mode is mutable at runtime so it can be flipped from the UI toggle.
# Everything that branches on it reads is_secure()/current_mode() at call 
# time rather than caching a constant, so a switch takes effect immediately.

VALID_MODES = ("insecure", "secure")
_INITIAL_MODE = os.environ.get("APP_MODE", "insecure").strip().lower()

if _INITIAL_MODE not in VALID_MODES:
    msg = f"APP_MODE must be one of {VALID_MODES}, system read: {_INITIAL_MODE!r}"
    logger.error(msg)
    raise SystemExit(msg)

_mode = _INITIAL_MODE

def current_mode() -> str:
    return _mode


def is_secure() -> bool:
    return _mode == "secure"


def set_mode(mode: str) -> str:
    global _mode
    mode = mode.strip().lower()

    if mode not in VALID_MODES:
        msg = f"App mode must be one of {VALID_MODES}"
        logger.error(msg)
        raise ValueError(msg)

    _mode = mode
    return _mode


# --- Paths ----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "money_manager.db"))
FRONTEND_DIR = BASE_DIR / "frontend"

def db_path() -> str:
    p = Path(DB_PATH)
    return str(p.with_name(f"{p.stem}.{_mode}{p.suffix}"))

# --- Server ---------------------------------------------------------------
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

# --- Secrets --------------------------------------------------------------
# Read from environment variables, if none then default is used.
JWT_SECRET = os.environ.get("JWT_SECRET", "jason-tp080522-css")

# A symmetric algorithm that shares one secret key
JWT_ALG = "HS256"

# Time-to-live for JWT session tokens, 1 hour I set
JWT_TTL_SECONDS = int(os.environ.get("JWT_TTL_SECONDS", str(60 * 60)))

# AES-256-GCM key for data encryption.
AES_KEY = os.environ.get("AES_KEY", "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")

# Login rate limiting (secure mode only)
MAX_FAILED_LOGINS = int(os.environ.get("MAX_FAILED_LOGINS", "5"))
LOCKOUT_SECONDS = int(os.environ.get("LOCKOUT_SECONDS", "60"))
