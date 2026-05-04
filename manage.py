#!/usr/bin/env python3
"""
CLI for managing allowed users.

Usage:
    python manage.py list
    python manage.py add <user_id> [--note "some note"]
    python manage.py remove <user_id>
"""

import argparse
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from bot.db.crud import init_db
from bot.db.access_crud import (
    add_allowed_user,
    get_all_allowed_users,
    remove_allowed_user,
)


async def cmd_list() -> None:
    users = await get_all_allowed_users()
    if not users:
        print("No allowed users.")
        return
    print(f"{'user_id':<15} {'added_at':<22} note")
    print("-" * 60)
    for u in users:
        print(f"{u['user_id']:<15} {u['added_at']:<22} {u['note'] or ''}")


async def cmd_add(user_id: int, note: str | None) -> None:
    inserted = await add_allowed_user(user_id, note)
    if inserted:
        print(f"✅ User {user_id} added.")
    else:
        print(f"⚠️  User {user_id} is already allowed.")


async def cmd_remove(user_id: int) -> None:
    removed = await remove_allowed_user(user_id)
    if removed:
        print(f"✅ User {user_id} removed.")
    else:
        print(f"⚠️  User {user_id} was not in the allowed list.")


async def main() -> None:
    await init_db()

    parser = argparse.ArgumentParser(description="Manage bot allowed users")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all allowed users")

    p_add = sub.add_parser("add", help="Grant access to a user")
    p_add.add_argument("user_id", type=int, help="Telegram user ID")
    p_add.add_argument("--note", default=None, help="Optional label (e.g. username)")

    p_rm = sub.add_parser("remove", help="Revoke access from a user")
    p_rm.add_argument("user_id", type=int, help="Telegram user ID")

    args = parser.parse_args()

    if args.command == "list":
        await cmd_list()
    elif args.command == "add":
        await cmd_add(args.user_id, args.note)
    elif args.command == "remove":
        await cmd_remove(args.user_id)


if __name__ == "__main__":
    asyncio.run(main())
