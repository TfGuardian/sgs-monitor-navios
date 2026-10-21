"""Deliver committed vessel monitoring events to VOS, without sending WhatsApp messages."""
from __future__ import annotations

import argparse
import os
import re
import time
from urllib.parse import urlparse

import requests


def integration_settings():
    url = os.getenv("VOS_INTEGRATION_URL", "").strip()
    secret = os.getenv("VOS_INTEGRATION_SECRET", "").strip()
    if not url and not secret:
        return None
    parsed = urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(r"/functions/v1/[A-Za-z0-9_-]+", parsed.path)
            or len(secret) < 32):
        raise ValueError("Invalid VOS integration configuration.")
    return url, secret


def deliver_pending(client, *, limit=10, budget_seconds=15, post=None):
    """Bounded drain. Stable delivery IDs make a lost acknowledgement safe."""
    settings = integration_settings()
    if settings is None:
        return 0
    url, secret = settings
    post = post or requests.post
    started = time.monotonic()
    sent = 0
    for _ in range(limit):
        remaining = budget_seconds - (time.monotonic() - started)
        if remaining <= 0:
            break
        item = client.rpc("claim_vos_delivery").execute().data
        if not item:
            break
        success, error = False, None
        try:
            response = post(
                url, headers={"Authorization": f"Bearer {secret}"},
                json=item["payload"], timeout=(min(3, remaining), min(5, remaining)),
                allow_redirects=False,
            )
            success = 200 <= response.status_code < 300
            if not success:
                error = f"HTTP_{response.status_code}"
        except requests.RequestException:
            # Never log request headers, response bodies, or secret-bearing exceptions.
            error = "TRANSPORT_ERROR"
        acknowledged = client.rpc("finish_vos_delivery", {
            "p_id": item["id"], "p_token": item["leaseToken"],
            "p_success": success, "p_error": error,
        }).execute().data
        if not success or not acknowledged:
            reason = error if not success else "ACK_NOT_CONFIRMED"
            print(f"VOS delivery deferred ({reason}); queued for retry.", flush=True)
            break
        sent += 1
    return sent


def sync_safely(client):
    try:
        count = deliver_pending(client)
        if count:
            print(f"VOS: {count} delivery(s) confirmed.", flush=True)
    except Exception as exc:
        # A VOS outage must never interrupt collection or reveal credentials.
        print(f"VOS sync deferred ({type(exc).__name__}).", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Send queued vessel monitoring updates to VOS")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    from vessel_monitor.config import criar_supabase
    if integration_settings() is None:
        parser.error("Configure VOS_INTEGRATION_URL and VOS_INTEGRATION_SECRET.")
    client = criar_supabase(administrativo=True)
    while True:
        sync_safely(client)
        if args.once:
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
