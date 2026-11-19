import os
import threading
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

def run_flask(port):
    """Ejecuta Flask en un hilo de fondo secundario para que Render detecte el puerto activo"""
    logger.info(f"Levantando servidor web en puerto {port}...")
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    # Iniciar servidor web de salud en el hilo secundario
    web_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
    web_thread.start()

    # Iniciar el bot de Telegram en el HILO PRINCIPAL (Requerido para señales y polling de Telegram)
    logger.info("Iniciando bot de Telegram en el hilo principal...")
    from bot_telegram import main
    main()
