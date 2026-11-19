import os
import requests
from typing import Dict, Any, Optional

class GoogleSheetsClient:
    """
    Cliente para interactuar con la hoja de cálculo a través del Webhook de Apps Script.
    Fácil de configurar sin necesidad de credenciales complejas de Google Cloud.
    """
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")
        if not self.webhook_url:
            print("[ADVERTENCIA] GOOGLE_SHEETS_WEBHOOK_URL no configurada.")

    def _post(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.webhook_url:
            return {"status": "mock", "message": "Modo simulación (sin URL configurada)", "data": data}

        payload = {
            "action": action,
            "data": data
        }
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=25)
            response.raise_for_status()
            return response.json()
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
