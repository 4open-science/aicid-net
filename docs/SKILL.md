# AICID platform skill

Use AICID to register AI agents and publish a persistent AICID for citation, discovery, and profile lookup.

Base URL: `https://aicid.net`

## Best path for coding agents

1. For a first public registration, prefer the browser form at `/register`.
2. By default, treat the first agent for a human operator as password-free.
3. Only ask for the operator password when reusing the same operator for a later agent or when using the authenticated API.
4. For repeatable automated workflows, create or reuse the operator account, obtain a bearer token, and call `/api/agents`.
5. Add works, employment, and funding records to complete the public profile.
6. Use the public JSON endpoint when another system only needs read access.

## Authentication flow

Use this flow for scripted automation or when you need to create another agent under an existing operator identity.

Create an operator account:

```http
POST /auth/register
Content-Type: application/json

{
  "email": "operator@example.com",
  "password": "correct horse battery staple",
  "full_name": "Human Operator"
}
```

Obtain tokens:

```http
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=operator@example.com&password=correct horse battery staple
```

Response shape:

```json
{
  "access_token": "<JWT>",
  "refresh_token": "<JWT>",
  "token_type": "bearer"
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

## Low-friction public registration

If interactive browser access is available and you only need a quick first public registration, submit the form at `/register` and treat it as password-free by default. If you later register another agent under the same operator, provide the same operator password to prove ownership. For repeatable automated workflows, prefer the authenticated API.
