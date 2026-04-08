# Code Review: `/webhook` Endpoint (Python)

**Reviewer:** Mohamad 
**Verdict:** Request changes, do not merge.

Going to focus on the Python since the task said to pick one. Most of what's here applies to the PHP version too (and the PHP has one extra bug I'll call out at the bottom).

**Legend:** 🔴 critical · 🟡 medium · 🟢 nit

---

## 🔴 Critical

### 1. SQL injection via f-string interpolation

```python
cur.execute(
    f"INSERT INTO webhook_audit(email, raw_json) VALUES ('{email}', '{raw.decode(\"utf-8\")}')"
)
cur.execute(
    f"INSERT INTO users(email, role) VALUES('{email}', '{role}')"
)
```

Both `email` and `role` come straight from the JSON body. Anyone who can send a request to this endpoint can drop tables. A payload like `{"email": "x'); DROP TABLE users; --", "role": "admin"}` is enough.

The raw body is also interpolated into the audit insert, which means even a benign payload containing an apostrophe will crash the handler. So this is broken *and* exploitable, which is impressive.

This is the first thing I look for in any PR that touches SQL, f-strings inside `execute()` are the single most common way production databases get owned. CWE-89.

**Fix:** parameterized queries. Always.

```python
cur.execute(
    "INSERT INTO webhook_audit(email, raw_json) VALUES (?, ?)",
    (email, raw),
)
cur.execute(
    "INSERT INTO users(email, role) VALUES (?, ?)",
    (email, role),
)
```

Nothing else in this review matters if this doesn't get fixed.

---

### 2. Signature comparison is not constant-time

```python
return expected == sig
```

Python's `==` on strings short-circuits on the first mismatched byte. Given enough requests, an attacker can recover the signature byte-by-byte from response timing. The endpoint has no rate limiting, so "enough requests" is whatever the attacker wants.

CWE-208. This isn't theoretical, it's been demonstrated against real web apps over the network.

**Fix:** `hmac.compare_digest` runs in constant time.

```python
import hmac
return hmac.compare_digest(expected, sig)
```

---

### 3. `SHA256(secret + body)` is not HMAC

```python
expected = hashlib.sha256(
    (WEBHOOK_SECRET + body.decode("utf-8")).encode("utf-8")
).hexdigest()
```

This is the canonical length-extension footgun. SHA-256 is a Merkle–Damgård hash, which means given `H(secret || message)` and the length of the secret, you can compute `H(secret || message || padding || attacker_data)` *without knowing the secret*. The attacker doesn't need to brute-force anything, they just need one valid signature and they can forge more.

HMAC was invented specifically to prevent this. Use it.

```python
import hmac, hashlib

def compute_signature(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
```

Also: stop decoding the body to UTF-8 and re-encoding it. Sign the raw bytes. If the body contains any byte sequence that isn't valid UTF-8, the decode/encode round-trip will silently change what's being verified.

---

### 4. "Upsert" is just an INSERT

The task description says *upsert*. This does a plain `INSERT`. Two failure modes depending on the schema:

1. If `email` has a `UNIQUE` constraint, the second webhook for the same user crashes with `IntegrityError` → 500 → vendor retries → crashes again. Infinite loop until someone pages the on-call.
2. If it doesn't, you get duplicate rows and `SELECT WHERE email = ?` starts returning multiple results. Downstream code then breaks in creative ways.

**Fix:** SQLite supports native upsert.

```python
cur.execute(
    """INSERT INTO users(email, role) VALUES (?, ?)
       ON CONFLICT(email) DO UPDATE SET role = excluded.role""",
    (email, role),
)
```

Requires a `UNIQUE` index on `email`, which you'd want anyway.

---

### 5. `WEBHOOK_SECRET` defaults to `"dev-secret"` in production

```python
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-secret")
```

If the env var is ever unset in prod, bad Helm chart, missing secret, wrong namespace, the service silently keeps running and accepts any signature computed with `"dev-secret"`. The default string is also committed to the repo, so anyone with read access knows it.

Fail closed, not open.

```python
_DEV_MODE = os.getenv("FLASK_ENV") == "development"

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    if _DEV_MODE:
        WEBHOOK_SECRET = "dev-secret-do-not-use-in-production"
    else:
        raise RuntimeError("WEBHOOK_SECRET is required in production")
```

---

## 🟡 Medium

### 6. Unhandled `json.loads` → 500 instead of 400

```python
payload = json.loads(raw.decode("utf-8"))
```

A malformed body is a client error. Returning 500 tells the vendor to retry, so they'll keep sending the same garbage forever.

```python
try:
    payload = json.loads(raw.decode("utf-8"))
except (json.JSONDecodeError, UnicodeDecodeError):
    return ("malformed JSON", 400)
```

---

### 7. No schema validation

`email` can be an empty string, `None`, a dict, or fifty megabytes of garbage. `role` can be `"superadmin-please-give-me-root"` and the code will cheerfully insert it. Use Pydantic:

```python
from pydantic import BaseModel, EmailStr
from typing import Literal

class WebhookPayload(BaseModel):
    email: EmailStr
    role: Literal["user", "vendor", "admin"]
    metadata: dict = {}
```

Validate at the boundary, before any of that data touches SQL.

---

### 8. No request size limit

Nothing stops a client from POSTing a 10 GB body. Flask will happily try to read all of it.

```python
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB
```

Enforce it at the reverse proxy too, so oversized requests never reach the Python process.

---

### 9. No idempotency

Vendors retry. That's not a bug in the vendor, it's the retry contract every webhook system relies on. Without idempotency, every retry duplicates audit rows and re-fires any side effects (emails, provisioning, billing events). Require an `X-Event-Id` header, put a unique index on it in the audit table, and treat conflicts as a no-op 200.

Also worth storing the event ID alongside the user row, not just in audit, otherwise you can't tell *which* delivery created a given user, which makes incident forensics miserable.

```python
event_id = request.headers.get("X-Event-Id")
if not event_id:
    return ("missing X-Event-Id", 400)
```

---

### 10. No replay protection

Even a perfectly valid signature is valid forever. Capture one request, replay it whenever. Sign a timestamp along with the body and reject requests outside a ~5 minute window.

```python
signed_content = f"{timestamp}.".encode() + raw
expected = hmac.new(WEBHOOK_SECRET.encode(), signed_content, hashlib.sha256).hexdigest()
```

---

### 11. DB connection leaks on error

```python
def get_db():
    return sqlite3.connect(DB_PATH)
```

Nothing closes the connection. Nothing rolls back. If `cur.execute` throws (and given issue #1, it will), the connection leaks and any half-done transaction sits there until SQLite times out the lock. Wrap it in a context manager.

```python
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

---

### 12. Audit log stores parsed `email` next to raw JSON

An audit log's job is to be a faithful record of what came in over the wire. This stores `email` (parsed from the JSON) *and* the raw body, meaning if the parser ever gets it wrong, or the extraction logic has a bug, the audit row contains an email that doesn't match what was actually received.

Store raw data only: body bytes, headers, signature, timestamp, and the processing result. If you need to query by email later, query the `users` table. Audit and application state are two different things and shouldn't be mixed in one row.

---

## 🟢 Nits

### 13. No logging anywhere.
When this endpoint breaks at 3 AM, the on-call engineer has nothing. No request IDs, no error context, nothing. One `logger.info` on entry and one `logger.exception` in a try/except would go a long way.

### 14. No tests.
Zero. The signature verification logic is especially scary to ship untested, it's the class of code that looks right and is wrong in ways you find out about in an incident report.

### 15. `role` defaults to `"user"`, but these are vendors.
The task specifically says *"users who are vendors"*. Defaulting the role to `"user"` on a missing field will silently create the wrong kind of account. Either default to `"vendor"` or, probably better, reject the request if `role` is missing.

### 16. PHP bonus: the audit-enabled flag doesn't actually toggle.
Not in the Python, but worth flagging since the task included both: the PHP has `$DB_AUDIT_ENABLED = getenv("AUDIT_ENABLED") ?: "true";` and then `if ($DB_AUDIT_ENABLED) {...}`. In PHP, any non-empty string is truthy, so setting `AUDIT_ENABLED=false` leaves auditing *on*. The only way to disable auditing is to set an empty string, which nobody will guess. Someone is going to discover this during a compliance audit and it will not be a good day.

---

## Summary

| # | Severity | Issue | Fix effort |
|---|---|---|---|
| 1 | 🔴 | SQL injection | 10 min |
| 2 | 🔴 | Timing-attack on signature compare | 2 min |
| 3 | 🔴 | Not actually HMAC | 5 min |
| 4 | 🔴 | Insert, not upsert | 10 min (needs a migration) |
| 5 | 🔴 | Fails open on missing secret | 8 min |
| 6 | 🟡 | Malformed JSON → 500 | 3 min |
| 7 | 🟡 | No schema validation | 20 min |
| 8 | 🟡 | No body size limit | 5 min |
| 9 | 🟡 | No idempotency | ~30 min + schema change |
| 10 | 🟡 | No replay protection | 20 min |
| 11 | 🟡 | DB connection leaks | 10 min |
| 12 | 🟡 | Audit log mixes parsed + raw | 15 min |
| 13 | 🟢 | No logging | 10 min |
| 14 | 🟢 | No tests | an afternoon |
| 15 | 🟢 | Wrong default role | 2 min |
| 16 | 🟢 | PHP truthy-string bug | 2 min |

## Recommendation

Close this PR and open a new one that addresses the five critical items, none are optional and most are under ten minutes once you know what to look for. The medium items should become tracked issues and land before the endpoint sees real traffic.