import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

UBICACIONES_VALIDAS = [
    'LOCAL', 'TULANCINGO', 'APAN', 'CD SAHAGUN', 'ARCO NORTE (CD. SAHAGÚN)',
    'ARCO NORTE (TULANCINGO)', 'ARCO NORTE (CALPULALPAN)', 'ARCO NORTE (SANCTORUM)',
    'ARCO NORTE (TULA / ATITALAQUIA)', 'ARCO NORTE (TULA I)', 'ARCO NORTE (TULA II)',
    'ARCO NORTE (AJOLOAPAN)', 'ARCO NORTE (APAXCO)', 'ARCO NORTE (SAN MARTÍN TEXMELUCAN)',
    'ARCO NORTE (TEXMELUCAN)', 'ARCO NORTE (ATLACOMULCO)', 'ACTOPAN', 'ATITALAQUIA',
    'CASETA PACHUCA', 'CASETA SAN CRISTÓBAL', 'HUASCA', 'SAN AGUSTIN TLAX',
    'TEPEAPULCO', 'TIZAYUCA', 'TULA', 'VILLAS DE TEZONTEPEC', 'SINGUILUCAN',
    'REAL DEL MONTE', 'SANTIAGO DE ANAYA'
]

class SiniestrosAIParser:
    """
    Motor de Inteligencia Artificial Multimodal con Gemini para:
    1. Clasificación estricta de imágenes (individuales o agrupadas en álbumes):
       - SINIESTRO: Capturas de cabina/despacho -> Pestaña 'Registro' (Cols A-E).
       - COMBUSTIBLE: Foto de bomba dispensadora, ticket y/o tablero con odómetro -> Pestaña 'Control Combustible'.
    2. Parseo de mensajes de texto o transcripciones de voz.
    """
    MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"No se pudo inicializar Google GenAI SDK: {e}")

    def _generate(self, contents, response_mime_type: Optional[str] = "application/json") -> str:
        """Llama a Gemini con reintentos y fallback automático entre modelos disponibles"""
        if not self.client:
            raise ValueError("GEMINI_API_KEY no configurada")
            
        from google.genai import types
        last_err = None
        for model in self.MODELS:
            try:
                config_kwargs = {"temperature": 0.1}
                if response_mime_type:
                    config_kwargs["response_mime_type"] = response_mime_type
                config = types.GenerateContentConfig(**config_kwargs)

                resp = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
                if resp and resp.text:
                    return resp.text.strip()
            except Exception as e:
                last_err = e
                logger.warning(f"Fallo temporal con {model}: {e}")
                continue
        raise last_err or RuntimeError("No se obtuvo respuesta de ningún modelo de Gemini")

    def clasificar_y_extraer_imagenes(self, images_bytes: List[bytes], caption: str = "") -> Dict[str, Any]:
        """
        Analiza una o varias imágenes (álbum) y devuelve JSON estricto con tipo: 'SINIESTRO' o 'COMBUSTIBLE'.
        Consolida datos cuando se mandan varias fotos juntas (ej. bomba + odómetro).
        """
        hoy_ddmmaaaa = datetime.now().strftime("%d/%m/%Y")
        hoy_yyyymmdd = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""
        Eres un asistente de inteligencia artificial para un ajustador de seguros automotriz en México.
        Analiza cuidadosamente la(s) imagen(es) provista(s) (que pueden ser 1 o varias imágenes juntas, como capturas de chats de despacho, fotos de bombas de gasolina, odómetro en el tablero, o tickets de combustible).

        Fecha actual de referencia:
        - Para Siniestros (DD/MM/YYYY): "{hoy_ddmmaaaa}"
        - Para Combustible (YYYY-MM-DD): "{hoy_yyyymmdd}"

        Lista oficial de ubicaciones del tabulador (debes hacer coincidir exactamente la ubicación con alguna de estas):
        {json.dumps(UBICACIONES_VALIDAS, ensure_ascii=False)}

        Debes clasificar el envío en UNO de estos dos tipos y devolver ÚNICAMENTE el objeto JSON correspondiente:

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        TIPO 1: "SINIESTRO"
        Aplica si la imagen es una captura de pantalla de WhatsApp / cabina de despacho (ej. grupos de despacho de ajustes asignando un siniestro, reporte, vehículo, etc.).
        Estructura requerida:
        {{
            "tipo": "SINIESTRO",
            "fecha": "DD/MM/YYYY" (ej: "{hoy_ddmmaaaa}", o la fecha indicada en la captura),
            "aseguradora": "INBURSA" si el folio empieza con 705 o 305; "SPT" si empieza con 67; "CRABI" si empieza con 2026; o el nombre explícito si es otra en mayúsculas,
            "reporte": "Número de folio o reporte de siniestro (solo dígitos o clave limpia)",
            "ubicacion": "Ubicación en MAYÚSCULAS coincidiendo exactamente con la lista del tabulador (ej: 'LOCAL', 'TULANCINGO', 'APAN', 'CD SAHAGUN', 'ARCO NORTE (TULANCINGO)', 'ARCO NORTE (SANCTORUM)', etc.). Si es en la ciudad base usa 'LOCAL'.",
            "vehiculo": "Vehículo en MAYÚSCULAS (ej: 'BMW NEGRO', 'URVAN', 'VERSA', 'TSURU', 'RAM', etc.)"
        }}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        TIPO 2: "COMBUSTIBLE"
        Aplica si la(s) imagen(es) muestran una bomba dispensadora de gasolina, ticket de recarga de combustible, y/o el tablero con odómetro del vehículo (pueden venir varias fotos en el mismo grupo, ej. una de la bomba y otra del odómetro, debes consolidar ambos datos en un solo JSON).
        Estructura requerida:
        {{
            "tipo": "COMBUSTIBLE",
            "fecha": "YYYY-MM-DD" (ej: "{hoy_yyyymmdd}"),
            "odometro": 88688 (número entero con la lectura de km del tablero, o null si ninguna foto muestra el odómetro),
            "litros": 29.244 (cantidad de litros float de la bomba/ticket, o 0.0 si solo es foto de odómetro),
            "precio_litro": 22.99 (precio por litro float, o 0.0 si solo es odómetro),
            "total_pagado": 672.32 (importe total pagado float en MXN, o 0.0 si solo es odómetro),
            "tipo_evento": "Carga Parcial" | "Carga Tanque Lleno" | "Recorrido Diario"
                * Usa "Recorrido Diario" si solo se envió foto del odómetro sin carga de combustible.
                * Usa "Carga Tanque Lleno" si el ticket/pantalla indica lleno o venta completa.
                * Usa "Carga Parcial" si fue recarga normal de combustible.
        }}

        Responde ÚNICAMENTE con el objeto JSON estricto. Sin rodeos ni bloques de texto adicionales.
        """

        from google.genai import types
        contents = []
        for img in images_bytes:
            contents.append(types.Part.from_bytes(data=img, mime_type="image/jpeg"))

        if caption:
            contents.append(f"Texto / pie de foto del usuario: {caption}")
        contents.append(prompt)

        raw = self._generate(contents, response_mime_type="application/json")
        clean_json = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
        return json.loads(clean_json)

    def parse_reporte_texto(self, texto: str) -> Dict[str, Any]:
        """
        Extrae datos estructurados de un reporte enviado en texto o nota de voz.
        Clasifica si es SINIESTRO o COMBUSTIBLE.
        """
        lower = texto.lower()
        if "cargué" in lower or "gasolina" in lower or "litros" in lower or "odómetro" in lower or "odometro" in lower:
            return self._parse_combustible_texto(texto)
            
        hoy_ddmmaaaa = datetime.now().strftime("%d/%m/%Y")
        if self.client:
            try:
                prompt = f"""
                Eres un asistente de seguros automotrices en México. Extrae los datos del siguiente mensaje de siniestro.
                Fecha actual de referencia: "{hoy_ddmmaaaa}".
                Lista de ubicaciones válidas: {json.dumps(UBICACIONES_VALIDAS, ensure_ascii=False)}

                Mensaje:
                \"\"\"{texto}\"\"\"

                Responde en JSON estricto:
                {{
                    "tipo": "SINIESTRO",
                    "fecha": "DD/MM/YYYY",
                    "aseguradora": "INBURSA" si el folio empieza con 705 o 305; "SPT" si empieza con 67; "CRABI" si empieza con 2026; sino la aseguradora en mayúsculas,
                    "reporte": "número de reporte",
                    "ubicacion": "UBICACION DEL TABULADOR EN MAYUSCULAS",
                    "vehiculo": "VEHICULO EN MAYUSCULAS"
                }}
                """
                raw = self._generate(prompt, response_mime_type="application/json")
                clean_json = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
                return json.loads(clean_json)
            except Exception as e:
                logger.error(f"Error parseando texto con Gemini: {e}")

        # Fallback local heurístico
        return self._fallback_parse_texto(texto)

    def _fallback_parse_texto(self, texto: str) -> Dict[str, Any]:
        """Reglas heurísticas para texto sin conexión a IA"""
        texto_upper = texto.upper()
        
        # Reporte
        rep_match = re.search(r'\b(\d{5,10})\b', texto)
        reporte = rep_match.group(1) if rep_match else "S/N"
        if "ALE" in texto_upper:
            reporte = "ALE"

        # Aseguradora
        if reporte.startswith("705") or reporte.startswith("305"):
            aseguradora = "INBURSA"
        elif reporte.startswith("67"):
            aseguradora = "SPT"
        elif reporte.startswith("2026"):
            aseguradora = "CRABI"
        else:
            aseguradora = "SPT"
            for cia in ["INBURSA", "SPT", "CRABI", "QUALITAS", "GNP", "AXA", "CHUBB"]:
                if cia in texto_upper:
                    aseguradora = cia
                    break

        # Ubicación
        ubicacion = "LOCAL"
        for u in UBICACIONES_VALIDAS:
            if u in texto_upper:
                ubicacion = u
                break

        # Vehículo
        vehiculo = "S/D"
        for v in ["TRACTO KW", "TRACTO", "URVAN", "TSURU", "VERSA", "MG", "RIO", "YARIS", "RAM", "FIESTA", "ACCENT", "VDRIVE", "V-DRIVE", "AVEO", "MARCH", "BMW NEGRO", "VENTO", "AUDI", "MAZDA", "SENTRA"]:
            if v in texto_upper:
                vehiculo = v
                break

        return {
            "tipo": "SINIESTRO",
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "aseguradora": aseguradora,
            "reporte": reporte,
            "ubicacion": ubicacion,
            "vehiculo": vehiculo
        }

    def _parse_combustible_texto(self, texto: str) -> Dict[str, Any]:
        """Extrae combustible de un mensaje de texto"""
        hoy_yyyymmdd = datetime.now().strftime("%Y-%m-%d")
        odo = None
        odo_match = re.search(r'od[oó]metro\s*[:]?\s*(\d+)', texto, re.IGNORECASE) or re.search(r'\b(\d{5,6})\s*km\b', texto, re.IGNORECASE)
        if odo_match:
            odo = int(odo_match.group(1))

        litros = 0.0
        l_match = re.search(r'(\d+(?:\.\d{1,3})?)\s*(?:litros|lts|l\b)', texto, re.IGNORECASE)
        if l_match:
            litros = float(l_match.group(1))

        monto = 0.0
        m_match = re.search(r'\$\s*(\d+(?:\.\d{1,2})?)', texto) or re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:pesos|mxn)', texto, re.IGNORECASE)
        if m_match:
            monto = float(m_match.group(1))

        precio = round(monto / litros, 2) if (litros > 0 and monto > 0) else 0.0
        tipo_ev = "Recorrido Diario" if (litros == 0 and odo) else ("Carga Tanque Lleno" if "lleno" in texto.lower() else "Carga Parcial")

        return {
            "tipo": "COMBUSTIBLE",
            "fecha": hoy_yyyymmdd,
            "odometro": odo,
            "litros": litros,
            "precio_litro": precio,
            "total_pagado": monto,
            "tipo_evento": tipo_ev
        }

    def parse_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> Dict[str, Any]:
        """Transcripción y análisis de nota de voz"""
        if not self.client:
            return {"tipo": "desconocido", "transcripcion": "Se requiere GEMINI_API_KEY"}

        try:
            from google.genai import types
            prompt = """
            Transcribe esta nota de voz de un ajustador de seguros automotriz.
            Devuelve un JSON con:
            {
                "transcripcion": "texto completo transcrito"
            }
            """
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            raw = self._generate([audio_part, prompt], response_mime_type="application/json")
            clean_json = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()
            res = json.loads(clean_json)
            transcripcion = res.get("transcripcion", "")
            
            data = self.parse_reporte_texto(transcripcion)
            data["transcripcion_audio"] = transcripcion
            return data
        except Exception as e:
            logger.error(f"Error procesando audio con IA: {e}")
            return {"tipo": "desconocido", "transcripcion": "Error al procesar audio"}
