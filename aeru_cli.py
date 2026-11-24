#!/usr/bin/env python3
"""Thin CLI runner for the AERU voice MCP server.

Spawns aeru_voice_mcp.py over stdio (with the full environment, so network
and credential helpers keep working) and calls one tool.

Usage:
  python3 aeru_cli.py whoami
  python3 aeru_cli.py get_home_timeline --limit 10
  python3 aeru_cli.py get_notifications --limit 10
  python3 aeru_cli.py get_user_notes --username kumiko --limit 5
  python3 aeru_cli.py get_note --note-id <id>
  python3 aeru_cli.py post_note --text "本文"          # confirm with the user first
  python3 aeru_cli.py reply_to_note --note-id <id> --text "返信文"
  python3 aeru_cli.py react_to_note --note-id <id> --reaction ❤️
"""
import argparse
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


async def run(tool, args):
    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(HERE, "aeru_voice_mcp.py")],
        cwd=HERE,
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            return "".join(c.text for c in result.content if c.type == "text")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tool")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--username")
    parser.add_argument("--note-id", dest="note_id")
    parser.add_argument("--text")
    parser.add_argument("--reaction")
    a = parser.parse_args()

    args = {}
    if a.limit is not None:
        args["limit"] = a.limit
    if a.username is not None:
        args["username"] = a.username
    if a.note_id is not None:
        args["note_id"] = a.note_id
    if a.text is not None:
        args["text"] = a.text
    if a.reaction is not None:
        args["reaction"] = a.reaction

    print(asyncio.run(run(a.tool, args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
