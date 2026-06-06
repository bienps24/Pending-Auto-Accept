"""
OmniGate Helper Userbot
- DM lang ang sinasagot (keyword-based auto-reply)
- Auto-react sa DM messages ng user
- HINDI sumasagot sa group/channel
- Pending join requests = OmniGate bot ang bahala (hindi userbot)
"""

import os
import re
import logging
import random
from telethon import TelegramClient, events
from telethon.tl.types import ReactionEmoji
from telethon.tl.functions.messages import SendReactionRequest

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("userbot")

# ---------------------------------------------------------------------------
# Config (galing sa environment variables — wag i-hardcode)
# ---------------------------------------------------------------------------
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# Kung gusto mong i-on/off ang auto-react
AUTO_REACT = os.environ.get("AUTO_REACT", "1") == "1"

# Default reaction emoji sa bawat DM
REACT_EMOJI = os.environ.get("REACT_EMOJI", "\U0001F44D")  # 👍

# ---------------------------------------------------------------------------
# Keyword rules
# Each rule: list of trigger patterns (regex, case-insensitive) -> reply
# Inuna ang mas specific na rules. Ang unang tumama, yun ang sasagot.
# ---------------------------------------------------------------------------
KEYWORD_RULES = [
    {
        "patterns": [r"\bhi\b", r"\bhello\b", r"\bhey\b", r"kumusta", r"kamusta", r"musta"],
        "replies": [
            "Hello! 👋 This account is managed by @omnigatebot to help accept your pending join requests automatically.",
        ],
    },
    {
        "patterns": [r"\bvip\b", r"premium", r"subscribe", r"sub\b"],
        "replies": [
            "For VIP access, check the pinned message in the channel or tap the menu in @omnigatebot. 🎬",
        ],
    },
    {
        "patterns": [r"\bjoin\b", r"\baccept\b", r"pending", r"request", r"approve"],
        "replies": [
            "Your join request will be accepted automatically by @omnigatebot. Wait lang ng a few seconds. ✅",
        ],
    },
    {
        "patterns": [r"\bpay", r"\bgcash\b", r"\bstars?\b", r"bayad", r"price", r"magkano", r"how much"],
        "replies": [
            "Payments are handled via Telegram Stars inside the bot. Tap the menu in @omnigatebot to see the options. ⭐",
        ],
    },
    {
        "patterns": [r"\bhelp\b", r"tulong", r"support", r"problem", r"issue", r"\bbug\b"],
        "replies": [
            "Need help? Send your concern here and the admin will get back to you. Salamat sa pasensya! 🙏",
        ],
    },
    {
        "patterns": [r"salamat", r"thank", r"thanks", r"ty\b"],
        "replies": [
            "Walang anuman! 😊 Enjoy!",
        ],
    },
]

# Fallback kung walang tumama sa keywords
DEFAULT_REPLY = (
    "Thanks for your message! 🤖 This account is automated to help with "
    "join requests via @omnigatebot. An admin will reply if needed."
)

# ---------------------------------------------------------------------------
# Anti-spam: huwag paulit-ulit sumagot sa parehong tao sa loob ng X seconds
# ---------------------------------------------------------------------------
import time
REPLY_COOLDOWN = int(os.environ.get("REPLY_COOLDOWN", "30"))  # seconds
_last_reply = {}  # user_id -> timestamp


def on_cooldown(user_id: int) -> bool:
    now = time.time()
    last = _last_reply.get(user_id, 0)
    if now - last < REPLY_COOLDOWN:
        return True
    _last_reply[user_id] = now
    return False


def match_reply(text: str) -> str:
    """Hanapin ang tamang reply base sa keyword. None kung walang match (gamit default)."""
    if not text:
        return DEFAULT_REPLY
    low = text.lower()
    for rule in KEYWORD_RULES:
        for pat in rule["patterns"]:
            if re.search(pat, low):
                return random.choice(rule["replies"])
    return DEFAULT_REPLY


# ---------------------------------------------------------------------------
# Client setup (StringSession para hindi kailangan ng file sa Railway)
# ---------------------------------------------------------------------------
from telethon.sessions import StringSession

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    # Local lang ito gagamitin para mag-generate ng session (tingnan login.py)
    client = TelegramClient("userbot_local", API_ID, API_HASH)


# ---------------------------------------------------------------------------
# Event handler: DM messages lang (private), galing sa ibang tao
# ---------------------------------------------------------------------------
@client.on(events.NewMessage(incoming=True))
async def handle_dm(event):
    # SADya lang DM (private chat). Skip groups/channels.
    if not event.is_private:
        return

    sender = await event.get_sender()
    # Skip kung galing sa ibang bot (iwas loop)
    if getattr(sender, "bot", False):
        return

    user_id = event.sender_id
    text = event.raw_text or ""

    # ---- Auto-react ----
    if AUTO_REACT:
        try:
            await client(
                SendReactionRequest(
                    peer=event.chat_id,
                    msg_id=event.id,
                    reaction=[ReactionEmoji(emoticon=REACT_EMOJI)],
                )
            )
        except Exception as e:
            log.warning("React failed: %s", e)

    # ---- Auto-reply (with cooldown) ----
    if on_cooldown(user_id):
        log.info("Skipped reply to %s (cooldown)", user_id)
        return

    reply = match_reply(text)
    try:
        await event.reply(reply)
        log.info("Replied to %s: %.40s", user_id, reply)
    except Exception as e:
        log.warning("Reply failed: %s", e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not SESSION_STRING:
        log.error(
            "Walang SESSION_STRING. Run mo muna ang login.py locally para "
            "ma-generate ito, tapos ilagay sa Railway environment variables."
        )
        return
    log.info("OmniGate Helper userbot starting...")
    client.start()
    log.info("Userbot is online. DM auto-reply + auto-react active.")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
