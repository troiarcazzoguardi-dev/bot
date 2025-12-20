from telegram.ext import Updater, CommandHandler
import subprocess
import os
import signal
import socket

TOKEN = "7857611131:AAExGDSgM7YkTZDDF-wA1_jOdCVFEXQ9buc"
AUTHORIZED_ID = 5699538596

process = None
LAST_CMD = None
HOSTNAME = socket.gethostname()

def auth(update):
    return update.effective_user.id == AUTHORIZED_ID

def start(update, context):
    if not auth(update): return
    update.message.reply_text(
        f"🤖 Locust CLI bot su {HOSTNAME}\n"
        "Uso:\n"
        "/run ALL <parametri locust>\n"
        "/stop\n"
        "/status"
    )

def run_command(update, context):
    global process, LAST_CMD
    if not auth(update): return

    text = update.message.text.strip()
    parts = text.split(maxsplit=2)

    if len(parts) < 3:
        update.message.reply_text(
            "⚠️ Uso corretto:\n"
            "/run ALL --host https://example.com -u 100 -r 10 --run-time 5m"
        )
        return

    target, cli_args = parts[1], parts[2]

    if target != "ALL" and target != HOSTNAME:
        return

    if process and process.poll() is None:
        update.message.reply_text(f"[{HOSTNAME}] ⚠️ già in esecuzione")
        return

    LAST_CMD = cli_args

    process = subprocess.Popen(
        LAST_CMD,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )

    update.message.reply_text(
        f"[{HOSTNAME}] ▶️ LOCUST AVVIATO\n"
        f"Cmd: {LAST_CMD}"
    )

def stop_command(update, context):
    global process
    if not auth(update): return

    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process = None
        update.message.reply_text(f"[{HOSTNAME}] ⛔ fermato")
    else:
        update.message.reply_text(f"[{HOSTNAME}] ℹ️ nessun processo")

def status_command(update, context):
    if not auth(update): return

    if process and process.poll() is None:
        update.message.reply_text(
            f"[{HOSTNAME}] 🟢 attivo\nCmd: {LAST_CMD}"
        )
    else:
        update.message.reply_text(f"[{HOSTNAME}] 🔴 fermo")

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
