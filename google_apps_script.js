/**
 * ====================================================================================================
 * ASISTENTE DE SINIESTROS Y CONTROL DE COMBUSTIBLE - BOT 100% EN LA NUBE DE GOOGLE (24/7 SIEMPRE ACTIVO)
 * ====================================================================================================
 * Spreadsheet ID: 1PbhYjyw1rCWvP7iaDXcwhKjMHvwuGszxlq0wseA1W0o
 *
 * Este script convierte tu Google Sheet en el servidor del bot de Telegram.
 * Funciona las 24 horas del día, los 365 días del año sin necesidad de tener tu PC encendida.
 *
 * Características:
 * 1. Recibe mensajes, fotos y notas de voz directamente desde Telegram vía Webhook.
 * 2. Agrupa álbumes de fotos (Media Groups, ej. bomba de gasolina + odómetro) en un solo análisis.
 * 3. Consulta la IA de Gemini con visión artificial directamente desde la nube de Google.
 * 4. Pestaña 'Registro': Escribe ÚNICAMENTE columnas A a E (Fórmulas F:J intactas).
 * 5. Pestaña 'Control Combustible': Escribe ÚNICAMENTE columnas manuales (Fórmulas D, I, J intactas).
 * 6. Lee los cálculos automáticos de la hoja y te responde la confirmación a tu Telegram.
 */

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CONFIGURACIÓN DE CLAVES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const TELEGRAM_BOT_TOKEN = "TU_TELEGRAM_BOT_TOKEN";
const GEMINI_API_KEY = "TU_GEMINI_API_KEY";

const UBICACIONES_VALIDAS = [
  'LOCAL', 'TULANCINGO', 'APAN', 'CD SAHAGUN', 'ARCO NORTE (CD. SAHAGÚN)',
  'ARCO NORTE (TULANCINGO)', 'ARCO NORTE (CALPULALPAN)', 'ARCO NORTE (SANCTORUM)',
  'ARCO NORTE (TULA / ATITALAQUIA)', 'ARCO NORTE (TULA I)', 'ARCO NORTE (TULA II)',
  'ARCO NORTE (AJOLOAPAN)', 'ARCO NORTE (APAXCO)', 'ARCO NORTE (SAN MARTÍN TEXMELUCAN)',
  'ARCO NORTE (TEXMELUCAN)', 'ARCO NORTE (ATLACOMULCO)', 'ACTOPAN', 'ATITALAQUIA',
  'CASETA PACHUCA', 'CASETA SAN CRISTÓBAL', 'HUASCA', 'SAN AGUSTIN TLAX',
  'TEPEAPULCO', 'TIZAYUCA', 'TULA', 'VILLAS DE TEZONTEPEC', 'SINGUILUCAN',
  'REAL DEL MONTE', 'SANTIAGO DE ANAYA'
];

/**
 * Punto de entrada principal cuando Telegram envía un evento (Webhook)
 */
function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput("OK");
    }

    const payload = JSON.parse(e.postData.contents);

    // CASO 1: Llamada estructurada desde sheets_client (Python)
    if (payload.action) {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      let res = {};
      if (payload.action === "registrar_siniestro") {
        res = agregarSiniestro(ss, payload.data);
      } else if (payload.action === "registrar_combustible") {
        res = agregarCombustible(ss, payload.data);
      } else if (payload.action === "obtener_resumen") {
        res = obtenerResumen(ss);
      }
      return ContentService.createTextOutput(JSON.stringify({ status: "success", data: res }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // CASO 2: Llamada directa desde Telegram Webhook
    const message = payload.message || payload.edited_message;
    if (message) {
      const chatId = message.chat.id;
      if (message.text) procesarTexto(chatId, message.text);
      else if (message.photo && message.photo.length > 0) procesarFoto(chatId, message);
      else if (message.voice || message.audio) procesarAudio(chatId, message);
      return ContentService.createTextOutput("OK");
    }

    return ContentService.createTextOutput("OK");
  } catch (error) {
    Logger.log("Error en doPost: " + error.toString());
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "online",
    message: "Servidor del Bot de Telegram en Google Apps Script activo 24/7"
  })).setMimeType(ContentService.MimeType.JSON);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MANEJO DE FOTOS Y ÁLBUMES (MEDIA GROUPS)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function procesarFoto(chatId, message) {
  const fileId = message.photo[message.photo.length - 1].file_id;
  const caption = message.caption || "";
  const mediaGroupId = message.media_group_id;

  if (mediaGroupId) {
    // Manejo de álbum con CacheService
    const cache = CacheService.getScriptCache();
    const key = "mg_" + mediaGroupId;
    const lock = LockService.getScriptLock();
    lock.waitLock(5000);

    let list = [];
    const cached = cache.get(key);
    if (cached) {
      list = JSON.parse(cached);
    }
    list.push({ fileId: fileId, caption: caption });
    cache.put(key, JSON.stringify(list), 60);
    lock.releaseLock();

    // Esperar 2 segundos para permitir que llegue la segunda foto del álbum
    Utilities.sleep(2000);

    // Verificar si este hilo es el encargado de procesar el lote completo
    const procKey = "proc_" + mediaGroupId;
    if (!cache.get(procKey)) {
      cache.put(procKey, "true", 60);
      const finalList = JSON.parse(cache.get(key) || "[]");
      const fileIds = finalList.map(item => item.fileId);
      const consolidatedCaption = finalList.map(item => item.caption).filter(Boolean).join(" ");
      
      enviarMensajeTelegram(chatId, `🔍 Analizando ${fileIds.length} fotos agrupadas con IA...`);
      ejecutarAnalisisVision(chatId, fileIds, consolidatedCaption);
    }
  } else {
    // Foto individual
    enviarMensajeTelegram(chatId, "🔍 Analizando imagen con IA...");
    ejecutarAnalisisVision(chatId, [fileId], caption);
  }
}

function ejecutarAnalisisVision(chatId, fileIds, caption) {
  try {
    // Descargar imágenes de Telegram y convertirlas a Base64
    const imageParts = [];
    for (let i = 0; i < fileIds.length; i++) {
      const b64 = descargarFotoTelegramBase64(fileIds[i]);
      if (b64) {
        imageParts.push({
          inline_data: {
            mime_type: "image/jpeg",
            data: b64
          }
        });
      }
    }

    if (imageParts.length === 0) {
      enviarMensajeTelegram(chatId, "⚠️ No pude descargar la imagen de Telegram.");
      return;
    }

    const hoyDDMMAAAA = formatearFechaDDMMAAAA();
    const hoyYYYYMMDD = formatearFechaYYYYMMDD();

    const promptText = `
    Eres un asistente para un ajustador de seguros en México.
    Analiza la(s) imagen(es) provistas (captura de WhatsApp de despacho, ticket de gasolina, bomba o tablero con odómetro).
    Fecha actual de referencia:
    - Para Siniestro (DD/MM/YYYY): "${hoyDDMMAAAA}"
    - Para Combustible (YYYY-MM-DD): "${hoyYYYYMMDD}"

    Lista oficial de ubicaciones del tabulador:
    ${JSON.stringify(UBICACIONES_VALIDAS)}

    Clasifica en UNO de los dos tipos y responde ÚNICAMENTE en JSON estricto:

    OPCIÓN 1: SINIESTRO (captura de chat/cabina de despacho)
    {
      "tipo": "SINIESTRO",
      "fecha": "DD/MM/YYYY",
      "aseguradora": "INBURSA" si folio inicia con 705 o 305; "SPT" si inicia con 67; "CRABI" si inicia con 2026; sino la aseguradora en mayúsculas,
      "reporte": "número de reporte o folio",
      "ubicacion": "UBICACION EXACTA DEL TABULADOR EN MAYUSCULAS (ej. LOCAL, TULANCINGO, APAN, ARCO NORTE (TULANCINGO), etc.)",
      "vehiculo": "VEHICULO EN MAYUSCULAS (ej. BMW NEGRO, VERSA, URVAN, etc.)"
    }

    OPCIÓN 2: COMBUSTIBLE (bomba de gasolina, ticket y/o tablero con odómetro. Si vienen varias fotos, consolida ambos datos)
    {
      "tipo": "COMBUSTIBLE",
      "fecha": "YYYY-MM-DD",
      "odometro": 88688 (entero en km, o null si ninguna foto muestra el odómetro),
      "litros": 29.244 (float, o 0.0 si solo fue odómetro),
      "precio_litro": 22.99 (float, o 0.0 si solo fue odómetro),
      "total_pagado": 672.32 (float, o 0.0 si solo fue odómetro),
      "tipo_evento": "Carga Parcial" | "Carga Tanque Lleno" | "Recorrido Diario" (Recorrido Diario si solo fue odómetro)
    }
    `;

    const parts = [...imageParts];
    if (caption) {
      parts.push({ text: "Pie de foto del usuario: " + caption });
    }
    parts.push({ text: promptText });

    const resultado = llamarGeminiAPI(parts);
    procesarResultadoEnHojas(chatId, resultado);

  } catch (error) {
    Logger.log("Error en analisis de vision: " + error.toString());
    enviarMensajeTelegram(chatId, "❌ Error al procesar imagen: " + error.toString());
  }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MANEJO DE TEXTO Y AUDIOS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function procesarTexto(chatId, texto) {
  const tLower = texto.trim().toLowerCase();

  if (tLower === "/start") {
    enviarMensajeTelegram(chatId,
      "🚗 *¡Hola! Soy tu Asistente de Siniestros y Control de Flota.*\n\n" +
      "☁️ *Servidor 100% en la Nube de Google (24/7 Activo).*\n" +
      "Nunca se apaga aunque tu PC esté apagada o no tengas batería.\n\n" +
      "📸 *Manda fotos individuales o en álbum:* \n" +
      "• Capturas de asignación de siniestros.\n" +
      "• Fotos de bomba dispensadora y odómetro (¡incluso juntas en un álbum!).\n\n" +
      "📊 *Comandos:*\n" +
      "• /resumen - Ver siniestros y montos pendientes por cobrar.\n" +
      "• /ayuda - Guía rápida."
    );
    return;
  }

  if (tLower === "/ayuda") {
    enviarMensajeTelegram(chatId,
      "💡 *¿Cómo registrar?*\n\n" +
      "1️⃣ *Fotos:* Manda capturas de cabina o fotos de gasolina/odómetro (solas o juntas en álbum).\n" +
      "2️⃣ *Texto:* Puedes escribir libremente: _\"Inbursa 7057081 tulancingo ram\"_ o _\"Cargué $800 magna 35L odómetro 128950\"_.\n" +
      "3️⃣ *Audio:* Mantén presionado el micrófono y manda una nota de voz."
    );
    return;
  }

  if (tLower === "/resumen") {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const resumen = obtenerResumen(ss);
    enviarMensajeTelegram(chatId,
      "📊 *RESUMEN DE COBROS PENDIENTES*\n" +
      "━━━━━━━━━━━━━━━━━━━━\n" +
      `⏳ *Pendientes de pago:* ${resumen.pendientes_conteo} siniestros\n` +
      `💰 *Monto por cobrar:* $${resumen.pendientes_monto.toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN\n\n` +
      `✅ *Siniestros liquidados:* ${resumen.pagadas_conteo}\n` +
      `💵 *Monto cobrado:* $${resumen.pagadas_monto.toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN\n` +
      "━━━━━━━━━━━━━━━━━━━━\n" +
      `📁 *Total registrados:* ${resumen.total_siniestros}`
    );
    return;
  }

  // Parsear texto con Gemini
  enviarMensajeTelegram(chatId, "🧠 Analizando mensaje...");
  const promptText = `
  Analiza este mensaje de un ajustador de seguros:
  "${texto}"
  Fecha actual: "${formatearFechaDDMMAAAA()}"
  Ubicaciones: ${JSON.stringify(UBICACIONES_VALIDAS)}

  Clasifica en SINIESTRO o COMBUSTIBLE y responde en JSON estricto:
  Si es SINIESTRO:
  {"tipo": "SINIESTRO", "fecha": "DD/MM/YYYY", "aseguradora": "...", "reporte": "...", "ubicacion": "...", "vehiculo": "..."}
  Si es COMBUSTIBLE:
  {"tipo": "COMBUSTIBLE", "fecha": "YYYY-MM-DD", "odometro": 128000 o null, "litros": 0.0, "precio_litro": 0.0, "total_pagado": 0.0, "tipo_evento": "Carga Parcial"|"Carga Tanque Lleno"|"Recorrido Diario"}
  `;
  try {
    const res = llamarGeminiAPI([{ text: promptText }]);
    procesarResultadoEnHojas(chatId, res);
  } catch (e) {
    enviarMensajeTelegram(chatId, "❌ Error procesando texto: " + e.toString());
  }
}

function procesarAudio(chatId, message) {
  enviarMensajeTelegram(chatId, "🎧 Escuchando nota de voz...");
  try {
    const fileId = (message.voice || message.audio).file_id;
    const b64 = descargarFotoTelegramBase64(fileId);
    const promptText = `
    Escucha esta nota de voz de un ajustador de seguros.
    Fecha actual: "${formatearFechaDDMMAAAA()}"
    Ubicaciones: ${JSON.stringify(UBICACIONES_VALIDAS)}

    Clasifica en SINIESTRO o COMBUSTIBLE y responde en JSON estricto:
    Si es SINIESTRO:
    {"tipo": "SINIESTRO", "fecha": "DD/MM/YYYY", "aseguradora": "...", "reporte": "...", "ubicacion": "...", "vehiculo": "..."}
    Si es COMBUSTIBLE:
    {"tipo": "COMBUSTIBLE", "fecha": "YYYY-MM-DD", "odometro": 128000 o null, "litros": 0.0, "precio_litro": 0.0, "total_pagado": 0.0, "tipo_evento": "Carga Parcial"|"Carga Tanque Lleno"|"Recorrido Diario"}
    `;
    const parts = [
      { inline_data: { mime_type: "audio/ogg", data: b64 } },
      { text: promptText }
    ];
    const res = llamarGeminiAPI(parts);
    procesarResultadoEnHojas(chatId, res);
  } catch (e) {
    enviarMensajeTelegram(chatId, "❌ Error procesando audio: " + e.toString());
  }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// INSERCIÓN EN SHEETS Y RESPUESTA CON FÓRMULAS CALCULADAS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function procesarResultadoEnHojas(chatId, data) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  if (data.tipo === "SINIESTRO") {
    const r = agregarSiniestro(ss, data);
    const msg = 
      "📋 *¡Siniestro Registrado con Éxito!*\n" +
      "━━━━━━━━━━━━━━━━━━━━\n" +
      `📑 *Pestaña:* \`Registro\` (Fila ${r.fila})\n` +
      `📅 *Fecha:* ${r.fecha}\n` +
      `🏢 *Aseguradora:* ${r.aseguradora}\n` +
      `🔢 *Reporte:* \`${r.reporte}\`\n` +
      `📍 *Ubicación:* ${r.ubicacion}\n` +
      `🚗 *Vehículo:* ${r.vehiculo}\n` +
      "────────────────────\n" +
      "📊 *Cálculos automáticos de tu Hoja:*\n" +
      `💵 *Atención:* ${r.atencion}\n` +
      `🛣️ *Casetas:* ${r.casetas}\n` +
      `📍 *Kilometraje:* ${r.kilometraje}\n` +
      `💳 *TOTAL:* ${r.total} MXN\n` +
      `📌 *Status:* \`${r.status}\`\n` +
      "━━━━━━━━━━━━━━━━━━━━\n" +
      "✅ _Guardado sin sobreescribir fórmulas._";
    enviarMensajeTelegram(chatId, msg);

  } else if (data.tipo === "COMBUSTIBLE") {
    const r = agregarCombustible(ss, data);
    const odoStr = (typeof r.odometro === 'number') ? r.odometro.toLocaleString() + " km" : r.odometro + " km";
    const kmRecStr = (typeof r.km_recorridos === 'number') ? r.km_recorridos.toLocaleString() + " km" : r.km_recorridos + " km";
    const rendStr = (typeof r.rendimiento === 'number') ? r.rendimiento.toFixed(2) + " km/L" : r.rendimiento;

    const msg =
      "⛽ *¡Registro de Combustible Exitoso!*\n" +
      "━━━━━━━━━━━━━━━━━━━━\n" +
      `📑 *Pestaña:* \`Control Combustible\` (Fila ${r.fila})\n` +
      `📅 *Fecha:* ${r.fecha}\n` +
      `🚗 *Odómetro:* ${odoStr}\n` +
      `🔄 *Evento:* \`${r.tipo_evento}\`\n` +
      "────────────────────\n" +
      "⛽ *Datos de Carga ingresados:*\n" +
      `• *Litros:* ${r.litros} L\n` +
      `• *Precio/L:* ${r.precio_litro}\n` +
      `• *Total Pagado:* ${r.total_pagado} MXN\n` +
      "────────────────────\n" +
      "📊 *Cálculos automáticos de tu Hoja:*\n" +
      `📈 *Km Recorridos:* ${kmRecStr}\n` +
      `⚡ *Rendimiento:* ${rendStr}\n` +
      `💲 *Costo por Km:* ${r.costo_km}\n` +
      "━━━━━━━━━━━━━━━━━━━━\n" +
      "✅ _Guardado sin sobreescribir fórmulas._";
    enviarMensajeTelegram(chatId, msg);

  } else {
    enviarMensajeTelegram(chatId, "⚠️ No pude determinar si era un siniestro o combustible.");
  }
}

function agregarSiniestro(ss, data) {
  const sheet = ss.getSheetByName("Registro") || ss.getSheets()[0];
  const maxRows = Math.max(sheet.getLastRow(), 200);
  const dataBC = sheet.getRange(2, 2, maxRows - 1, 2).getValues();

  let targetRow = 2;
  for (let i = 0; i < dataBC.length; i++) {
    const b = (dataBC[i][0] || "").toString().trim();
    const c = (dataBC[i][1] || "").toString().trim();
    if (b === "" && c === "") {
      targetRow = i + 2;
      break;
    }
  }

  const fecha = data.fecha || formatearFechaDDMMAAAA();
  const reporte = (data.reporte || "S/N").toString().trim();
  let aseguradora = (data.aseguradora || "").toString().trim().toUpperCase();

  // Validación estricta con la regla de validación de datos de la Columna B
  const aseguradorasValidas = ["INBURSA", "MAPFRE", "SPT", "CRABI", "PRIMERO", "MAPS"];
  if (aseguradorasValidas.indexOf(aseguradora) === -1) {
    if (reporte.startsWith("705") || reporte.startsWith("305")) aseguradora = "INBURSA";
    else if (reporte.startsWith("67")) aseguradora = "SPT";
    else if (reporte.startsWith("2026")) aseguradora = "CRABI";
    else aseguradora = "SPT";
  }

  const ubicacion = (data.ubicacion || "LOCAL").toUpperCase();
  const vehiculo = (data.vehiculo || "S/D").toUpperCase();

  // Escribir ÚNICAMENTE en las columnas A a E (1 a 5)
  sheet.getRange(targetRow, 1, 1, 5).setValues([[
    fecha, aseguradora, reporte, ubicacion, vehiculo
  ]]);

  SpreadsheetApp.flush();

  const rowVals = sheet.getRange(targetRow, 1, 1, 11).getValues()[0];
  return {
    fila: targetRow,
    fecha: rowVals[0],
    aseguradora: rowVals[1],
    reporte: rowVals[2],
    ubicacion: rowVals[3],
    vehiculo: rowVals[4],
    atencion: formatearMoneda(rowVals[5]),
    casetas: formatearMoneda(rowVals[6]),
    otros: formatearMoneda(rowVals[7]),
    kilometraje: formatearMoneda(rowVals[8]),
    total: formatearMoneda(rowVals[9]),
    status: rowVals[10] || "PENDIENTE"
  };
}

function agregarCombustible(ss, data) {
  const sheet = ss.getSheetByName("Control Combustible");
  if (!sheet) throw new Error("No se encontró la pestaña 'Control Combustible'");

  const maxRows = Math.max(sheet.getLastRow(), 200);
  const numRows = maxRows - 8;
  const dataBC = sheet.getRange(9, 2, numRows, 2).getValues();

  let targetRow = 9;
  let ultimoOdometroValido = 0;

  for (let i = 0; i < dataBC.length; i++) {
    const b = (dataBC[i][0] || "").toString().trim();
    const c = (dataBC[i][1] || "").toString().trim();
    if (c !== "" && !isNaN(Number(c.replace(/,/g, '')))) {
      ultimoOdometroValido = Number(c.replace(/,/g, ''));
    }
    if (b === "" || c === "") {
      targetRow = i + 9;
      break;
    }
  }

  const fecha = data.fecha || formatearFechaYYYYMMDD();
  let odoVal = (data.odometro !== null && data.odometro !== undefined && Number(data.odometro) > 0)
    ? Number(data.odometro)
    : (ultimoOdometroValido > 0 ? ultimoOdometroValido : "");

  const tipoEvento = data.tipo_evento || (Number(data.litros) > 0 ? "Carga Parcial" : "Recorrido Diario");
  const litros = Number(data.litros) || 0;
  const precioLitro = Number(data.precio_litro) || 0;
  const totalPagado = Number(data.total_pagado) || 0;
  const notas = data.notas || "Registro vía Telegram";

  // Escribir Col B y Col C
  sheet.getRange(targetRow, 2, 1, 2).setValues([[fecha, odoVal]]);
  // Col D (KM RECORRIDOS) -> Intacta

  // Escribir Col E, F, G, H
  sheet.getRange(targetRow, 5, 1, 4).setValues([[tipoEvento, litros, precioLitro, totalPagado]]);
  // Col I y J -> Intactas

  // Escribir Col K
  sheet.getRange(targetRow, 11, 1, 1).setValue(notas);

  SpreadsheetApp.flush();

  const rowVals = sheet.getRange(targetRow, 2, 1, 10).getValues()[0];
  return {
    fila: targetRow,
    fecha: rowVals[0],
    odometro: rowVals[1],
    km_recorridos: rowVals[2],
    tipo_evento: rowVals[3],
    litros: rowVals[4],
    precio_litro: formatearMoneda(rowVals[5]),
    total_pagado: formatearMoneda(rowVals[6]),
    rendimiento: rowVals[7],
    costo_km: formatearMoneda(rowVals[8]),
    notas: rowVals[9]
  };
}

function obtenerResumen(ss) {
  const sheet = ss.getSheetByName("Registro") || ss.getSheets()[0];
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return { pendientes_conteo: 0, pendientes_monto: 0, pagadas_conteo: 0, pagadas_monto: 0, total_siniestros: 0 };

  const data = sheet.getRange("A2:K" + lastRow).getValues();
  let pendientesCount = 0;
  let pendientesTotal = 0;
  let pagadasCount = 0;
  let pagadasTotal = 0;

  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    const reporte = row[2];
    const total = Number(row[9]) || 0;
    const status = (row[10] || "").toString().trim().toUpperCase();

    if (reporte) {
      if (status === "PENDIENTE") {
        pendientesCount++;
        pendientesTotal += total;
      } else if (status === "PAGADA") {
        pagadasCount++;
        pagadasTotal += total;
      }
    }
  }

  return {
    pendientes_conteo: pendientesCount,
    pendientes_monto: pendientesTotal,
    pagadas_conteo: pagadasCount,
    pagadas_monto: pagadasTotal,
    total_siniestros: pendientesCount + pagadasCount
  };
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// COMUNICACIÓN CON TELEGRAM Y GEMINI
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function descargarFotoTelegramBase64(fileId) {
  try {
    const urlInfo = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getFile?file_id=${fileId}`;
    const respInfo = JSON.parse(UrlFetchApp.fetch(urlInfo).getContentText());
    if (!respInfo.ok) return null;

    const filePath = respInfo.result.file_path;
    const fileUrl = `https://api.telegram.org/file/bot${TELEGRAM_BOT_TOKEN}/${filePath}`;
    const imageBlob = UrlFetchApp.fetch(fileUrl).getBlob();
    return Utilities.base64Encode(imageBlob.getBytes());
  } catch (e) {
    Logger.log("Error descargando foto: " + e.toString());
    return null;
  }
}

function llamarGeminiAPI(parts) {
  const models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.0-flash"];
  let lastErr = null;

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`;
    const payload = {
      contents: [{ parts: parts }],
      generationConfig: {
        temperature: 0.1,
        response_mime_type: "application/json"
      }
    };

    try {
      const options = {
        method: "post",
        contentType: "application/json",
        payload: JSON.stringify(payload),
        muteHttpExceptions: true
      };
      const response = UrlFetchApp.fetch(url, options);
      const code = response.getResponseCode();
      if (code === 200) {
        const json = JSON.parse(response.getContentText());
        const rawText = json.candidates[0].content.parts[0].text;
        const clean = rawText.replace(/^```json\s*|\s*```$/g, "").trim();
        return JSON.parse(clean);
      } else {
        lastErr = new Error(`Gemini ${model} HTTP ${code}: ${response.getContentText()}`);
      }
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("No se pudo obtener respuesta de Gemini");
}

function enviarMensajeTelegram(chatId, texto) {
  try {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
    const payload = {
      chat_id: chatId,
      text: texto,
      parse_mode: "Markdown"
    };
    UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
  } catch (e) {
    Logger.log("Error enviando mensaje Telegram: " + e.toString());
  }
}

function formatearFechaDDMMAAAA() {
  const d = new Date();
  const dia = ("0" + d.getDate()).slice(-2);
  const mes = ("0" + (d.getMonth() + 1)).slice(-2);
  return `${dia}/${mes}/${d.getFullYear()}`;
}

function formatearFechaYYYYMMDD() {
  const d = new Date();
  const dia = ("0" + d.getDate()).slice(-2);
  const mes = ("0" + (d.getMonth() + 1)).slice(-2);
  return `${d.getFullYear()}-${mes}-${dia}`;
}

function formatearMoneda(val) {
  if (typeof val === 'number') {
    return "$" + val.toFixed(2);
  }
  return val !== undefined && val !== null && val !== "" ? val.toString() : "$0.00";
}
