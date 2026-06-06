# OmniGate Helper Userbot

DM auto-reply (keyword-based) + auto-react. DM lang ang sinasagot, hindi
sumasagot sa group/channel. Pending join requests = @omnigatebot ang bahala.

## Setup (one-time, sa LOCAL PC mo)

1. Kunin ang API_ID at API_HASH sa https://my.telegram.org
2. Local lang muna:
   ```
   pip install telethon
   export API_ID=123456
   export API_HASH=your_api_hash
   python login.py
   ```
3. I-login gamit phone +639667109658 + code + 2FA (kung meron).
4. I-copy ang SESSION_STRING na lalabas.

## Deploy sa Railway

1. Push lahat ng files na ito sa GitHub repo (hal. `omnigate-helper`).
2. Railway -> New Project -> Deploy from GitHub.
3. Sa Variables, ilagay:
   - `API_ID`         = (galing my.telegram.org)
   - `API_HASH`       = (galing my.telegram.org)
   - `SESSION_STRING` = (galing login.py)
4. Optional variables:
   - `AUTO_REACT`     = 1   (1=on, 0=off)
   - `REACT_EMOJI`    = 👍  (default reaction)
   - `REPLY_COOLDOWN` = 30  (seconds bago ulit sumagot sa parehong tao)
5. Railway auto-detects Procfile (worker). Done.

## Pag-edit ng keyword replies

Buksan ang `userbot.py`, hanapin ang `KEYWORD_RULES`. Bawat rule may
`patterns` (regex triggers) at `replies` (pwede maraming variant, random
pick). Ang `DEFAULT_REPLY` ang sasagot kung walang tumamang keyword.

## Babala

- SESSION_STRING = parang password ng account mo. WAG i-share.
- Iwas mass-messaging/spam para hindi ma-ban ang account.
- Kung mag-iiba ka ng password o mag-logout sa session, kailangang
  i-regenerate ang SESSION_STRING.
