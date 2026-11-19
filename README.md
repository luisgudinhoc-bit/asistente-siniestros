# 🚗 Asistente Automatizado de Siniestros y Control de Flota

Agente inteligente para ajustadores de seguros que registra automáticamente siniestros, fotografías de odómetro (kilometraje) y cargas de combustible directo en tu Google Sheet vía **Telegram** o **WhatsApp**.

---

## 📋 ¿Qué hace este Asistente?

1. **Registro de Siniestros (Texto o Audio):**
   - Escribe o reenvía el mensaje de cabina: `"Inbursa 7057081 Tulancingo Ram casetas 195"`
   - O manda una nota de voz hablando normal.
   - La IA extrae: Aseguradora, No. Reporte, Ubicación, Tipo de Vehículo, Honorarios de atención ($170 / $200), Casetas, Kilometraje y Status `PENDIENTE`.
   - Se inserta directamente en la siguiente fila disponible de tu hoja de cálculo.

2. **Lectura de Odómetro por Foto (Visión Artificial):**
   - Tomas una foto al tablero de tu vehículo.
   - La IA localiza el odómetro digital/analógico y extrae los kilómetros exactos (ej. `128,898 km`).
   - Calcula automáticamente cuántos kilómetros recorriste desde tu última foto registrada.
   - Lo guarda en la pestaña `ODOMETRO`.

3. **Cargas de Gasolina (Foto de Ticket, Bomba o Texto):**
   - Envías foto del ticket o escribes `"Cargué $800 de magna"`.
   - Extrae litros, monto total, precio por litro y estación.
   - Lo guarda en la pestaña `GASOLINA`.

4. **Resumen de Pagos en Tiempo Real:**
   - Escribe `/resumen` para conocer cuántos servicios tienes pendientes y el total acumulado por cobrar al despacho.

---

## 🚀 Guía de Instalación Rápida (5 Minutos)

### Paso 1: Configurar el Webhook en tu Google Sheet
1. Abre tu hoja de Google Sheets.
2. En el menú superior haz clic en: **Extensiones** > **Apps Script**.
3. Borra cualquier código que aparezca y pega el contenido completo del archivo `google_apps_script.js`.
4. Haz clic en el botón azul **Implementar** (arriba a la derecha) > **Nueva implementación**.
5. Selecciona el tipo de engranaje ⚙️: **Aplicación web**.
   - **Ejecutar como:** *Yo (tu cuenta)*
   - **Quién tiene acceso:** *Cualquier usuario*
6. Haz clic en **Implementar**, autoriza los permisos y **copia la URL de la aplicación web**.

---

### Paso 2: Crear tu Bot de Telegram (Recomendado)
> Telegram es la opción más recomendada porque es **100% gratuita, instantánea, no requiere servidores costosos y nunca banea tu número de teléfono**.

1. Abre Telegram y busca al usuario `@BotFather`.
2. Escribe el comando `/newbot`.
3. Sigue las instrucciones para darle un nombre y usuario a tu bot (ejemplo: `MiAjusteBot`).
4. `@BotFather` te entregará un **Token HTTP API** (ejemplo: `789123456:AAFd4...`). Cópialo.

*(Si prefieres WhatsApp, revisa la sección al final).*

---

### Paso 3: Obtener tu API Key de Gemini
1. Entra a [Google AI Studio](https://aistudio.google.com/).
2. Inicia sesión y genera una **API Key** gratuita.
3. Cópiala.

---

### Paso 4: Configurar y Ejecutar
1. En esta carpeta, crea un archivo llamado `.env` copiando de `.env.example`:
```env
GEMINI_API_KEY=tu_api_key_de_gemini
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/TU_SCRIPT_ID/exec
TELEGRAM_BOT_TOKEN=tu_token_de_botfather
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Inicia el bot de Telegram:
```bash
python bot_telegram.py
```

4. ¡Listo! Abre tu bot en Telegram, presiona `/start` y manda tu primer reporte o foto.

---

## 📱 ¿Y si quiero usar WhatsApp?

Para usar WhatsApp existen dos opciones:
1. **Meta WhatsApp Cloud API (Oficial):**
   - Configura una App en [developers.facebook.com](https://developers.facebook.com).
   - Añade el producto de WhatsApp y obtén tu Phone Number ID y Token de acceso.
   - Ejecuta `python bot_whatsapp.py` y apunta tu webhook a `https://tu-dominio/webhook`.
2. **Evolution API / Baileys (No oficial, WhatsApp Web):**
   - Si no quieres lidiar con Meta Cloud API, puedes levantar un contenedor de Evolution API y vincular tu WhatsApp escaneando un código QR.
