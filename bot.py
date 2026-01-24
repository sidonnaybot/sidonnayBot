import socket
import requests
import time
import threading
import os

# ================= settings =================

CAPS_MIN_LETTERS = 14
CAPS_PERCENT = 0.7
CAPS_TIMEOUT = 60

BANNED_WORDS = [
    "пидор","пидорас","пидарас","педик","гомик","гомосек","куколд",
    "хач","чурка","узкоглазый","москаль","хохол","жиды","негр","ниггер",
    "даун","дауны","дауна","пидики","куколды","куколдов","пидиков","пидоров"
    "черномазый","черномазых","негров","нигеров","хохлов"
]

WARN_RESET_TIME = 600
BANNED_TIMEOUT = 600

ANNOUNCE_TEXT = "telegram t.me/sidonnay"
ANNOUNCE_INTERVAL = 900

# ================= env =================

SERVER = "irc.chat.twitch.tv"
PORT = 6667

BOT_NICK = os.getenv("BOT_NICK")
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")
CHANNEL = os.getenv("CHANNEL")

CLIENT_ID = os.getenv("CLIENT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
BROADCASTER_ID = os.getenv("BROADCASTER_ID")
MODERATOR_ID = os.getenv("MODERATOR_ID")

# ================= socket =================

sock = socket.socket()
sock.connect((SERVER, PORT))
sock.settimeout(1)

sock.send("CAP REQ :twitch.tv/commands twitch.tv/tags twitch.tv/membership\r\n".encode())
sock.send(f"PASS {OAUTH_TOKEN}\r\n".encode())
sock.send(f"NICK {BOT_NICK}\r\n".encode())
sock.send(f"JOIN {CHANNEL}\r\n".encode())

print("бот подключился к twitch")

# ================= status =================

caps_warns = {}
banned_warns = {}
stream_online = False

def reset_warns():
    while True:
        time.sleep(WARN_RESET_TIME)
        caps_warns.clear()
        banned_warns.clear()

threading.Thread(target=reset_warns, daemon=True).start()

# ================= helix =================

HEADERS = {
    "Client-ID": CLIENT_ID,
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def is_stream_online():
    r = requests.get(
        f"https://api.twitch.tv/helix/streams?user_id={BROADCASTER_ID}",
        headers=HEADERS
    )
    data = r.json()
    return bool(data.get("data"))

def get_user_id(username):
    r = requests.get(
        f"https://api.twitch.tv/helix/users?login={username}",
        headers=HEADERS
    )
    data = r.json()
    if data.get("data"):
        return data["data"][0]["id"]
    return None

def timeout_user(user_id, duration, reason):
    requests.post(
        "https://api.twitch.tv/helix/moderation/bans",
        headers=HEADERS,
        params={
            "broadcaster_id": BROADCASTER_ID,
            "moderator_id": MODERATOR_ID
        },
        json={
            "data": {
                "user_id": user_id,
                "duration": duration,
                "reason": reason
            }
        }
    )

def delete_message(msg_id):
    requests.delete(
        "https://api.twitch.tv/helix/moderation/chat",
        headers=HEADERS,
        params={
            "broadcaster_id": BROADCASTER_ID,
            "moderator_id": MODERATOR_ID,
            "message_id": msg_id
        }
    )

# ================= logics =================

def is_caps(msg):
    letters = [c for c in msg if c.isalpha()]
    if len(letters) < CAPS_MIN_LETTERS:
        return False
    return sum(c.isupper() for c in letters) / len(letters) >= CAPS_PERCENT

def contains_banned(msg):
    msg = msg.lower()
    return any(word in msg for word in BANNED_WORDS)

# ================= announce =================

def announce_loop():
    while True:
        time.sleep(ANNOUNCE_INTERVAL)
        if stream_online:
            requests.post(
                "https://api.twitch.tv/helix/chat/announcements",
                headers=HEADERS,
                params={
                    "broadcaster_id": BROADCASTER_ID,
                    "moderator_id": MODERATOR_ID
                },
                json={
                    "message": ANNOUNCE_TEXT,
                    "color": "purple"
                }
            )

threading.Thread(target=announce_loop, daemon=True).start()

# ================= stream check =================

def stream_status_loop():
    global stream_online
    while True:
        stream_online = is_stream_online()
        time.sleep(30)

threading.Thread(target=stream_status_loop, daemon=True).start()

# ================= main =================

while True:
    try:
        data = sock.recv(2048).decode("utf-8", errors="ignore")
    except socket.timeout:
        continue

    if data.startswith("PING"):
        sock.send("PONG :tmi.twitch.tv\r\n".encode())
        continue

    if not stream_online or "PRIVMSG" not in data:
        continue

    try:
        tags, msg = data.split(" PRIVMSG ", 1)
        message = msg.split(":", 1)[1]
        username = tags.split("display-name=", 1)[1].split(";", 1)[0].lower()
        msg_id = tags.split("id=", 1)[1].split(";", 1)[0]
    except:
        continue

    if username in ["sidonnay", "sidonnaybot", "sleepystephan", "lexus421991"]:
        continue

    # ===== ban word =====
    if contains_banned(message):
        delete_message(msg_id)
        banned_warns[username] = banned_warns.get(username, 0) + 1

        if banned_warns[username] >= 2:
            uid = get_user_id(username)
            if uid:
                timeout_user(uid, BANNED_TIMEOUT, "тайм-аут за повторный ban word")
        else:
            sock.send(f"PRIVMSG {CHANNEL} :@{username} предупреждение за ban word\r\n".encode())
        continue

    # ===== caps =====
    if is_caps(message):
        delete_message(msg_id)
        caps_warns[username] = caps_warns.get(username, 0) + 1

        if caps_warns[username] >= 2:
            uid = get_user_id(username)
            if uid:
                timeout_user(uid, CAPS_TIMEOUT, "тайм-аут за повторный caps lock")
        else:
            sock.send(f"PRIVMSG {CHANNEL} :@{username} выключите caps lock\r\n".encode())
        continue

    # ===== commands =====
    msg = message.lower().strip()

    if msg == "!tg":
        sock.send(f"PRIVMSG {CHANNEL} :https://t.me/sidonnay\r\n".encode())
    elif msg == "!boosty":
        sock.send(f"PRIVMSG {CHANNEL} :https://boosty.to/sidonnay\r\n".encode())
    elif msg == "!youtube":
        sock.send(f"PRIVMSG {CHANNEL} :https://youtube.com/@sidonnay\r\n".encode())
    elif msg == "!instagram":
        sock.send(f"PRIVMSG {CHANNEL} :https://instagram.com/sidonnay\r\n".encode())