#!/usr/bin/env python3
"""
Telegram Ring Notification
Uses your second Telegram account to ring your main phone.
Run this once to create a session, then it can be used from GitHub Actions.
"""

import os
import asyncio
import hashlib
import random
import secrets
from telethon import TelegramClient, functions, types

# Load .env if present (no external dependency)
def _load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if value and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except OSError:
        pass

_load_env_file()

# Configuration - Get from https://my.telegram.org
API_ID_RAW = os.environ.get("TELEGRAM_API_ID", "")
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

try:
    API_ID = int(API_ID_RAW)
except ValueError:
    API_ID = 0

# Phone/username to ring (your main account)
TARGET_USER = os.environ.get("TELEGRAM_TARGET_USER", "")  # Can be username or phone

# Ring duration in seconds before disconnecting
RING_DURATION = int(os.environ.get("RING_DURATION", "10"))


async def get_g_a_hash(client: TelegramClient) -> bytes:
    """Generate a valid g_a_hash for phone call request."""
    dh_config = await client(functions.messages.GetDhConfigRequest(version=0, random_length=256))
    if isinstance(dh_config, types.messages.DhConfigNotModified):
        # If this ever happens, retry with version 0 again.
        dh_config = await client(functions.messages.GetDhConfigRequest(version=0, random_length=256))

    p_bytes = dh_config.p
    g = dh_config.g

    p = int.from_bytes(p_bytes, "big")
    # 256-byte random secret exponent, reduced modulo p-1
    a = int.from_bytes(secrets.token_bytes(256), "big") % (p - 1) + 1
    g_a = pow(g, a, p)
    g_a_bytes = g_a.to_bytes(len(p_bytes), "big")

    return hashlib.sha256(g_a_bytes).digest()


async def ring_phone(target_user: str, duration: int = 10):
    """
    Ring a Telegram user's phone.
    Initiates a call, lets it ring for duration seconds, then cancels.
    """
    print(f"[Ring] Starting Telegram ring notification to {target_user}...")
    
    # Create client
    if SESSION_STRING:
        # Use session string from environment (for GitHub Actions)
        from telethon.sessions import StringSession
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    else:
        # Use file session (for local development)
        client = TelegramClient("ring_session", API_ID, API_HASH)
    
    try:
        await client.start()
        me = await client.get_me()
        print(f"[Ring] Logged in as {me.first_name} (@{me.username})")
        
        # Get target user
        user = await client.get_entity(target_user)
        print(f"[Ring] Target: {user.first_name} (@{user.username if hasattr(user, 'username') else 'N/A'})")
        
        # Request call - this makes the phone ring!
        print(f"[Ring] Initiating call...")
        
        call_protocol = types.PhoneCallProtocol(
            min_layer=65,
            max_layer=92,
            library_versions=["3.0.0"],
            udp_p2p=True,
            udp_reflector=True
        )
        
        g_a_hash = await get_g_a_hash(client)
        result = await client(functions.phone.RequestCallRequest(
            user_id=user,
            random_id=random.randint(0, 2**31 - 1),
            g_a_hash=g_a_hash,
            protocol=call_protocol,
            video=False
        ))
        
        print(f"[Ring] 📞 Phone is ringing!")
        
        # Get the call object
        phone_call = result.phone_call
        call_id = phone_call.id
        access_hash = phone_call.access_hash
        
        # Let it ring
        print(f"[Ring] Ringing for {duration} seconds...")
        await asyncio.sleep(duration)
        
        # Discard the call
        print(f"[Ring] Ending call...")
        await client(functions.phone.DiscardCallRequest(
            peer=types.InputPhoneCall(id=call_id, access_hash=access_hash),
            duration=0,
            reason=types.PhoneCallDiscardReasonHangup(),
            connection_id=0
        ))
        
        print(f"[Ring] ✅ Ring notification completed!")
        return True
        
    except Exception as e:
        print(f"[Ring] ❌ Error: {e}")
        return False
        
    finally:
        await client.disconnect()


async def main():
    """Main entry point."""
    if not API_ID or not API_HASH:
        print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH required")
        print("Get them from https://my.telegram.org")
        return
    
    if not TARGET_USER:
        print("Error: TELEGRAM_TARGET_USER required (username or phone)")
        return
    
    await ring_phone(TARGET_USER, RING_DURATION)


if __name__ == "__main__":
    asyncio.run(main())
