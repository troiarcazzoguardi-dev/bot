from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
import os
import signal
import socket

# ================= CONFIG =================
TOKEN = "8131285292:AAFkhGHNDzEJ4dxsnkq77AfeHmju5xDLyyk"
AUTHORIZED_ID = 8131285292   # IL TUO chat_id
# =========================================

process = None
LAST_CMD = None
HOSTNAME = socket.gethostname()

# ----- Handler /start -----
def start(update, context):
    if update.effective_user.id != AUTHORIZED_ID:
        return

    keyboard = [
        [InlineKeyboardButton("▶️ START", callback_data="start")],
        [InlineKeyboardButton("⛔ STOP", callback_data="stop")],
        [InlineKeyboardButton("📊 STATUS", callback_data="status")]
    ]

    update.message.reply_text(
        f"🤖 Bot attivo su: {HOSTNAME}\nScrivi il comando hping3 da eseguire e poi premi START.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ----- Handler dei pulsanti -----
def buttons(update, context):
    global process, LAST_CMD
    query = update.callback_query
    query.answer()

    if query.from_user.id != AUTHORIZED_ID:
        return

    if query.data == "start":
        if LAST_CMD is None:
            query.edit_message_text("⚠️ Nessun comando hping3 impostato")
            return
        if process is None or process.poll() is not None:
            process = subprocess.Popen(
                LAST_CMD,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            query.edit_message_text(f"▶️ AVVIATO su {HOSTNAME}\nComando: {LAST_CMD}")
        else:
            query.edit_message_text(f"⚠️ Già in esecuzione su {HOSTNAME}")

    elif query.data == "stop":
        if process and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process = None
            query.edit_message_text(f"⛔ FERMATO su {HOSTNAME}")
        else:
            query.edit_message_text(f"ℹ️ Nessun processo attivo su {HOSTNAME}")

    elif query.data == "status":
        if process and process.poll() is None:
            query.edit_message_text(f"🟢 ATTIVO su {HOSTNAME}\nComando: {LAST_CMD}")
        else:
            query.edit_message_text(f"🔴 FERMO su {HOSTNAME}")

# ----- Handler messaggi testo (comando hping3) -----
def receive_cmd(update, context):
    global LAST_CMD
    if update.effective_user.id != AUTHORIZED_ID:
        return

    text = update.message.text.strip()
    if text.startswith("hping3"):
        LAST_CMD = text
        update.message.reply_text("✅ Comando salvato. Premi ▶️ START per eseguirlo.")
    else:
        update.message.reply_text("⚠️ Solo comandi hping3 sono permessi.")

# ----- Main -----
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, receive_cmd))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
