from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
import os
import signal
import socket

# ================= CONFIG =================
TOKEN = "8131285292:AAFkhGHNDzEJ4dxsnkq77AfeHmju5xDLyyk"  # token del bot creato da BotFather
AUTHORIZED_ID = 5699538596                  # tuo chat_id numerico
# =========================================

process = None
LAST_CMD = None
HOSTNAME = socket.gethostname()

# ----- Funzione per creare la tastiera inline -----
def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ START", callback_data="start")],
        [InlineKeyboardButton("⛔ STOP", callback_data="stop")],
        [InlineKeyboardButton("📊 STATUS", callback_data="status")]
    ])

# ----- Handler /start -----
def start(update, context):
    if update.effective_user.id != AUTHORIZED_ID:
        return

    update.message.reply_text(
        f"🤖 Bot attivo su: {HOSTNAME}\nScrivi il comando hping3 da eseguire e poi premi un pulsante:",
        reply_markup=get_keyboard()
    )

# ----- Handler pulsanti -----
def buttons(update, context):
    global process, LAST_CMD
    query = update.callback_query
    query.answer()

    if query.from_user.id != AUTHORIZED_ID:
        return

    if query.data == "start":
        if LAST_CMD is None:
            query.message.reply_text("⚠️ Nessun comando hping3 impostato", reply_markup=get_keyboard())
            return

        if process is None or process.poll() is not None:
            try:
                process = subprocess.Popen(
                    LAST_CMD,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )
                query.message.reply_text(f"▶️ AVVIATO su {HOSTNAME}\nComando: {LAST_CMD}", reply_markup=get_keyboard())
            except Exception as e:
                query.message.reply_text(f"❌ Errore avvio comando:\n{e}", reply_markup=get_keyboard())
        else:
            query.message.reply_text(f"⚠️ Già in esecuzione su {HOSTNAME}", reply_markup=get_keyboard())

    elif query.data == "stop":
        if process and process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process = None
            query.message.reply_text(f"⛔ FERMATO su {HOSTNAME}", reply_markup=get_keyboard())
        else:
            query.message.reply_text(f"ℹ️ Nessun processo attivo su {HOSTNAME}", reply_markup=get_keyboard())

    elif query.data == "status":
        if process and process.poll() is None:
            query.message.reply_text(f"🟢 ATTIVO su {HOSTNAME}\nComando: {LAST_CMD}", reply_markup=get_keyboard())
        else:
            query.message.reply_text(f"🔴 FERMO su {HOSTNAME}", reply_markup=get_keyboard())

# ----- Handler per ricevere comandi hping3 -----
def receive_cmd(update, context):
    global LAST_CMD
    if update.effective_user.id != AUTHORIZED_ID:
        return

    text = update.message.text.strip()
    if text.startswith("hping3"):
        # usa percorso completo di hping3
        LAST_CMD = text.replace("hping3", "/usr/sbin/hping3", 1)
        update.message.reply_text(
            "✅ Comando salvato. Premi un pulsante per eseguirlo:",
            reply_markup=get_keyboard()
        )
    else:
        update.message.reply_text(
            "⚠️ Solo comandi hping3 sono permessi.",
            reply_markup=get_keyboard()
        )

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
