#!/usr/bin/env python3
"""
Telegram Account Login Script
Run this once to create a Telethon StringSession for your second account.
The session string can be stored in GitHub Secrets.
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import sys

print("=" * 50)
print("Telegram Account Login for Voice Calls (Telethon)")
print("=" * 50)
print()
print("You need to get API credentials from https://my.telegram.org")
print("1. Go to https://my.telegram.org/auth")
print("2. Login with your phone number")
print("3. Click 'API development tools'")
print("4. Create an app (any name/description)")
print("5. Copy the api_id and api_hash")
print()

api_id_raw = input("Enter your api_id: ").strip()
api_hash = input("Enter your api_hash: ").strip()

try:
    api_id = int(api_id_raw)
except ValueError:
    print("Error: api_id must be a number.")
    sys.exit(1)

print()
print("Now logging into your Telegram account...")
print("You'll receive a code on Telegram or SMS.")
print()

# Create client and login
client = TelegramClient(StringSession(), api_id, api_hash)

with client:
    client.start()
    me = client.get_me()
    session_string = client.session.save()

print()
print("=" * 50)
print(f"✅ Successfully logged in as: {me.first_name} (@{me.username})")
print("=" * 50)
print()
print("Session string created (store this as a secret):")
print(session_string)
print()
print("Next steps:")
print("1. Add these to GitHub secrets:")
print(f"   TELEGRAM_API_ID={api_id}")
print(f"   TELEGRAM_API_HASH={api_hash}")
print("2. Add the session string as TELEGRAM_SESSION secret")
