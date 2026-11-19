import os
import io
import asyncio
import logging
from typing import Dict, List, Any
from dotenv import load_dotenv

# Cargar .env desde el mismo directorio del script
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from gemini_parser import SiniestrosAIParser
from sheets_client import GoogleSheetsClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Instancias principales
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ai_parser = SiniestrosAIParser()
sheets_client = GoogleSheetsClient()

# Buffer asíncrono para Media Groups (Álbumes de fotos)
# media_group_id -> { "photos": [bytes], "caption": str, "message": Update.message, "chat_id": int }
MEDIA_GROUP_BUFFERS: Dict[str, Dict[str, Any]] = {}
MEDIA_GROUP_DELAY = 1.8  # Segundos de espera tras recibir la primera foto del grupo


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🚗 *¡Hola! Soy tu Asistente de Siniestros y Control de Flota.*\n\n"
        "Estoy conectado directamente a tu hoja de Google Sheets.\n"
        "Ahora clasifico automáticamente tus fotos (individuales o en álbumes):\n\n"
        "📸 *1. Capturas de Siniestro (WhatsApp/Cabina):*\n"
        "Manda la captura del chat de asignación. Se registrarán fecha, aseguradora, reporte, ubicación y vehículo en la pestaña `Registro`.\n"
        "_(Tus fórmulas de Atención, Casetas, Km y Total se calcularán solas)._\n\n"
        "⛽ *2. Control de Combustible y Odómetro:*\n"
        "Manda fotos de la bomba dispensadora, tickets de gasolina o tablero con odómetro (¡incluso 2 fotos juntas en un mismo álbum!).\n"
        "Se registrarán en la pestaña `Control Combustible` sin tocar tus fórmulas de Rendimiento ni Costo por Km.\n\n"
        "📊 *Comandos disponibles:*\n"
        "• /resumen - Ver el balance de siniestros pendientes y montos por cobrar.\n"
        "• /ayuda - Ver ejemplos de uso."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def ayuda_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💡 *Guía de uso del Asistente:*\n\n"
        "1️⃣ *Fotos de Siniestros:* Manda una captura del grupo de WhatsApp donde asignan el reporte. La IA detectará folio, aseguradora, ubicación del tabulador y auto.\n\n"
        "2️⃣ *Fotos de Gasolina / Odómetro:* Puedes mandar 1 sola foto o mandar 2 fotos juntas (ej. bomba de gasolina + odómetro del tablero). El bot esperará ~1.8s a que lleguen ambas y las consolidará en un solo registro.\n\n"
        "3️⃣ *Texto o Audio:* También puedes escribir o mandar una nota de voz:\n"
        "   _\"Inbursa 7057081 tulancingo ram\"_\n"
        "   _\"Cargué $800 de magna 34.5 litros odómetro 128950\"_\n\n"
        "4️⃣ *Consultas:* Escribe /resumen para consultar tus siniestros pendientes."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def resumen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Consultando tu hoja de cálculo...")
    resumen = sheets_client.obtener_resumen()
    
    if resumen.get("status") == "success" and "data" in resumen:
        data = resumen["data"]
        texto = (
            "📊 *RESUMEN DE COBROS PENDIENTES*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ *Pendientes de pago:* {data.get('pendientes_conteo', 0)} siniestros\n"
            f"💰 *Monto por cobrar:* ${data.get('pendientes_monto', 0):,.2f} MXN\n\n"
            f"✅ *Siniestros liquidados:* {data.get('pagadas_conteo', 0)}\n"
            f"💵 *Monto cobrado:* ${data.get('pagadas_monto', 0):,.2f} MXN\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 *Total registrados:* {data.get('total_siniestros', 0)}"
        )
    else:
        texto = f"ℹ️ Error consultando la hoja: {resumen.get('message', 'Sin respuesta')}"
    await update.message.reply_text(texto, parse_mode="Markdown")


async def procesar_conjunto_imagenes(photos: List[bytes], caption: str, message):
    """
    Procesa un conjunto de 1 o más imágenes consolidadas, las clasifica con Gemini
    y escribe ÚNICAMENTE los campos de entrada en la pestaña correspondiente de Google Sheets.
    Luego responde con los datos registrados y los valores calculados por las fórmulas.
    """
    total_imgs = len(photos)
    txt_espera = f"🔍 Analizando {total_imgs} imágenes juntas con IA..." if total_imgs > 1 else "🔍 Analizando imagen con IA..."
    msg_espera = await message.reply_text(txt_espera)

    try:
        resultado = ai_parser.clasificar_y_extraer_imagenes(photos, caption)
        tipo = resultado.get("tipo")

        if tipo == "SINIESTRO":
            # Pestaña 'Registro' (solo Cols A a E)
            res = sheets_client.registrar_siniestro(resultado)
            if res.get("status") == "success":
                data = res.get("data", {})
                fila = data.get("fila", "")
                
                respuesta = (
                    "📋 *¡Siniestro Registrado con Éxito!*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📑 *Pestaña:* `Registro` (Fila {fila})\n"
                    f"📅 *Fecha:* {data.get('fecha')}\n"
                    f"🏢 *Aseguradora:* {data.get('aseguradora')}\n"
                    f"🔢 *Reporte:* `{data.get('reporte')}`\n"
                    f"📍 *Ubicación:* {data.get('ubicacion')}\n"
                    f"🚗 *Vehículo:* {data.get('vehiculo')}\n"
                    "────────────────────\n"
                    "📊 *Cálculos automáticos de tu Hoja:*\n"
                    f"💵 *Atención:* {data.get('atencion')}\n"
                    f"🛣️ *Casetas:* {data.get('casetas')}\n"
                    f"📍 *Kilometraje:* {data.get('kilometraje')}\n"
                    f"💲 *Otros:* {data.get('otros')}\n"
                    f"💳 *TOTAL:* {data.get('total')} MXN\n"
                    f"📌 *Status:* `{data.get('status')}`\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ _Columnas A a E guardadas. Fórmulas intactas._"
                )
                await msg_espera.edit_text(respuesta, parse_mode="Markdown")
            else:
                await msg_espera.edit_text(f"❌ Error al registrar en 'Registro': {res.get('message')}")

        elif tipo == "COMBUSTIBLE":
            # Pestaña 'Control Combustible' (solo columnas manuales)
            res = sheets_client.registrar_combustible(resultado)
            if res.get("status") == "success":
                data = res.get("data", {})
                fila = data.get("fila", "")
                
                odo_str = f"{data.get('odometro'):,} km" if isinstance(data.get('odometro'), (int, float)) else f"{data.get('odometro')} km"
                km_rec = f"{data.get('km_recorridos'):,} km" if isinstance(data.get('km_recorridos'), (int, float)) else f"{data.get('km_recorridos')} km"
                rend = f"{data.get('rendimiento'):.2f} km/L" if isinstance(data.get('rendimiento'), (int, float)) else f"{data.get('rendimiento')}"

                respuesta = (
                    "⛽ *¡Registro de Combustible Exitoso!*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📑 *Pestaña:* `Control Combustible` (Fila {fila})\n"
                    f"📅 *Fecha:* {data.get('fecha')}\n"
                    f"🚗 *Odómetro:* {odo_str}\n"
                    f"🔄 *Tipo Evento:* `{data.get('tipo_evento')}`\n"
                    "────────────────────\n"
                    "⛽ *Datos de Carga ingresados:*\n"
                    f"• *Litros:* {data.get('litros')} L\n"
                    f"• *Precio/L:* {data.get('precio_litro')}\n"
                    f"• *Total Pagado:* {data.get('total_pagado')} MXN\n"
                    "────────────────────\n"
                    "📊 *Cálculos automáticos de tu Hoja:*\n"
                    f"📈 *Km Recorridos:* {km_rec}\n"
                    f"⚡ *Rendimiento:* {rend}\n"
                    f"💲 *Costo por Km:* {data.get('costo_km')}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ _Entradas manuales guardadas. Fórmulas intactas._"
                )
                await msg_espera.edit_text(respuesta, parse_mode="Markdown")
            else:
                await msg_espera.edit_text(f"❌ Error al registrar en 'Control Combustible': {res.get('message')}")

        else:
            await msg_espera.edit_text(
                "⚠️ No pude clasificar la imagen con certeza en *SINIESTRO* o *COMBUSTIBLE*.\n"
                "Por favor verifica que la imagen sea nítida."
            )

    except Exception as e:
        logger.error(f"Error procesando imágenes: {e}")
        await msg_espera.edit_text(f"❌ Error al procesar imagen(es): {str(e)}")


async def process_media_group_after_delay(media_group_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Espera a que lleguen todas las fotos del álbum y luego las procesa juntas"""
    await asyncio.sleep(MEDIA_GROUP_DELAY)
    buffer_data = MEDIA_GROUP_BUFFERS.pop(media_group_id, None)
    if not buffer_data:
        return

    photos = buffer_data["photos"]
    caption = buffer_data["caption"]
    message = buffer_data["message"]
    logger.info(f"Procesando álbum media_group_id={media_group_id} con {len(photos)} fotos.")
    await procesar_conjunto_imagenes(photos, caption, message)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador de fotos individuales y álbumes (Media Groups)
    """
    message = update.message
    if not message or not message.photo:
        return

    # Descargar la foto en máxima resolución
    photo_file = await message.photo[-1].get_file()
    photo_bytes = bytes(await photo_file.download_as_bytearray())
    caption = message.caption or ""
    media_group_id = message.media_group_id

    if media_group_id:
        # La foto forma parte de un álbum (media group)
        if media_group_id in MEDIA_GROUP_BUFFERS:
            MEDIA_GROUP_BUFFERS[media_group_id]["photos"].append(photo_bytes)
            if not MEDIA_GROUP_BUFFERS[media_group_id]["caption"] and caption:
                MEDIA_GROUP_BUFFERS[media_group_id]["caption"] = caption
        else:
            MEDIA_GROUP_BUFFERS[media_group_id] = {
                "photos": [photo_bytes],
                "caption": caption,
                "message": message,
                "chat_id": message.chat_id,
            }
            # Disparar temporizador asíncrono para esperar a las demás fotos
            asyncio.create_task(process_media_group_after_delay(media_group_id, context))
    else:
        # Foto individual enviada sola
        await procesar_conjunto_imagenes([photo_bytes], caption, message)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo de mensajes de texto directo"""
    texto_usuario = update.message.text
    msg_procesando = await update.message.reply_text("🧠 Analizando reporte con IA...")

    try:
        resultado = ai_parser.parse_reporte_texto(texto_usuario)
        tipo = resultado.get("tipo")

        if tipo == "COMBUSTIBLE":
            res = sheets_client.registrar_combustible(resultado)
            if res.get("status") == "success":
                data = res.get("data", {})
                fila = data.get("fila", "")
                odo_str = f"{data.get('odometro'):,} km" if isinstance(data.get('odometro'), (int, float)) else f"{data.get('odometro')} km"
                km_rec = f"{data.get('km_recorridos'):,} km" if isinstance(data.get('km_recorridos'), (int, float)) else f"{data.get('km_recorridos')} km"
                rend = f"{data.get('rendimiento'):.2f} km/L" if isinstance(data.get('rendimiento'), (int, float)) else f"{data.get('rendimiento')}"

                respuesta = (
                    "⛽ *¡Registro de Combustible Exitoso!*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📑 *Pestaña:* `Control Combustible` (Fila {fila})\n"
                    f"📅 *Fecha:* {data.get('fecha')}\n"
                    f"🚗 *Odómetro:* {odo_str}\n"
                    f"🔄 *Tipo Evento:* `{data.get('tipo_evento')}`\n"
                    "────────────────────\n"
                    "⛽ *Datos de Carga:*\n"
                    f"• *Litros:* {data.get('litros')} L\n"
                    f"• *Precio/L:* {data.get('precio_litro')}\n"
                    f"• *Total Pagado:* {data.get('total_pagado')} MXN\n"
                    "────────────────────\n"
                    "📊 *Cálculos automáticos de tu Hoja:*\n"
                    f"📈 *Km Recorridos:* {km_rec}\n"
                    f"⚡ *Rendimiento:* {rend}\n"
                    f"💲 *Costo por Km:* {data.get('costo_km')}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ _Entradas manuales guardadas. Fórmulas intactas._"
                )
                await msg_procesando.edit_text(respuesta, parse_mode="Markdown")
            else:
                await msg_procesando.edit_text(f"❌ Error al registrar combustible: {res.get('message')}")

        else:
            res = sheets_client.registrar_siniestro(resultado)
            if res.get("status") == "success":
                data = res.get("data", {})
                fila = data.get("fila", "")
                
                respuesta = (
                    "📋 *¡Siniestro Registrado con Éxito!*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📑 *Pestaña:* `Registro` (Fila {fila})\n"
                    f"📅 *Fecha:* {data.get('fecha')}\n"
                    f"🏢 *Aseguradora:* {data.get('aseguradora')}\n"
                    f"🔢 *Reporte:* `{data.get('reporte')}`\n"
                    f"📍 *Ubicación:* {data.get('ubicacion')}\n"
                    f"🚗 *Vehículo:* {data.get('vehiculo')}\n"
                    "────────────────────\n"
                    "📊 *Cálculos automáticos de tu Hoja:*\n"
                    f"💵 *Atención:* {data.get('atencion')}\n"
                    f"🛣️ *Casetas:* {data.get('casetas')}\n"
                    f"📍 *Kilometraje:* {data.get('kilometraje')}\n"
                    f"💲 *Otros:* {data.get('otros')}\n"
                    f"💳 *TOTAL:* {data.get('total')} MXN\n"
                    f"📌 *Status:* `{data.get('status')}`\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ _Columnas A a E guardadas. Fórmulas intactas._"
                )
                await msg_procesando.edit_text(respuesta, parse_mode="Markdown")
            else:
                await msg_procesando.edit_text(f"❌ Error al registrar siniestro: {res.get('message')}")

    except Exception as e:
        logger.error(f"Error procesando texto: {e}")
        await msg_procesando.edit_text(f"❌ Error al procesar el mensaje: {str(e)}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo de notas de voz"""
    msg_espera = await update.message.reply_text("🎧 Transcribiendo y analizando nota de voz...")

    try:
        voice = update.message.voice or update.message.audio
        voice_file = await voice.get_file()
        audio_bytes = bytes(await voice_file.download_as_bytearray())

        resultado = ai_parser.parse_audio(audio_bytes, mime_type="audio/ogg")
        transcripcion = resultado.get("transcripcion_audio") or resultado.get("transcripcion", "")
        tipo = resultado.get("tipo")

        if tipo == "COMBUSTIBLE":
            res = sheets_client.registrar_combustible(resultado)
            if res.get("status") == "success":
                data = res.get("data", {})
                await msg_espera.edit_text(
                    f"🗣️ *Voz:* _{transcripcion}_\n\n"
                    f"⛽ *Combustible registrado en Fila {data.get('fila')}*\n"
                    f"Litros: {data.get('litros')} L | Total: {data.get('total_pagado')}\n"
                    f"Rendimiento: {data.get('rendimiento')} km/L",
                    parse_mode="Markdown"
                )
        else:
            res = sheets_client.registrar_siniestro(resultado)
            if res.get("status") == "success":
                data = res.get("data", {})
                await msg_espera.edit_text(
                    f"🗣️ *Voz:* _{transcripcion}_\n\n"
                    f"📋 *Siniestro registrado en Fila {data.get('fila')}*\n"
                    f"{data.get('aseguradora')} `{data.get('reporte')}` | {data.get('ubicacion')}\n"
                    f"Total calculado: *{data.get('total')}*",
                    parse_mode="Markdown"
                )

    except Exception as e:
        logger.error(f"Error procesando nota de voz: {e}")
        await msg_espera.edit_text(f"❌ Error procesando audio: {str(e)}")


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Por favor coloca tu TELEGRAM_BOT_TOKEN en el archivo .env")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ayuda", ayuda_command))
    app.add_handler(CommandHandler("resumen", resumen_command))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    print("🤖 Bot Asistente de Siniestros y Combustible iniciado (v2 con Media Groups)...")
    app.run_polling()


if __name__ == "__main__":
    main()
