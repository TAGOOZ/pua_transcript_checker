PUA Transcript Checker + Telegram Ring (GitHub Actions)

Needs 2 Telegram accounts:
1) main account to receive ring
2) secondary account to place the call (session)

Telegram bot (message alert)
1) open https://web.telegram.org/k/#@BotFather
2) create bot, copy token
3) message bot, then open:
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
4) copy chat_id

Telegram ring secrets (voice call)
1) go https://my.telegram.org
2) create app -> get api_id + api_hash
3) run python3 telegram_login.py
4) save printed session string

GitHub Actions secrets
Repo -> Settings -> Secrets and variables -> Actions
Add:
PUA_USERNAME
PUA_PASSWORD
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TELEGRAM_API_ID
TELEGRAM_API_HASH
TELEGRAM_SESSION
TELEGRAM_TARGET_USER
ENABLE_TELEGRAM_RING (true)
RING_DURATION (10)

Notes
- ring happens only when 2025 Fall found
- keep TELEGRAM_SESSION private
- Tip: Telethon can send messages from the secondary account, so you can skip the bot in future (not implemented yet).
