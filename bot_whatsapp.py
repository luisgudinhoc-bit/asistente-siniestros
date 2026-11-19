import os
import requests
import json
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from gemini_parser import SiniestrosAIParser
from sheets_client import GoogleSheetsClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp_bot")

app = Flask(__name__)

# Configuración Meta WhatsApp Cloud API
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "siniestros_secret_token_123")

ai_parser = SiniestrosAIParser()
sheets_client = GoogleSheetsClient()

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Verificación requerida por Meta Developer Console"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verificado exitosamente.")
            return challenge, 200
        else:
            return "Token de verificación incorrecto", 403
    return "Faltan parámetros", 400

@app.route("/webhook", methods=["POST"])
def receive_message():
    """Recepción de mensajes entrantes de WhatsApp"""
    data = request.get_json()

    if not data or "entry" not in data:
        return "EVENT_RECEIVED", 200

    try:
        entry = data["entry"][0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return "EVENT_RECEIVED", 200

        msg = messages[0]
        from_number = msg.get("from")
        msg_type = msg.get("type")

        if msg_type == "text":
            texto = msg.get("text", {}).get("body", "")
            procesar_texto(from_number, texto)

        elif msg_type == "image":
            image_id = msg.get("image", {}).get("id")
            caption = msg.get("image", {}).get("caption", "")
            procesar_imagen(from_number, image_id, caption)

        elif msg_type == "audio":
            audio_id = msg.get("audio", {}).get("id")
            procesar_audio(from_number, audio_id)

    except Exception as e:
        logger.error(f"Error procesando mensaje de WhatsApp: {e}")

    return "EVENT_RECEIVED", 200

def descargar_media_meta(media_id: str) -> bytes:
    """Descarga un archivo multimedia usando Graph API de Meta"""
    url_info = f"https://graph.facebook.com/v19.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    resp = requests.get(url_info, headers=headers).json()
    media_url = resp.get("url")

    media_data = requests.get(media_url, headers=headers)
    return media_data.content

def enviar_whatsapp(to_number: str, text: str):
    """Envía un mensaje de texto por WhatsApp"""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        logger.warning(f"No hay credenciales de WhatsApp. Mensaje a {to_number}: {text}")
        return

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)

def procesar_texto(from_number: str, texto: str):
    lower = texto.lower()
    if "cargué" in lower or "gasolina" in lower or "litros" in lower:
        datos = ai_parser.parse_gasolina(texto=texto)
        sheets_client.registrar_gasolina(datos)
        resp = (
            f"⛽ *Gasolina Registrada*\n"
            f"Importe: ${datos.get('monto_total', 0):,.2f}\n"
            f"Litros: {datos.get('litros', 0)} L\n"
            f"Guardado en tu Google Sheet."
        )
    elif "resumen" in lower or "saldo" in lower:
        resumen = sheets_client.obtener_resumen()
        data = resumen.get("data", {})
        resp = (
            f"📊 *Resumen de Siniestros*\n"
            f"Pendientes: {data.get('pendientes_conteo', 0)}\n"
            f"Por cobrar: ${data.get('pendientes_monto', 0):,.2f} MXN"
        )
    else:
        datos = ai_parser.parse_reporte_texto(texto)
        sheets_client.registrar_siniestro(datos)
        atencion = datos.get('atencion', 0.0)
        casetas = datos.get('casetas', 0.0)
        total = atencion + casetas + datos.get('kilometraje_monto', 0.0) + datos.get('otros', 0.0)
        resp = (
            f"📋 *Siniestro Registrado*\n"
            f"• Aseguradora: {datos.get('aseguradora', 'S/D')}\n"
            f"• Reporte: {datos.get('reporte', 'S/N')}\n"
            f"• Ubicación: {datos.get('ubicacion', 'LOCAL')}\n"
            f"• Vehículo: {datos.get('vehiculo', 'S/D')}\n"
            f"• Total: ${total:,.2f} MXN\n"
            f"Status: PENDIENTE"
        )
    enviar_whatsapp(from_number, resp)

def procesar_imagen(from_number: str, image_id: str, caption: str):
    image_bytes = descargar_media_meta(image_id)
    if "gasolina" in caption.lower() or "ticket" in caption.lower():
        datos = ai_parser.parse_gasolina(image_bytes=image_bytes, texto=caption)
        sheets_client.registrar_gasolina(datos)
        resp = f"⛽ Ticket registrado: ${datos.get('monto_total', 0):,.2f} MXN ({datos.get('litros', 0)} L)."
    else:
        datos = ai_parser.parse_odometro_foto(image_bytes)
        km = datos.get("kilometraje", 0)
        if km > 0:
            res_odo = sheets_client.registrar_odometro(datos)
            rec = res_odo.get("data", {}).get("km_recorridos", 0)
            rec_str = f" (+{rec:,.0f} km)" if rec > 0 else ""
            resp = f"📸 Odómetro registrado: *{km:,.0f} km*{rec_str}."
        else:
            resp = "⚠️ No pude leer el odómetro con claridad. Intenta con una toma más cercana."
    enviar_whatsapp(from_number, resp)

def procesar_audio(from_number: str, audio_id: str):
    audio_bytes = descargar_media_meta(audio_id)
    resultado = ai_parser.parse_audio(audio_bytes, mime_type="audio/ogg")
    tipo = resultado.get("tipo")
    if tipo == "siniestro":
        sheets_client.registrar_siniestro(resultado)
        resp = f"🗣️ Siniestro registrado por voz: {resultado.get('aseguradora')} {resultado.get('reporte')} - ${resultado.get('atencion')} MXN."
    elif tipo == "gasolina":
        sheets_client.registrar_gasolina(resultado)
        resp = f"🗣️ Gasolina registrada por voz: ${resultado.get('monto_total')} MXN."
    else:
        resp = f"🗣️ Audio recibido: {resultado.get('transcripcion')}"
    enviar_whatsapp(from_number, resp)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Servidor de WhatsApp escuchando en puerto {port}")
    app.run(host="0.0.0.0", port=port)
