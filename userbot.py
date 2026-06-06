"""
OmniGate Helper Userbot  (v3)
- DM lang ang sinasagot (smart keyword + variations)
- Lahat ng reply ay tungkol sa OmniGate / pending request / access
- Hindi paulit-ulit; varied reactions; tahimik sa group/channel
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

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
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
            "Hey there! \U0001F44B Your join request is being processed \u2014 you'll be approved automatically.",
            "Hi! Welcome. Your pending request is in the queue and will be accepted shortly. \u2705",
            "Hello! No action needed on your end \u2014 your request gets approved for you. \U0001F64C",
            "Hey! \U0001F44B Just sit tight, your request is handled automatically.",
        ],
    },
    {
        "name": "join_pending",
        "patterns": [r"\bjoin\b", r"\baccept", r"\bpending\b", r"\brequest\b",
                     r"\bapprove", r"\bwait", r"how long", r"\bqueue\b",
                     r"how (do|can) i (get in|join)", r"let me in", r"not in yet",
                     r"still waiting", r"\bin na\b", r"kelan", r"kailan"],
        "replies": [
            "Your join request gets approved automatically \u2014 usually within a short while. No need to re-send. \u2705",
            "You're already in the queue. Old pending requests get cleared automatically, so just hold on. \U0001F44D",
            "No worries \u2014 pending requests are accepted for you. Give it a bit and you'll be in. \U0001F3AC",
            "That's all automated. Your request will go through; please don't cancel or re-request.",
            "It's being handled \u2014 approvals happen automatically, including older pending requests. \u23F3",
        ],
    },
    {
        "name": "denied_problem",
        "patterns": [r"\bdenied\b", r"\brejected\b", r"\bdeclined\b", r"\bblocked\b",
                     r"can'?t (join|get in)", r"not working", r"\bstuck\b", r"\berror\b",
                     r"\bhindi ako\b", r"di pa rin", r"wala pa rin"],
        "replies": [
            "If you're still not in after a while, try sending the join request again \u2014 it'll be picked up automatically.",
            "Sometimes it takes a moment. If it's been long, re-request once and it should clear. \U0001F44D",
            "No problem \u2014 re-send the join request and it'll be processed. Let me know if it still doesn't work.",
        ],
    },
    {
        "name": "what_is_this",
        "patterns": [r"what (is|are) (this|you)", r"\bwho are you\b", r"\bbot\b",
                     r"\bautomated\b", r"sino (ka|to)", r"ano (to|ito|ka)", r"\bomnigate\b",
                     r"\bhelper\b"],
        "replies": [
            "This account is an automated helper that takes care of pending join requests, so you don't have to wait on a manual approval. \U0001F916",
            "I'm a helper account \u2014 I make sure pending requests get accepted automatically. \u2705",
            "Automated helper here! My job is to clear pending join requests so members get in smoothly.",
        ],
    },
    {
        "name": "help",
        "patterns": [r"\bhelp\b", r"\btulong\b", r"\bsupport\b", r"\bproblem\b",
                     r"\bissue\b", r"\bconcern\b", r"\bask\b", r"\btanong\b"],
        "replies": [
            "Sure \u2014 if it's about a join request, it's handled automatically. For anything else, an admin will follow up here. \U0001F64F",
            "Happy to help. What's going on? If it's about access, your request is already being processed.",
            "Tell me the details \u2014 if it needs a human, the admin will jump in shortly.",
        ],
    },
    {
        "name": "thanks",
        "patterns": [r"\bthank", r"\bthanks\b", r"\bty\b", r"\bsalamat\b",
                     r"\bappreciate", r"\bnice\b", r"\bgreat\b", r"\bok\b", r"\bokay\b", r"\bsige\b"],
        "replies": [
            "Anytime! Enjoy. \U0001F60A",
            "You got it \u2014 welcome in! \U0001F64C",
            "No problem at all. \U0001F44D",
            "Glad to help. Take care!",
        ],
    },
    {
        "name": "bye",
        "patterns": [r"\bbye\b", r"\bgoodbye\b", r"\bcya\b", r"\bsee you\b",
                     r"\bingat\b", r"\bpaalam\b"],
        "replies": [
            "Take care! \U0001F44B",
            "See you around \u2014 welcome aboard!",
            "Later! Reach out anytime.",
        ],
    },
]

DEFAULT_REPLIES = [
    "Thanks for reaching out! If this is about a join request, it's being approved automatically \u2014 no action needed. \u2705",
    "Got your message! Your pending request is handled for you. An admin will reply if anything else is needed. \U0001F916",
    "Noted! Access is taken care of automatically. Let me know if you have a specific question.",
    "You're all set \u2014 pending requests get accepted automatically. \U0001F64C",
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
    if rule:
        return pick_non_repeating(user_id, rule["replies"])
    return pick_non_repeating(user_id, DEFAULT_REPLIES)


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
    log.info("OmniGate Helper userbot (v3) starting...")
    client.start()
    log.info("Online. OmniGate-focused DM replies + varied reactions active.")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
