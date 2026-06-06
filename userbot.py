"""
OmniGate Helper Userbot  (v2 — adaptive)
- DM lang ang sinasagot (smart keyword + variations)
- Hindi paulit-ulit: iniiwasan ang parehong reply sa parehong tao
- Varied reactions, hindi laging nagrereact (mas natural)
- HINDI sumasagot sa group/channel
- Pending join requests = OmniGate bot ang bahala
"""

import os
import re
import time
import asyncio
import random
import logging
from collections import defaultdict

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import ReactionEmoji
from telethon.tl.functions.messages import SendReactionRequest

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("userbot")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ.get("SESSION_STRING", "")

AUTO_REACT = os.environ.get("AUTO_REACT", "1") == "1"
REACT_CHANCE = float(os.environ.get("REACT_CHANCE", "1.0"))
REPLY_COOLDOWN = int(os.environ.get("REPLY_COOLDOWN", "30"))

REACTION_POOL = ["\U0001F44D", "\U0001F525", "\U0001F44C", "\u2764\uFE0F",
                 "\U0001F389", "\U0001F60A", "\U0001F44F", "\u2728",
                 "\U0001F60D", "\U0001F4AF", "\U0001F64C", "\U0001F914"]

KEYWORD_RULES = [
    {
        "name": "greeting",
        "patterns": [r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\byo\b",
                     r"kumusta", r"kamusta", r"\bmusta\b", r"good (morning|afternoon|evening)"],
        "replies": [
            "Hey there! \U0001F44B You're all set \u2014 your join request is handled automatically.",
            "Hi! Welcome aboard. Everything's been taken care of on our end. \U0001F64C",
            "Hello! Glad to have you here. Anything you need, just ask.",
            "Hey! \U0001F44B You're good to go. Let me know if you have any questions.",
        ],
    },
    {
        "name": "join",
        "patterns": [r"\bjoin\b", r"\baccept", r"\bpending\b", r"\brequest\b",
                     r"\bapprove", r"how (do|can) i (get in|join)", r"let me in"],
        "replies": [
            "No worries \u2014 your request gets approved automatically, usually within seconds. \u2705",
            "You're already in the queue. It clears on its own in a moment. \U0001F44D",
            "All join requests are auto-approved here, so just sit tight. \U0001F3AC",
            "That's handled automatically \u2014 give it a few seconds and you'll be in.",
        ],
    },
    {
        "name": "vip",
        "patterns": [r"\bvip\b", r"\bpremium\b", r"\bsubscribe", r"\bsub\b",
                     r"\bunlock\b", r"\bexclusive\b"],
        "replies": [
            "For VIP access, check the menu inside the bot \u2014 all the options are there. \U0001F3AC",
            "VIP details are in the pinned post and the bot menu. Worth a look! \u2728",
            "You can grab VIP straight from the bot. Tap the menu to see what's included.",
            "Premium unlocks the exclusive content \u2014 full breakdown is in the bot menu. \U0001F513",
        ],
    },
    {
        "name": "payment",
        "patterns": [r"\bpay\b", r"\bpayment\b", r"\bgcash\b", r"\bstars?\b",
                     r"\bbayad\b", r"\bprice\b", r"\bcost\b", r"\bmagkano\b",
                     r"how much", r"\bbuy\b"],
        "replies": [
            "Payments run through Telegram Stars right inside the bot \u2014 quick and secure. \u2B50",
            "Just tap the menu in the bot to see pricing and pay with Stars. \u2B50",
            "Everything's paid via Telegram Stars in-app. No external links needed. \U0001F44D",
            "Pricing and payment are all in the bot menu \u2014 Stars only, nice and simple.",
        ],
    },
    {
        "name": "help",
        "patterns": [r"\bhelp\b", r"\btulong\b", r"\bsupport\b", r"\bproblem\b",
                     r"\bissue\b", r"\bbug\b", r"\bstuck\b", r"\bnot working\b",
                     r"can'?t\b", r"\berror\b"],
        "replies": [
            "Got it \u2014 drop the details here and the admin will follow up shortly. \U0001F64F",
            "Sure, I can pass this along. What exactly are you running into?",
            "Tell me what's happening and I'll make sure it gets looked at.",
            "No problem. Send over the details and we'll sort it out for you.",
        ],
    },
    {
        "name": "thanks",
        "patterns": [r"\bthank", r"\bthanks\b", r"\bty\b", r"\bsalamat\b",
                     r"\bappreciate", r"\bnice\b", r"\bgreat\b", r"\bawesome\b"],
        "replies": [
            "Anytime! Enjoy. \U0001F60A",
            "You got it. Happy to help! \U0001F64C",
            "No problem at all \u2014 have fun!",
            "Glad I could help. Take care! \U0001F44D",
        ],
    },
    {
        "name": "bye",
        "patterns": [r"\bbye\b", r"\bgoodbye\b", r"\bcya\b", r"\bsee you\b",
                     r"\bgtg\b", r"\bingat\b", r"\bpaalam\b"],
        "replies": [
            "Catch you later! \U0001F44B",
            "Take care! See you around.",
            "Later! Reach out anytime you need something.",
        ],
    },
    {
        "name": "question",
        "patterns": [r"\?$", r"^(what|how|why|when|where|who|can|is|are|do|does)\b"],
        "replies": [
            "Good question \u2014 the bot menu has most of the answers. If not, the admin will jump in.",
            "Let me point you to the bot menu first; if you're still stuck, just say so.",
            "Most of that is covered in the bot menu. Anything specific I can clear up?",
        ],
    },
]

DEFAULT_REPLIES = [
    "Thanks for reaching out! You're all set here \u2014 the bot handles the rest. \U0001F916",
    "Got your message! Everything's running automatically. Let me know if you need anything.",
    "Appreciate the message! If you have a question, the bot menu's a good place to start.",
    "Noted! You're good to go. An admin will chime in if anything needs a human. \U0001F64C",
]

_last_reply_time = {}
_last_reply_text = {}
_last_emoji = {}
_seen_users = set()
_msg_count = defaultdict(int)


def on_cooldown(user_id):
    now = time.time()
    if now - _last_reply_time.get(user_id, 0) < REPLY_COOLDOWN:
        return True
    _last_reply_time[user_id] = now
    return False


def pick_non_repeating(user_id, options):
    if len(options) == 1:
        return options[0]
    last = _last_reply_text.get(user_id)
    choices = [o for o in options if o != last] or options
    chosen = random.choice(choices)
    _last_reply_text[user_id] = chosen
    return chosen


def match_rule(text):
    if not text:
        return None
    low = text.lower().strip()
    for rule in KEYWORD_RULES:
        for pat in rule["patterns"]:
            if re.search(pat, low):
                return rule
    return None


def build_reply(user_id, text):
    rule = match_rule(text)
    is_first_time = user_id not in _seen_users
    if rule:
        reply = pick_non_repeating(user_id, rule["replies"])
    else:
        reply = pick_non_repeating(user_id, DEFAULT_REPLIES)
    if is_first_time and (rule is None or rule["name"] in ("greeting", "join")):
        intro = random.choice([
            "",
            " (This account's automated to help with access \u2014 real admins step in when needed.)",
            "",
        ])
        reply = reply + intro
    return reply


if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("userbot_local", API_ID, API_HASH)


@client.on(events.NewMessage(incoming=True))
async def handle_dm(event):
    if not event.is_private:
        return
    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    user_id = event.sender_id
    text = event.raw_text or ""
    _msg_count[user_id] += 1

    if AUTO_REACT and random.random() < REACT_CHANCE:
        try:
            choices = [e for e in REACTION_POOL if e != _last_emoji.get(user_id)] or REACTION_POOL
            emoji = random.choice(choices)
            _last_emoji[user_id] = emoji
            await client(SendReactionRequest(
                peer=event.chat_id, msg_id=event.id,
                reaction=[ReactionEmoji(emoticon=emoji)],
            ))
        except Exception as e:
            log.warning("React failed: %s", e)

    if on_cooldown(user_id):
        log.info("Skipped reply to %s (cooldown)", user_id)
        _seen_users.add(user_id)
        return

    reply = build_reply(user_id, text)
    _seen_users.add(user_id)

    try:
        async with client.action(event.chat_id, "typing"):
            await asyncio.sleep(min(1.5 + len(reply) * 0.01, 4))
        await event.reply(reply)
        log.info("Replied to %s: %.50s", user_id, reply)
    except Exception as e:
        log.warning("Reply failed: %s", e)


def main():
    if not SESSION_STRING:
        log.error("Walang SESSION_STRING. Run login.py locally muna.")
        return
    log.info("OmniGate Helper userbot (v2 adaptive) starting...")
    client.start()
    log.info("Online. Adaptive DM replies + varied reactions active.")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
