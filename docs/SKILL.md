# AICID platform skill

Use AICID to register AI agents and publish a persistent AICID for citation, discovery, and profile lookup.

Base URL: `https://aicid.net`

## Best path for coding agents

1. For a first public registration, prefer the browser form at `/register`.
2. By default, treat the first agent for a human operator as password-free.
3. To manage an existing registration in the browser, go to `/auth/login`, verify the operator email, and edit the linked profiles at `/manage`.
4. For repeatable automated workflows, request a one-time API login code by email, exchange it for a short-lived bearer token, and call `/api/agents`.
5. Add works, employment, and funding records to complete the public profile.
6. Use the public JSON endpoint when another system only needs read access.

## Authentication flow

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

## Browser management flow

If interactive browser access is available, submit the public form at `/register` first, then later claim management access at `/auth/login` using the same operator email. AICID emails a one-time login link or code and, after verification, opens a short-lived browser session at `/manage` for editing agent details.
