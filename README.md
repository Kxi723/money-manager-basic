# Money Manager

A small personal finance tracker which runs in **two switchable modes** so the same app can be 
shown before and after security hardening:

| Mode | What it shows |
|------|---------------|
| **Insecure** | The two deliberate weaknesses, present and exploitable. |
| **Secure** | The same app, both weaknesses fixed. |

Flip modes live with the **lock toggle** (bottom-left of the UI), or set `APP_MODE` at start.
Each mode keeps its own SQLite file (`money_manager.insecure.db` / `.secure.db`), auto-seeded on
first use, so switching never mixes plaintext with ciphertext. Switching signs you out — the
insecure token isn't valid in secure mode, which is itself part of the lesson.

> Uni assignment on the my own machine; the insecure mode is deliberately weak.

## The two flaws (and fixes)

**Flaw 1 — Broken access control (IDOR) + weak auth**
- *Insecure:* records fetched / edited / deleted by client-supplied `id` / `?user_id=` with no
  ownership check; passwords as bare unsalted **SHA-1**; no login rate limiting.
- *Secure:* every query scoped `WHERE user_id = <token user>` (foreign row → **404**);
  **Argon2id** passwords; **signed JWT** sessions; lockout after 5 failed logins.

**Flaw 2 — Sensitive data in cleartext**
- *Insecure:* `amount` and `note` written to SQLite as **plaintext**; served over plain HTTP,
  so request bodies are visible in DevTools / Wireshark.
- *Secure:* `amount` / `note` encrypted with **AES-256-GCM** (key from `AES_KEY`) before write.
  TLS and at-rest encryption are complementary: TLS protects data in transit, field encryption
  keeps a stolen `.db` file unreadable.

### Secondary flaws (also insecure → fixed in secure)

- **No password policy:** *insecure* accepts any password; *secure* requires 8+ characters with
  an uppercase letter and a digit at registration (existing/seeded accounts still log in).
- **Client-side-only input validation:** *insecure* trusts the client — the transaction amount
  is checked only in the frontend, so a request bypassing it (curl / DevTools) can store zero,
  negative, or absurdly large values; *secure* validates `0 < amount ≤ 1,000,000` on the server.

## Run it

Requires Python 3.14. From the repo root:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install fastapi==0.138.1 "uvicorn[standard]==0.49.0" pydantic==2.13.4 argon2-cffi==25.1.0 PyJWT==2.13.0 cryptography==49.0.0
cp .env.example .env                                       # optional; defaults work locally

APP_MODE=insecure .venv/Scripts/python backend/seed.py     # seed demo data
APP_MODE=insecure .venv/Scripts/python run.py              # http://127.0.0.1:8000
```

Demo users: **jason / password** and **test / admin**. The **"Sign in with Google"** button is a
demo shortcut (not real OAuth) — it logs straight into `jason`.

> On Windows PowerShell, set the mode first: `$env:APP_MODE="insecure"; .venv/Scripts/python run.py`.

## Demo script

Log in as **jason**; **test** owns the other seeded transactions.

- **Flaw 1 — IDOR:** replay a request against another user's transaction id —
  `curl http://127.0.0.1:8000/api/transactions/<id> -H "Authorization: Bearer <jason_token>"`.
  Insecure returns it (breach); secure returns **404**. Same for `DELETE` and `?user_id=`.
- **Flaw 1 — weak auth:** `users.password` is `sha1$...` (insecure) vs `$argon2id$...` (secure);
  wrong-password spam is unlimited (insecure) vs `429` after 5 tries (secure).
- **Flaw 2 — at rest:** open the DB file and compare `amount` / `note` —
  `.venv/Scripts/python -c "import sqlite3;[print(r) for r in sqlite3.connect('money_manager.insecure.db').execute('SELECT amount, note FROM transactions LIMIT 4')]"`.
  Insecure shows plaintext; the secure file shows AES-GCM ciphertext.
- **Flaw 2 — in transit:** on plain HTTP, a login/transaction body is visible in DevTools →
  Network or Wireshark. (Optional: run uvicorn with `--ssl-keyfile` / `--ssl-certfile` for a
  local HTTPS demo.)

## Configuration (via `.env`)

| Var | Default | Purpose |
|-----|---------|---------|
| `APP_MODE` | `insecure` | `insecure` or `secure` |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | server bind |
| `DB_PATH` | `money_manager.db` | base SQLite path (mode suffix added) |
| `JWT_SECRET` | dev default | JWT signing (secure) |
| `AES_KEY` | dev default | 32-byte key, hex or base64 (secure) |
| `MAX_FAILED_LOGINS` / `LOCKOUT_SECONDS` | `5` / `60` | login lockout (secure) |

`.env` is gitignored; all config is read from the environment.

## Design

A warm analog **paper ledger**: ruled hairlines and right-aligned tabular-figure amounts
(Fraunces / Hanken Grotesk / JetBrains Mono). No gradients, glass, or emoji.
