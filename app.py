import os
import sys
import time
import threading
import logging
from collections import deque
from flask import Flask, jsonify, Response

# Buffer circular en memoria para capturar los últimos 300 logs
log_buffer = deque(maxlen=300)

class BufferHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            log_buffer.append(msg)
        except Exception:
            pass

# Configurar logging global
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
buffer_handler = BufferHandler()
buffer_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(buffer_handler)

# Loggers principales
for logger_name in ["render_service", "bot_telegram", "gemini_parser", "sheets_client", "telegram", "httpx"]:
    l = logging.getLogger(logger_name)
    l.setLevel(logging.INFO)
    l.addHandler(buffer_handler)

app = Flask(__name__)
logger = logging.getLogger("render_service")

# Estado global del bot
bot_status = {
    "running": False,
    "started_at": None,
    "restart_count": 0,
    "last_error": None
}

@app.route("/", methods=["GET", "HEAD"])
@app.route("/ping", methods=["GET", "HEAD"])
@app.route("/health", methods=["GET", "HEAD"])
def ping():
    """
    Endpoint ultra-ligero para cron-job.org y health checks.
    Devuelve estrictamente 2 bytes 'OK' en texto plano para evitar
    el error de 'Response data too big' de cron-job.org.
    """
    return Response("OK", status=200, mimetype="text/plain", headers={"Content-Length": "2"})

@app.route("/status")
def status_endpoint():
    """Diagnóstico detallado en JSON con verificación de variables y estado del bot"""
    tg = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip("\"'")
    gem = os.getenv("GEMINI_API_KEY", "").strip().strip("\"'")
    sh = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", "").strip().strip("\"'")

    return jsonify({
        "status": "online",
        "service": "Asistente de Siniestros Telegram Bot",
        "bot_active": bot_status["running"],
        "bot_restarts": bot_status["restart_count"],
        "last_error": bot_status["last_error"],
        "env_check": {
            "TELEGRAM_BOT_TOKEN": f"Configurado ({tg[:6]}...)" if tg else "FALTANTE",
            "GEMINI_API_KEY": f"Configurado ({gem[:6]}...)" if gem else "FALTANTE",
            "GOOGLE_SHEETS_WEBHOOK_URL": f"Configurado ({sh[:25]}...)" if sh else "FALTANTE"
        }
    }), 200

@app.route("/logs")
def logs():
    """Endpoint para ver los logs en vivo desde el navegador"""
    return Response("\n".join(log_buffer), mimetype="text/plain; charset=utf-8")

def run_flask(port):
    """Ejecuta Flask en un hilo secundario para health checks y logs"""
    logger.info(f"Levantando servidor web en puerto {port}...")
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def run_telegram_loop():
    """Ejecuta el bot de Telegram con reinicio automático si ocurre alguna excepción"""
    global bot_status
    import bot_telegram

    while True:
        try:
            bot_status["running"] = True
            bot_status["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info("Iniciando polling de Telegram...")
            bot_telegram.main()
            logger.warning("main() de bot_telegram finalizó normalmente. Reiniciando en 5s...")
        except Exception as e:
            bot_status["running"] = False
            bot_status["restart_count"] += 1
            bot_status["last_error"] = str(e)
            logger.exception(f"Error fatal en bot_telegram: {e}. Reiniciando en 5s...")
        finally:
            bot_status["running"] = False
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    # Iniciar servidor web de salud y logs en el hilo secundario
    web_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
    web_thread.start()

    # Iniciar el bot de Telegram en el HILO PRINCIPAL con loop de reinicio
    logger.info("Iniciando bucle del bot de Telegram en el hilo principal...")
    run_telegram_loop()
