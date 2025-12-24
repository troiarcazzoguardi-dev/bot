#!/usr/bin/env python3
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import subprocess
import os
import signal
import socket

# ================= CONFIG =================
TOKEN = "7857611131:AAExGDSgM7YkTZDDF-wA1_jOdCVFEXQ9buc"  # inserisci il tuo token valido
AUTHORIZED_ID = 5699538596  # tuo chat_id numerico
# =========================================

process = None
LAST_CMD = None
HOSTNAME = socket.gethostname()

# ----- /start -----
def start(update, context):
    if update.effective_user.id != AUTHORIZED_ID:
        return
    update.message.reply_text(
        f"🤖 Bot attivo su: {HOSTNAME}\n"
        "Usa /run ALL <comando> per eseguirlo su tutte le VNC attive.\n"
        "Puoi usare /stop per fermare e /status per verificare lo stato."
    )

# ----- /run -----
def run_command(update, context):
    global process, LAST_CMD
    if update.effective_user.id != AUTHORIZED_ID:
        return

    text = update.message.text.strip()
    if not text.startswith("/run"):
        return

    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        update.message.reply_text("⚠️ Formato corretto: /run ALL <comando>")
        return

    target, cmd = parts[1], parts[2]
    if target != "ALL" and target != HOSTNAME:
        return  # comando destinato ad altri nodi

    LAST_CMD = cmd
    if process is None or process.poll() is not None:
        process = subprocess.Popen(
            LAST_CMD,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )
        update.message.reply_text(f"[{HOSTNAME}] ▶️ AVVIATO\nComando: {LAST_CMD}")
    else:
        update.message.reply_text(f"[{HOSTNAME}] ⚠️ Già in esecuzione")

# ----- /stop -----
def stop_command(update, context):
    global process
    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process = None
        update.message.reply_text(f"[{HOSTNAME}] ⛔ FERMATO")
    else:
        update.message.reply_text(f"[{HOSTNAME}] ℹ️ Nessun processo attivo")

# ----- /status -----
def status_command(update, context):
    global process, LAST_CMD
    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        update.message.reply_text(f"[{HOSTNAME}] 🟢 ATTIVO\nComando: {LAST_CMD}")
    else:
        update.message.reply_text(f"[{HOSTNAME}] 🔴 FERMO")

# ----- Main -----
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("run", run_command))
    dp.add_handler(CommandHandler("stop", stop_command))
    dp.add_handler(CommandHandler("status", status_command))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
