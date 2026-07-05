"""
FastAPI app: auth, transaction and mode routes; also serves the frontend
"""
import logging
from logging_config import setup_logging

setup_logging()
logger = logging.getLogger("money-manager")

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import security
from db import db
from seed import ensure_seeded

# Server start, FastAPI enters to this context
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_seeded()
    logger.info(f"Running in {config.current_mode()} mode")
    yield


app = FastAPI(title="Money Manager", version="1.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Auto-shutdown
# ---------------------------------------------------------------------------
_SHUTDOWN_GRACE_SECONDS = 3
_open_pages = 0
_pending_shutdown: asyncio.Task | None = None

# Register a WebSocket endpoint to track open pages
@app.websocket("/ws")
async def _page_socket(ws: WebSocket):
    global _open_pages, _pending_shutdown
    await ws.accept()
    _open_pages += 1

    # If new page connected, cancel shutdown task
    if _pending_shutdown:
        _pending_shutdown.cancel()
        _pending_shutdown = None

    try:
        while True:
            # Hold the connection open until the page closes or reloads
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _open_pages -= 1
        if _open_pages <= 0:
            _pending_shutdown = asyncio.create_task(_shutdown_when_idle())


async def _shutdown_when_idle() -> None:
    await asyncio.sleep(_SHUTDOWN_GRACE_SECONDS)

    # After x seconds of no open pages, shut down
    if _open_pages <= 0:
        logger.info("Shutting down because no open pages remain")
        os._exit(0)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    user_id = security.read_token(token)
    # Skip invalid token
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    with db() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    # Skip missing user
    if row is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {"id": row["id"], "username": row["username"]}


def _row_to_json(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "amount": float(security.decrypt_field(row["amount"])),
        "type": row["type"],
        "category": row["category"],
        "note": security.decrypt_field(row["note"]),
        "date": row["date"],
    }


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
class User(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


@app.post("/api/register")
def register(account: User):
    with db() as conn:
        # Skip duplicate username
        exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (account.username,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="Username already taken")

        # Insert new user into db
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
            (account.username, security.hash_password(account.password)),
        )
        uid = conn.execute("SELECT id FROM users WHERE username = ?", (account.username,)).fetchone()["id"]

    token = security.issue_token(uid, account.username)
    return {"token": token, "user_id": uid, "username": account.username}


@app.post("/api/login")
def login(account: User):
    # Set limit on login attempts to mitigate brute force attacks, 0 in insecure mode
    locked = security.is_locked(account.username)
    if locked:
        raise HTTPException(status_code=429, detail=f"Too many attempts. Try again in {locked}s.")

    with db() as conn:
        row = conn.execute( "SELECT id, username, password FROM users WHERE username = ?", (account.username,)).fetchone()
    # Wrong username or password
    if row is None or not security.verify_password(account.password, row["password"]):
        security.record_failure(account.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    security.record_success(account.username)
    token = security.issue_token(row["id"], row["username"])
    return {"token": token, "user_id": row["id"], "username": row["username"]}


@app.post("/api/logout")
def logout():
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


# ---------------------------------------------------------------------------
# Transaction routes
# ---------------------------------------------------------------------------
# Try 'api("/api/transactions").then(console.log)'
@app.get("/api/transactions")
def list_transactions(request: Request, user: dict = Depends(current_user)):
    if config.is_secure():
        owner_id = user["id"]
        
    # Insecure Direct Object Reference
    else:
        owner_id = request.query_params.get("user_id", user["id"])
    with db() as conn:
        rows = conn.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", (owner_id,)).fetchall()

    return [_row_to_json(r) for r in rows]


# Try 'api("/api/transactions/45").then(console.log)'
@app.get("/api/transactions/{tx_id}")
def get_transaction(tx_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        # Only return the transaction if it belongs to the current user
        if config.is_secure():
            row = conn.execute("SELECT * FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user["id"]),).fetchone()

        # Changing trasaction id returns another user's transaction
        else:
            row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _row_to_json(row)


class Transaction(BaseModel):
    amount: float
    type: str
    category: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=500)
    date: str | None = None


@app.post("/api/transactions", status_code=201)
def create_transaction(tx: Transaction, user: dict = Depends(current_user)):
    if tx.type not in ("income", "expense"):
        raise HTTPException(status_code=400, detail="type must be income or expense")
    tx_date = tx.date or date.today().isoformat()

    with db() as conn:
        conn.execute(
            """INSERT INTO transactions (user_id, amount, type, category, note, date)
               VALUES (?, ?, ?, ?, ?, ?)""", (
                user["id"],
                security.encrypt_field(str(tx.amount)),
                tx.type,
                tx.category,
                security.encrypt_field(tx.note),
                tx_date,
            ),
        )
        new_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (new_id,)).fetchone()
    return _row_to_json(row)


@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int, user: dict = Depends(current_user)):
    with db() as conn:
        if config.is_secure():
            cur = conn.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?",(tx_id, user["id"]),)

        else:
            # Can delete anyone's row.
            cur = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Transaction not found")
    return {"ok": True}


@app.get("/api/summary")
def summary(user: dict = Depends(current_user)):
    """Totals for the current calendar month: income, expense, balance."""
    month_prefix = date.today().strftime("%Y-%m")

    with db() as conn:
        rows = conn.execute("SELECT amount, type, date FROM transactions WHERE user_id = ?", (user["id"],),).fetchall()

    income = expense = 0.0
    for r in rows:
        # Show transactions with current month
        if not r["date"].startswith(month_prefix):
            continue

        amt = float(security.decrypt_field(r["amount"]))
        if r["type"] == "income":
            income += amt
        else:
            expense += amt

    return {
        "month": month_prefix,
        "income": round(income, 2),
        "expense": round(expense, 2),
        "balance": round(income - expense, 2),
    }


class ModeIn(BaseModel):
    mode: str


@app.get("/api/mode")
def mode():
    return {"mode": config.current_mode()}


@app.post("/api/mode")
def switch_mode(body: ModeIn):
    old_mode = config.current_mode()

    try:
        new_mode = config.set_mode(body.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    ensure_seeded()

    logger.info(f"Mode switched: {old_mode} -> {new_mode}")
    return {"mode": new_mode}


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(config.FRONTEND_DIR / "index.html")


@app.get("/dashboard")
def dashboard():
    return FileResponse(config.FRONTEND_DIR / "dashboard.html")


app.mount(
    "/static",
    StaticFiles(directory=str(config.FRONTEND_DIR / "static")),
    name="static",
)
