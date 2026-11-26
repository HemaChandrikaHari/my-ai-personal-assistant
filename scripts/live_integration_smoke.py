#!/usr/bin/env python3
"""Read-only live smoke test for the owner's connected provider accounts.

Required environment:
  ASSISTANT_API_URL       e.g. http://localhost:8000
  ASSISTANT_BEARER_TOKEN  short-lived API access token (production), OR
  ASSISTANT_USER_ID       development-only identity (local development)

This script never prints tokens, email content, task names, or calendar details.
It does not create, modify, send, or delete provider data.
"""
import os
import sys
import argparse

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-blueticks",
        action="store_true",
        help="Also run Blueticks MCP tool discovery (read-only; does not call tools).",
    )
    args = parser.parse_args()

    base_url = os.getenv("ASSISTANT_API_URL", "http://localhost:8000").rstrip("/")
    token = os.getenv("ASSISTANT_BEARER_TOKEN", "")
    user_id = os.getenv("ASSISTANT_USER_ID", "")
    if token:
        headers = {"Authorization": f"Bearer {token}"}
    elif user_id:
        headers = {"X-User-ID": user_id}
    else:
        print("FAIL: set ASSISTANT_BEARER_TOKEN or local-development ASSISTANT_USER_ID")
        return 2

    failures = 0
    with httpx.Client(base_url=base_url, headers=headers, timeout=30) as client:
        for path in ("/health", "/ready"):
            try:
                response = client.get(path)
                response.raise_for_status()
                print(f"PASS {path}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {path}: {type(exc).__name__}")

        try:
            response = client.get("/api/v1/connections")
            response.raise_for_status()
            connections = {item["provider"]: item for item in response.json()}
        except Exception as exc:
            print(f"FAIL /api/v1/connections: {type(exc).__name__}")
            return 1

        for provider in ("google", "todoist"):
            connected = bool(connections.get(provider, {}).get("connected"))
            if not connected:
                failures += 1
                print(f"FAIL {provider}: account is not connected")
                continue
            print(f"PASS {provider}: OAuth connection exists")

        google = connections.get("google", {})
        scopes = set(google.get("scopes", []))
        if google.get("connected") and "https://www.googleapis.com/auth/gmail.readonly" in scopes:
            try:
                response = client.get("/api/v1/google/gmail/messages", params={"max_results": 1})
                response.raise_for_status()
                count = len(response.json().get("messages", []))
                print(f"PASS Gmail API: read succeeded ({count} message metadata item(s), content not displayed)")
            except Exception as exc:
                failures += 1
                print(f"FAIL Gmail API: {type(exc).__name__}")
        elif google.get("connected"):
            failures += 1
            print("FAIL Gmail API: granted Gmail read scope is missing")

        if google.get("connected") and "https://www.googleapis.com/auth/calendar.events" in scopes:
            try:
                response = client.get("/api/v1/google/calendar/events", params={"max_results": 1})
                response.raise_for_status()
                count = len(response.json().get("items", []))
                print(f"PASS Google Calendar API: read succeeded ({count} event(s), details not displayed)")
            except Exception as exc:
                failures += 1
                print(f"FAIL Google Calendar API: {type(exc).__name__}")
        elif google.get("connected"):
            failures += 1
            print("FAIL Google Calendar API: granted Calendar scope is missing")

        todoist = connections.get("todoist", {})
        todoist_scopes = set(todoist.get("scopes", []))
        if todoist.get("connected") and ({"data:read", "data:read_write"} & todoist_scopes):
            try:
                response = client.get("/api/v1/todoist/tasks")
                response.raise_for_status()
                payload = response.json()
                tasks = payload.get("results", payload.get("tasks", []))
                print(f"PASS Todoist API: read succeeded ({len(tasks)} task(s), details not displayed)")
            except Exception as exc:
                failures += 1
                print(f"FAIL Todoist API: {type(exc).__name__}")
        elif todoist.get("connected"):
            failures += 1
            print("FAIL Todoist API: granted read scope is missing")

        if args.check_blueticks:
            try:
                response = client.post("/api/v1/integrations/blueticks/discover")
                response.raise_for_status()
                names = [tool.get("name", "") for tool in response.json().get("tools", [])]
                print(f"PASS Blueticks MCP discovery: {len(names)} tool(s) discovered; no tool invoked")
            except Exception as exc:
                failures += 1
                print(f"FAIL Blueticks MCP discovery: {type(exc).__name__}")

    if failures:
        print(f"\nRESULT: {failures} live check(s) failed.")
        return 1
    print("\nRESULT: all requested read-only live integration checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
