import os
import requests
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """
    Cliente para interactuar con la hoja de cálculo a través del Webhook de Apps Script.
    Fácil de configurar sin necesidad de credenciales complejas de Google Cloud.
    """
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")
        if not self.webhook_url:
            logger.warning("[ADVERTENCIA] GOOGLE_SHEETS_WEBHOOK_URL no configurada.")

    def _post(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.webhook_url:
            return {"status": "mock", "message": "Modo simulación (sin URL configurada)", "data": data}

        payload = {
            "action": action,
            "data": data
        }
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            
            # Intentar decodificar JSON
            try:
                return response.json()
            except Exception:
                # Si la respuesta no es JSON válido (ej: texto plano "OK" o HTML)
                text = response.text.strip()
                if text == "OK":
                    return {"status": "success", "message": "Registrado (respuesta OK)", "data": data}
                return {"status": "error", "message": f"Respuesta no reconocida de Google Sheets: {text[:100]}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def registrar_siniestro(self, siniestro_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra en pestaña 'Registro' (solo columnas A-E) y retorna valores calculados"""
        return self._post("registrar_siniestro", siniestro_data)

    def registrar_combustible(self, combustible_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra en pestaña 'Control Combustible' (solo columnas manuales) y retorna cálculos"""
        return self._post("registrar_combustible", combustible_data)

    def obtener_resumen(self) -> Dict[str, Any]:
        return self._post("obtener_resumen", {})
