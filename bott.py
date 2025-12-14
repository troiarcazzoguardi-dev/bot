import asyncio
import subprocess
import os
import signal
import socket
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= CONFIG =================
TOKEN = "8386952835:AAEJ8hXDq0NRUje_5eChu-jRZhBwz0Vw2CLI"
AUTHORIZED_ID = 5699538596
# =========================================

process = None
LAST_CMD = None
HOSTNAME = socket.gethostname()

# ----- /start -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTHORIZED_ID:
        return
    await update.message.reply_text(
        f"🤖 Bot attivo su: {HOSTNAME}\n"
        "Usa /run ALL <comando> per eseguirlo su tutte le VNC attive.\n"
        "Puoi usare /stop per fermare e /status per verificare lo stato."
    )

# ----- /run -----
async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process, LAST_CMD
    if update.effective_user.id != AUTHORIZED_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Formato corretto: /run ALL <comando>")
        return

    target = context.args[0]
    cmd = " ".join(context.args[1:])

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
        await update.message.reply_text(f"[{HOSTNAME}] ▶️ AVVIATO\nComando: {LAST_CMD}")
    else:
        await update.message.reply_text(f"[{HOSTNAME}] ⚠️ Già in esecuzione")

# ----- /stop -----
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process
    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process = None
        await update.message.reply_text(f"[{HOSTNAME}] ⛔ FERMATO")
    else:
        await update.message.reply_text(f"[{HOSTNAME}] ℹ️ Nessun processo attivo")

# ----- /status -----
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process, LAST_CMD
    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        await update.message.reply_text(f"[{HOSTNAME}] 🟢 ATTIVO\nComando: {LAST_CMD}")
    else:
        await update.message.reply_text(f"[{HOSTNAME}] 🔴 FERMO")

# ----- Main -----
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))

    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()  # mantiene il bot in esecuzione

if __name__ == "__main__":
    asyncio.run(main())
