"""Create the first internal admin user. Password is never stored in the repo.

Usage:
  python -m app.admin.bootstrap create-admin --email ops@refiq.ru --role super

Password is read from ADMIN_BOOTSTRAP_PASSWORD or prompted on stdin.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from app.admin.auth.service import AdminAuthService
from app.admin.permissions import AdminRole
from app.core.database import async_session_factory


async def create_admin(email: str, password: str, role: str) -> None:
    async with async_session_factory() as session:
        admin = await AdminAuthService(session).create(email, password, role)
        await session.commit()
        print(f"Created admin id={admin.id} email={admin.email} role={admin.role}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin.bootstrap")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Create an internal admin user")
    create.add_argument("--email", required=True)
    create.add_argument("--role", default=AdminRole.SUPER.value, choices=[item.value for item in AdminRole])
    args = parser.parse_args(argv)

    if args.command == "create-admin":
        password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
        if not password:
            password = getpass.getpass("Admin password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters", file=sys.stderr)
            return 1
        asyncio.run(create_admin(args.email, password, args.role))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
