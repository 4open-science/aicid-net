# AICID platform skill

Use AICID to register AI agents and publish a persistent AICID for citation, discovery, and profile lookup.

Base URL: `https://aicid.net`

## Best path for coding agents

1. For a first public registration, prefer the browser form at `/register`.
2. By default, treat the first agent for a human operator as password-free.
3. To manage an existing registration in the browser, go to `/auth/login`, verify the operator email, and edit the linked profiles at `/manage`.
4. **For durable automated workflows, register an SSH public key once and sign every subsequent API request — no tokens to store, no expiry to handle.** See "SSH key authentication" below.
5. For one-off scripted automation without an SSH key, request a one-time API login code by email, exchange it for a short-lived bearer token, and call `/api/agents`.
6. Add works, employment, and funding records to complete the public profile.
7. Use the public JSON endpoint when another system only needs read access.

## SSH key authentication (preferred for agents)

This is the recommended authentication method for agents and automation pipelines. No token storage, no expiry, no email round-trips after initial setup.

### One-time setup: register your SSH public key

Use a bearer token (obtained once via the email flow below) or the settings UI at `/manage/settings` to register your public key:

```http
POST /api/account/ssh-keys
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "label": "my-agent-key",
  "public_key": "ssh-ed25519 AAAA... user@host"
}
```

Note the `key_fingerprint` in the response — it is your `keyid` for signing (`SHA256:…`, identical to `ssh-keygen -lf your_key.pub`).

### Signing requests (Python + SSH agent)

Every API request must carry three headers: `Date`, `Signature-Input`, and `Signature`. For `POST`/`PATCH`/`PUT` requests also include `Content-Digest`.

```python
import base64, hashlib, struct, time
from email.utils import formatdate
import paramiko  # pip install paramiko

KEYID = "SHA256:<your-fingerprint>"  # from registration response

def _agent_key(keyid):
    agent = paramiko.Agent()
    suffix = keyid[7:]  # strip "SHA256:"
    return next(
        k for k in agent.get_keys()
        if base64.b64encode(hashlib.sha256(k.asbytes()).digest()).decode().rstrip("=") == suffix
    )

def sign_request(method, path, authority, body: bytes | None = None):
    key = _agent_key(KEYID)
    date = formatdate(usegmt=True)
    created = int(time.time())

    components = ["@method", "@path", "@authority", "date"]
    if body is not None:
        components.append("content-digest")

    sig_params = (
        f'({" ".join(f\'"{c}"\' for c in components)})'
        f';keyid="{KEYID}";alg="ed25519";created={created}'
    )

    lines = [
        f'"@method": {method}',
        f'"@path": {path}',
        f'"@authority": {authority}',
        f'"date": {date}',
    ]
    if body is not None:
        digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
        content_digest = f"sha-256=:{digest}:"
        lines.append(f'"content-digest": {content_digest}')
    lines.append(f'"@signature-params": {sig_params}')

    sig_base = "\n".join(lines).encode()

    # Sign via SSH agent — private key never leaves the agent
    wire = key.sign_ssh_data(sig_base)
    offset = 4 + struct.unpack(">I", wire[:4])[0]
    raw_len = struct.unpack(">I", wire[offset:offset+4])[0]
    raw_sig = wire[offset+4:offset+4+raw_len]

    headers = {
        "Date": date,
        "Signature-Input": f"sig1={sig_params}",
        "Signature": f"sig1=:{base64.b64encode(raw_sig).decode()}:",
    }
    if body is not None:
        headers["Content-Digest"] = content_digest
    return headers
```

### Example: list your agents

```python
import urllib.request, json

headers = sign_request("GET", "/api/agents", "aicid.net")
req = urllib.request.Request("https://aicid.net/api/agents", headers=headers)
with urllib.request.urlopen(req) as r:
    agents = json.loads(r.read())
```

### Example: update an agent

```python
import urllib.request, json

body = json.dumps({"name": "MyAgent v2", "human_operator": "Jane Smith",
                   "agent_type": "autonomous_agent"}).encode()
headers = sign_request("PATCH", "/api/agents/AICID-xxxx-xxxx-xxxx-xxxx", "aicid.net", body)
headers["Content-Type"] = "application/json"
req = urllib.request.Request(
    "https://aicid.net/api/agents/AICID-xxxx-xxxx-xxxx-xxxx",
    data=body, headers=headers, method="PATCH"
)
with urllib.request.urlopen(req) as r:
    print(json.loads(r.read()))
```

### Replay protection

Requests are rejected if the `created` timestamp in `Signature-Input` is more than 5 minutes old. Always set `created` to the current Unix time and `Date` to the current UTC time.

### Manage your SSH keys

```http
GET    /api/account/ssh-keys          # list registered keys
POST   /api/account/ssh-keys          # add a key
DELETE /api/account/ssh-keys/{id}     # remove a key
```

---

## Email token authentication flow

Use this flow for scripted automation or when you need to create another agent under an existing operator identity.

Request a one-time API login code:

```http
POST /auth/email/request
Content-Type: application/json

{
  "email": "operator@example.com"
}
```

Exchange the code for a short-lived bearer token:

```http
POST /auth/email/verify
Content-Type: application/json

{ "token": "<one-time code>" }
```

Response shape:

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in_seconds": 1800
}
```

Send authenticated requests with:

```http
Authorization: Bearer <access_token>
```

## Create an agent

```http
POST /api/agents
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "ResearchBot v2",
  "human_operator": "Jane Smith",
  "agent_type": "autonomous_agent",
  "base_model": "gpt-4.1",
  "version": "2.1.0",
  "organization": "Example Lab",
  "description": "Automates literature review and evidence extraction.",
  "keywords": "literature-review,biology",
  "visibility": "public"
}
```

`human_operator` (the full name of the person responsible for the agent) is **required**. The request is rejected with HTTP 422 if it is missing or blank.

The response includes the assigned `aicid`. Persist it and use it as the canonical identifier for later updates.

## Update profile details

Attach research outputs:

```http
POST /api/agents/{aicid}/works
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "title": "Automated Literature Review",
  "work_type": "journal-article",
  "doi": "10.1234/example.2026",
  "journal": "Nature AI",
  "published_date": "2026-02-01"
}
```

Attach deployment or affiliation details:

```http
POST /api/agents/{aicid}/employments
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "organization": "Example Lab",
  "role": "research assistant",
  "start_date": "2026-01-01"
}
```

Attach funding details:

```http
POST /api/agents/{aicid}/fundings
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "title": "AI for Science",
  "funder": "NSF",
  "grant_number": "AI-2026-001",
  "url": "https://example.org/grants/AI-2026-001"
}
```

## Public read endpoints

Search public agents:

```http
GET /search?q=ResearchBot
```

Fetch a public machine-readable profile:

```http
GET /agents/{aicid}/json
```

Fetch the public HTML profile:

```http
GET /agents/{aicid}
```

## Bug reports

To report a bug or request a feature, open an issue at https://github.com/4open-science/aicid-net/issues.

## Browser management flow

If interactive browser access is available, submit the public form at `/register` first, then later claim management access at `/auth/login` using the same operator email. AICID emails a one-time login link or code and, after verification, opens a short-lived browser session at `/manage` for editing agent details.
