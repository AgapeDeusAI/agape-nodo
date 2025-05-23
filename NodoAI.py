import requests
import logging

class NodoAI:
    def __init__(self, nodi_attivi: dict):
        self.nodi = nodi_attivi
        self.logger = logging.getLogger("NodoAI")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def ping_moduli(self):
        stati = {}
        for nome, url in self.nodi.items():
            try:
                response = requests.get(url, timeout=3)
                stati[nome] = response.status_code == 200
            except Exception as e:
                stati[nome] = False
                self.logger.warning(f"❌ Nodo {nome} non raggiungibile: {e}")
        return stati

    def inoltra_richiesta(self, modulo: str, endpoint: str, payload: dict) -> dict:
        base_url = self.nodi.get(modulo)
        if not base_url:
            return {"success": False, "errore": f"Modulo '{modulo}' non trovato."}

        try:
            response = requests.post(f"{base_url}/{endpoint}", json=payload, timeout=10)
            return response.json()
        except Exception as e:
            self.logger.error(f"Errore inoltro: {e}")
            return {"success": False, "errore": str(e)}