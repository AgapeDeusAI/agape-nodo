import requests
import logging
import json # Explicitly import for potential JSON decoding errors
from functools import wraps # Best practice for decorators, though not directly used in this class

class NodoAI:
    def __init__(self, nodi_attivi: dict):
        """
        Initializes the NodoAI with a dictionary of active nodes.

        Args:
            nodi_attivi (dict): A dictionary where keys are module names (str)
                                and values are their base URLs (str).
        """
        self.nodi = nodi_attivi
        # Get a logger specific to this class.
        # It's crucial that basicConfig (or other logging setup) is done
        # at the application's entry point, not repeatedly here.
        self.logger = logging.getLogger("NodoAI")
        # Ensure logging is configured externally. If not, this warning helps identify it.
        if not self.logger.handlers:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            self.logger.warning("Logging not pre-configured. Basic logging set up within NodoAI. Consider configuring it globally at app startup.")

    def ping_moduli(self) -> dict:
        """
        Pings all registered AI modules to check their availability.

        Returns:
            dict: A dictionary where keys are module names and values are booleans
                  indicating their reachability (True if reachable, False otherwise).
        """
        stati = {}
        self.logger.info("Starting health check for all registered AI modules...")
        for nome, url in self.nodi.items():
            try:
                # Increased timeout for robustness on network delays
                response = requests.get(url.rstrip('/'), timeout=5) # Ensure no trailing slash for ping
                if response.status_code == 200:
                    stati[nome] = True
                    self.logger.info(f"✅ Nodo '{nome}' at {url} is reachable (Status: {response.status_code}).")
                else:
                    stati[nome] = False
                    self.logger.warning(f"⚠️ Nodo '{nome}' at {url} returned non-200 status: {response.status_code}.")
            except requests.exceptions.ConnectionError:
                stati[nome] = False
                self.logger.error(f"❌ Nodo '{nome}' at {url} - Connection Error: The module could not be reached.")
            except requests.exceptions.Timeout:
                stati[nome] = False
                self.logger.error(f"❌ Nodo '{nome}' at {url} - Timeout Error: The request timed out after 5 seconds.")
            except requests.exceptions.RequestException as e:
                # Catch any other requests-related errors (e.g., DNS issues, SSL errors)
                stati[nome] = False
                self.logger.error(f"❌ Nodo '{nome}' at {url} - Request Exception: {e}", exc_info=False) # exc_info=True for full traceback
            except Exception as e:
                # Catch any other unexpected errors during ping
                stati[nome] = False
                self.logger.critical(f"❌ Nodo '{nome}' at {url} - An unexpected error occurred during ping: {e}", exc_info=True)
        self.logger.info("AI module health check completed.")
        return stati

    def inoltra_richiesta(self, modulo: str, endpoint: str, payload: dict, method: str = "POST", headers: dict = None) -> dict:
        """
        Forwards a request to a specified AI module's endpoint.

        Args:
            modulo (str): The name of the target AI module (e.g., "traduzione").
            endpoint (str): The specific API endpoint on the module (e.g., "analizza").
            payload (dict): The JSON payload to send with the request.
            method (str): The HTTP method to use (e.g., "POST", "GET"). Defaults to "POST".
            headers (dict, optional): Additional HTTP headers to send. Defaults to None.

        Returns:
            dict: The JSON response from the module, or a detailed error dictionary
                  if the request fails.
        """
        base_url = self.nodi.get(modulo)
        if not base_url:
            error_msg = f"Modulo '{modulo}' non trovato o non configurato. Moduli disponibili: {list(self.nodi.keys())}"
            self.logger.warning(error_msg)
            return {"success": False, "errore": error_msg, "status_code": 404}

        # Robust URL construction: ensures exactly one slash between base_url and endpoint
        full_url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Prepare headers, ensuring Content-Type is set for JSON requests if not provided
        effective_headers = {} if headers is None else headers.copy()
        if method.upper() in ["POST", "PUT", "PATCH"] and "Content-Type" not in effective_headers:
            effective_headers["Content-Type"] = "application/json"

        self.logger.info(f"Forwarding {method.upper()} request to '{modulo}' ({full_url}) with payload keys: {list(payload.keys())}")

        try:
            # Use requests.request for flexible HTTP methods
            response = requests.request(
                method=method.upper(),
                url=full_url,
                json=payload if method.upper() in ["POST", "PUT", "PATCH"] else None, # Only send JSON for methods that typically have a body
                params=payload if method.upper() == "GET" else None, # Send as query params for GET
                headers=effective_headers,
                timeout=15 # Increased timeout for long-running AI tasks
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            try:
                return response.json()
            except json.JSONDecodeError:
                self.logger.error(f"Invalid JSON response from '{modulo}' at {full_url}. Raw response: {response.text[:200]}...")
                return {
                    "success": False,
                    "errore": f"Risposta JSON non valida dal modulo '{modulo}'.",
                    "status_code": 502, # Bad Gateway for malformed response
                    "details": response.text # Include raw text for debugging
                }

        except requests.exceptions.HTTPError as e:
            # Handles 4xx or 5xx responses from the target module
            status_code = e.response.status_code if e.response is not None else 500
            response_text = e.response.text if e.response is not None else "No response body."
            
            self.logger.error(f"HTTP Error from '{modulo}' ({full_url}): Status {status_code} - {response_text[:200]}...")
            
            error_details = {"success": False, "errore": f"Errore HTTP dal modulo '{modulo}': {status_code}"}
            try:
                # Attempt to parse error message from target module if it's JSON
                error_details["details"] = e.response.json() if e.response else None
            except json.JSONDecodeError:
                error_details["details"] = response_text # Fallback to raw text if not JSON
            error_details["status_code"] = status_code
            return error_details

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection Error forwarding to '{modulo}' at {full_url}: The module could not be reached.")
            return {
                "success": False,
                "errore": f"Errore di connessione al modulo '{modulo}'. Il modulo potrebbe essere offline o non raggiungibile.",
                "status_code": 503 # Service Unavailable
            }
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout Error forwarding to '{modulo}' at {full_url}: The request timed out after 15 seconds.")
            return {
                "success": False,
                "errore": f"Timeout durante l'inoltro della richiesta al modulo '{modulo}'.",
                "status_code": 504 # Gateway Timeout
            }
        except requests.exceptions.RequestException as e:
            # Catch any other requests-related errors (e.g., DNS resolution failure, SSL certificate errors)
            self.logger.error(f"General Request Exception forwarding to '{modulo}' at {full_url}: {e}", exc_info=False)
            return {
                "success": False,
                "errore": f"Errore di richiesta generico durante l'inoltro al modulo '{modulo}': {str(e)}",
                "status_code": 500
            }
        except Exception as e:
            # Catch any other unexpected, non-requests-specific errors
            self.logger.critical(f"An unexpected internal error occurred during request forwarding to {full_url}: {e}", exc_info=True)
            return {
                "success": False,
                "errore": f"Errore interno imprevisto durante l'inoltro: {str(e)}",
                "status_code": 500
            }

