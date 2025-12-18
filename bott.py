from telegram.ext import Updater, CommandHandler
import subprocess
import os
import signal
import socket
import psutil
import threading
import time

# ================= CONFIG =================
TOKEN = "8593144725:AAHw5UoWAnrANQCZIw1mwsbNkh8c_roFmLU"
AUTHORIZED_ID = 5699538596
# =========================================

process = None
LAST_CMD = None
HOSTNAME = socket.gethostname()

monitor_threads = {}
MONITOR_INTERVAL = 2  # secondi

# ---------- UTILS ----------
def get_cpu_status(top_n=5):
    cpu_total = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()

    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            procs.append(p.info)
        except:
            pass

    # secondo campionamento reale
    for p in procs:
        try:
            psutil.Process(p['pid']).cpu_percent(interval=0.1)
        except:
            pass

    procs = sorted(procs, key=lambda x: x['cpu_percent'], reverse=True)
    top_procs = procs[:top_n]

    msg = (
        f"🖥️ {HOSTNAME}\n"
        f"💻 CPU totale: {cpu_total}%\n"
        f"🧠 RAM usata: {mem.percent}%\n\n"
        f"🔥 Top {top_n} processi:\n"
    )

    for p in top_procs:
        msg += f"{p['name']} (PID {p['pid']}): {p['cpu_percent']}%\n"

    return msg


# ---------- COMMANDS ----------
def start(update, context):
    if update.effective_user.id != AUTHORIZED_ID:
        return
    update.message.reply_text(
        f"🤖 Bot attivo su {HOSTNAME}\n"
        "/run ALL <cmd>\n"
        "/stop\n"
        "/status\n"
        "/monitor\n"
        "/stopmonitor"
    )


def run_command(update, context):
    global process, LAST_CMD
    if update.effective_user.id != AUTHORIZED_ID:
        return

    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 3:
        update.message.reply_text("Uso: /run ALL <comando>")
        return

    target, cmd = parts[1], parts[2]
    if target != "ALL" and target != HOSTNAME:
        return

    LAST_CMD = cmd

    if process is None or process.poll() is not None:
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )
        update.message.reply_text(f"[{HOSTNAME}] ▶️ AVVIATO\n{cmd}")
    else:
        update.message.reply_text(f"[{HOSTNAME}] ⚠️ Già in esecuzione")


def stop_command(update, context):
    global process
    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process = None
        update.message.reply_text(f"[{HOSTNAME}] ⛔ FERMATO")
    else:
        update.message.reply_text("Nessun processo attivo")


def status_command(update, context):
    if update.effective_user.id != AUTHORIZED_ID:
        return

    if process and process.poll() is None:
        update.message.reply_text(f"[{HOSTNAME}] 🟢 ATTIVO\n{LAST_CMD}")
    else:
        update.message.reply_text(f"[{HOSTNAME}] 🔴 FERMO")


# ---------- MONITOR LIVE ----------
def monitor_loop(chat_id, bot, stop_event):
    msg = bot.send_message(chat_id, "📊 Avvio monitor CPU...")
    while not stop_event.is_set():
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text=get_cpu_status()
            )
        except:
            break
        time.sleep(MONITOR_INTERVAL)


def monitor_command(update, context):
    uid = update.effective_user.id
    if uid != AUTHORIZED_ID:
        return

    if uid in monitor_threads:
        update.message.reply_text("⚠️ Monitor già attivo")
        return

    stop_event = threading.Event()
    t = threading.Thread(
        target=monitor_loop,
        args=(update.effective_chat.id, context.bot, stop_event),
        daemon=True
    )
    t.start()
    monitor_threads[uid] = stop_event
    update.message.reply_text("✅ Monitor CPU avviato")


def stopmonitor_command(update, context):
    uid = update.effective_user.id
    if uid != AUTHORIZED_ID:
        return

    if uid in monitor_threads:
        monitor_threads[uid].set()
        del monitor_threads[uid]
        update.message.reply_text("⛔ Monitor fermato")
    else:
        update.message.reply_text("ℹ️ Nessun monitor attivo")


# ---------- MAIN ----------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("run", run_command))
    dp.add_handler(CommandHandler("stop", stop_command))
    dp.add_handler(CommandHandler("status", status_command))
    dp.add_handler(CommandHandler("monitor", monitor_command))
    dp.add_handler(CommandHandler("stopmonitor", stopmonitor_command))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()