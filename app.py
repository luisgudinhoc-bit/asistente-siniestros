import os
import threading
import asyncio
import logging
from flask import Flask, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("render_service")

@app.route("/")
@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "Asistente de Siniestros Telegram Bot",
        "active": True
    }), 200

def run_telegram_bot():
    """Ejecuta el bot de Telegram en un hilo de fondo dedicado con su propio event loop"""
    logger.info("Iniciando bot de Telegram en segundo plano...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from bot_telegram import main
        main()
    except Exception as e:
        logger.error(f"Error en ejecución del bot de Telegram: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Levantando servidor web en puerto {port}...")

    # Arrancar el bot de Telegram
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # Arrancar el servidor web HTTP para Render
    app.run(host="0.0.0.0", port=port)
