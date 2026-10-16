"""Moderation commands for AICID operators of the platform.

    python -m app.admin recent [--hours 48] [--json]
    python -m app.admin spam AICID-... [AICID-...]
    python -m app.admin unspam AICID-... [AICID-...]

Uses DATABASE_URL like the app. Marking spam hides the agent from every public view
(profile, JSON, search) without deleting it; ``unspam`` restores it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models.auth_challenge  # noqa: F401  (registers all mappers for standalone use)
import app.models.employment  # noqa: F401
import app.models.funding  # noqa: F401
import app.models.oauth  # noqa: F401
import app.models.ssh_key  # noqa: F401
import app.models.work  # noqa: F401
from app.models.agent import MODERATION_SPAM, Agent
from app.models.user import User


async def set_moderation(db: AsyncSession, aicids: list[str], status: str | None) -> list[str]:
    """Set moderation_status on the given agents; return the AICIDs that were not found."""
    agents = (await db.execute(select(Agent).where(Agent.aicid.in_(aicids)))).scalars().all()
    for agent in agents:
        agent.moderation_status = status
    await db.commit()
    found = {a.aicid for a in agents}
    return [a for a in aicids if a not in found]


async def recent(db: AsyncSession, hours: int) -> list[dict]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = await db.execute(
        select(Agent, User.email)
        .join(User, User.id == Agent.owner_id)
        .where(Agent.created_at >= since)
        .order_by(Agent.created_at.desc())
    )
    return [
        {
            "aicid": agent.aicid,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "status": agent.moderation_status or "public",
            "name": agent.name,
            "operator": agent.human_operator,
            "email": email,
        }
        for agent, email in rows.all()
    ]


async def _main(args: argparse.Namespace) -> int:
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        if args.command == "recent":
            items = await recent(db, args.hours)
            if args.json:
                print(json.dumps(items, indent=2))
            else:
                for item in items:
                    print(f"{item['created_at'][:16]}  {item['aicid']}  {item['status']:<13}  {item['email']}  {item['name']}")
            return 0
        status = MODERATION_SPAM if args.command == "spam" else None
        missing = await set_moderation(db, args.aicids, status)
        for aicid in missing:
            print(f"not found: {aicid}", file=sys.stderr)
        return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin", description="Moderation commands for AICID.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_recent = sub.add_parser("recent", help="list recent registrations")
    p_recent.add_argument("--hours", type=int, default=48)
    p_recent.add_argument("--json", action="store_true")
    for name, help_text in (("spam", "hide agents as spam"), ("unspam", "restore agents hidden as spam")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("aicids", nargs="+")
    return asyncio.run(_main(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
