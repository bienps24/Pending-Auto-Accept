"""
login.py  —  ISANG BESES LANG ITO PATAKBUHIN, SA LOCAL PC MO.

Layunin: mag-login gamit ang phone number mo at mag-generate ng SESSION_STRING.
Yung SESSION_STRING ang ilalagay mo sa Railway environment variables.

PAANO:
1. pip install telethon
2. Itakda ang API_ID at API_HASH (galing sa my.telegram.org):
       Windows (PowerShell):
           $env:API_ID="123456"; $env:API_HASH="abc123..."
       Mac/Linux:
           export API_ID=123456
           export API_HASH=abc123...
3. python login.py
4. Ilagay ang phone number (+639667109658), login code, at 2FA password kung meron.
5. I-copy ang mahabang SESSION_STRING na lalabas. Yan ang ilalagay sa Railway.

WAG MONG IPO-POST ANG SESSION_STRING KAHIT KANINO. Para na rin syang password
ng account mo.
"""

import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n" + "=" * 60)
    print("ETO ANG SESSION STRING MO (i-copy lahat, isang linya):")
    print("=" * 60)
    print(client.session.save())
    print("=" * 60)
    print("Ilagay ito sa Railway: Variables -> SESSION_STRING")
    print("WAG i-share kahit kanino. Para syang password.")
    print("=" * 60 + "\n")
