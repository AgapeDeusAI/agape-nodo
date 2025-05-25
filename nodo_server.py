import os
import subprocess
import logging
import requests
import json
from functools import wraps
from datetime import datetime

from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv

# --- Import your existing NodoAI class (assuming it's in NodoAI.py) ---
# Ensure NodoAI.py is in the same directory or properly installed
from NodoAI import NodoAI

# --- Configuration & Environment Setup ---
load_dotenv() # Load environment variables from .env file

# --- Logging Configuration ---
# Set up a robust logger for the entire application
LOG_LEVEL = os.getenv("FLASK_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("nodo_ai_gateway.log"), # Log to a file
        logging.StreamHandler() # Log to console
    ]
)
logger = logging.getLogger(__name__) # Get a logger for this module

# --- Environment Variables ---
# Control Flask debug mode
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
# Port for the Flask app
FLASK_PORT = int(os.getenv("FLASK_PORT", 3000))
# API Key for secure access to the gateway
API_KEY = os.getenv("NODO_AI_API_KEY")

# --- AI Module Configuration ---
# Centralized map for AI modules.
# Prioritize environment variables for production flexibility.
# Use a default structure if ENV vars aren't set, for local dev convenience.
AI_MODULES_CONFIG = {
    "traduzione": os.getenv("AI_MODULE_TRANSLATION_URL", "https://7d0ff2c3-973d-413e-b898-0ef9242ce498-00-2bopjz1135tl2.riker.replit.dev"),
    "voce": os.getenv("AI_MODULE_VOICE_URL", "http://91.99.124.103:3003"),
    "documenti": os.getenv("AI_MODULE_DOCS_URL", "https://25aa5aba-5879-45e3-bca2-e18b5cf623fd-00-39cpeuk7tdz6x.kirk.replit.dev/"),
    "video": os.getenv("AI_MODULE_VIDEO_URL", "https://87774083-f815-480f-9002-1f93141ae4d7-00-38f7m32ec368g.riker.replit.dev"),
    "media": os.getenv("AI_MODULE_MEDIA_URL", "https://c92b386d-5f8e-4376-8d42-05cde2043bf0-00-1m7yu23sxbbua.riker.replit.dev"),
    "finance": os.getenv("AI_MODULE_FINANCE_URL", "https://f6619c52-7895-4643-a9df-d243d0ff126f-00-26hfxudsay4t2.picard.replit.dev"),
    "code": os.getenv("AI_MODULE_CODE_URL", "https://7b782f3c-d803-4c9f-b0aa-390a5384be0e-00-3o4ya13bfhk1l.spock.replit.dev/")
}

# --- Initialize NodoAI Core ---
nodo = NodoAI(AI_MODULES_CONFIG)
logger.info(f"NodoAI gateway initialized with modules: {list(AI_MODULES_CONFIG.keys())}")

# --- Flask Application Setup ---
app = Flask(__name__)
CORS(app) # Enable Cross-Origin Resource Sharing for all routes
app.config['DEBUG'] = FLASK_DEBUG # Set Flask debug mode based on environment variable
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True # Pretty print JSON responses

# --- Utility Decorators for API Perfection ---

def require_api_key(view_function):
    """
    Decorator to enforce API key authentication.
    Checks for 'X-API-Key' in headers.
    """
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if app.config['DEBUG']:
            # Skip API key check in debug mode for easier local development
            logger.debug("API key check skipped in debug mode.")
            return view_function(*args, **kwargs)

        if not API_KEY:
            # If API_KEY is not set in environment, this is a misconfiguration
            logger.error("API_KEY environment variable is not set. Gateway is insecure!")
            abort(500, description="Server misconfiguration: API key not set.")

        client_api_key = request.headers.get('X-API-Key')
        if not client_api_key or client_api_key != API_KEY:
            logger.warning(f"Unauthorized access attempt from {request.remote_addr} to {request.path}. Invalid or missing API Key.")
            abort(401, description="Unauthorized: Invalid or missing API Key.")
        return view_function(*args, **kwargs)
    return decorated_function

def validate_json_input(required_keys=None):
    """
    Decorator to validate JSON request body and required keys.
    """
    if required_keys is None:
        required_keys = []

    def decorator(view_function):
        @wraps(view_function)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                logger.warning(f"Bad Request: Non-JSON content type for {request.path}.")
                abort(400, description="Content-Type must be application/json.")
            
            data = request.get_json()
            if not data:
                logger.warning(f"Bad Request: Empty JSON body for {request.path}.")
                abort(400, description="Empty JSON body provided.")
            
            for key in required_keys:
                if key not in data:
                    logger.warning(f"Bad Request: Missing required parameter '{key}' in JSON body for {request.path}.")
                    abort(400, description=f"Missing required JSON parameter: '{key}'.")
            
            # Optionally, you could store the parsed JSON in g or something for easy access
            # flask.g.request_data = data
            return view_function(*args, **kwargs)
        return decorated_function
    return decorator

def handle_api_exceptions(f):
    """
    Decorator to catch and log common exceptions for API endpoints,
    returning a consistent error response.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # Log the full traceback for unhandled exceptions
            logger.exception(f"Unhandled exception in API endpoint {request.path}: {e}")
            # Return a generic 500 error to the client to avoid leaking internal details
            abort(500, description=f"Internal Server Error: An unexpected error occurred. Please try again later.")
    return decorated_function

# --- API Endpoints ---

@app.route("/", methods=["GET"])
@handle_api_exceptions
def home():
    """
    Provides a status overview of the Nodo AI Gateway and lists available modules.
    """
    logger.info("Home endpoint accessed.")
    current_time = datetime.now().isoformat()
    return jsonify({
        "status": "✅ Nodo AI Gateway is active and operational.",
        "message": "Welcome to the central AI module gateway. Use /ping for module health, and /inoltra to route requests.",
        "timestamp": current_time,
        "available_modules": list(AI_MODULES_CONFIG.keys())
    })

@app.route("/ping", methods=["GET"])
@require_api_key
@handle_api_exceptions
def ping_modules():
    """
    Checks the health status of all configured AI modules.
    Returns a dictionary of module names to their boolean health status.
    """
    logger.info("Ping endpoint accessed. Checking module health...")
    # Use the ping_moduli method from the NodoAI instance
    module_statuses = nodo.ping_moduli()
    
    response = {
        "status": "AI Module Health Check Completed",
        "timestamp": datetime.now().isoformat(),
        "module_health": module_statuses,
        "active_modules_count": sum(1 for status in module_statuses.values() if status),
        "total_modules_configured": len(AI_MODULES_CONFIG)
    }
    logger.info(f"Module health check results: {response}")
    return jsonify(response)

@app.route("/inoltra/<modulo>/<endpoint>", methods=["GET", "POST", "PUT", "DELETE"])
@require_api_key
@handle_api_exceptions
def inoltra(modulo, endpoint):
    """
    Forwards incoming requests to the specified AI module's endpoint.
    Supports GET, POST, PUT, and DELETE methods.
    """
    logger.info(f"Inoltra request received for module: '{modulo}', endpoint: '{endpoint}' (Method: {request.method}).")

    if modulo not in AI_MODULES_CONFIG:
        logger.warning(f"Attempted to forward to non-existent module: '{modulo}'.")
        abort(404, description=f"Modulo '{modulo}' non trovato o non configurato.")

    payload = {}
    # Handle request body based on method and content type
    if request.method in ["POST", "PUT"]:
        if request.is_json:
            payload = request.get_json()
            logger.debug(f"JSON payload received for {modulo}/{endpoint}: {payload.keys()}")
        elif request.form:
            payload = request.form.to_dict() # For form data
            logger.debug(f"Form data payload received for {modulo}/{endpoint}: {payload.keys()}")
        else:
            logger.warning(f"No valid JSON or form data found for POST/PUT request to {modulo}/{endpoint}.")
            # It's better to allow empty payload for POST/PUT rather than forcing it
            # abort(400, description="Request body must be JSON or form data for POST/PUT methods.")
    elif request.method == "GET":
        payload = request.args.to_dict() # GET parameters
        logger.debug(f"GET parameters received for {modulo}/{endpoint}: {payload.keys()}")
    # For DELETE, payload is typically in query params or headers, or empty

    # Pass original headers from client to the target module, excluding host and content-length for direct proxy
    forward_headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in ['host', 'content-length', 'x-api-key'] # Exclude internal headers
    }
    # Add API_KEY to the internal module request headers for internal module authentication
    if API_KEY:
        forward_headers['X-API-Key'] = API_KEY
        logger.debug("Internal API key added to forward headers.")


    # Call NodoAI's inoltra_richiesta with dynamic method and headers
    try:
        risposta = nodo.inoltra_richiesta(
            modulo,
            endpoint,
            payload,
            method=request.method,
            headers=forward_headers
        )
        logger.info(f"Successfully forwarded request to {modulo}/{endpoint}.")
        return jsonify(risposta)
    except Exception as e:
        # NodoAI.inoltra_richiesta already handles internal errors and returns a dict
        # We can directly return its error response, as it's designed to be client-friendly
        logger.error(f"Error forwarding request for {modulo}/{endpoint}: {e}")
        # Assuming NodoAI.inoltra_richiesta returns a dict with 'success' and 'errore'
        error_response = {"success": False, "errore": f"Gateway forwarding error: {str(e)}"}
        # If NodoAI provided a specific status code (e.g., in its error dict), we could use it.
        # For now, returning a generic 500 if the forwarding itself throws an unhandled exception.
        abort(500, description="Error forwarding request to target module.")


# --- Global Error Handlers (for errors not caught by decorators) ---
@app.errorhandler(400)
def bad_request(error):
    logger.error(f"HTTP 400 Bad Request: {error.description}")
    return jsonify({"success": False, "errore": error.description}), 400

@app.errorhandler(401)
def unauthorized(error):
    logger.error(f"HTTP 401 Unauthorized: {error.description}")
    return jsonify({"success": False, "errore": error.description}), 401

@app.errorhandler(404)
def not_found(error):
    logger.warning(f"HTTP 404 Not Found: {request.path}")
    return jsonify({"success": False, "errore": f"Risorsa non trovata: {error.description}"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    logger.warning(f"HTTP 405 Method Not Allowed: {request.method} for {request.path}")
    return jsonify({"success": False, "errore": "Metodo non consentito per questa risorsa."}), 405

@app.errorhandler(500)
def internal_server_error(error):
    logger.critical(f"HTTP 500 Internal Server Error: {error.description}", exc_info=True)
    return jsonify({"success": False, "errore": "Errore interno del server. Riprova più tardi."}), 500

# --- Application Startup ---
if __name__ == "__main__":
    if not API_KEY and not FLASK_DEBUG:
        logger.critical("SECURITY WARNING: API_KEY is not set in production mode. Gateway is insecure!")
        # Optionally, sys.exit(1) here in a real production setup
    
    logger.info(f"Starting Nodo AI Gateway on 0.0.0.0:{FLASK_PORT} (Debug: {FLASK_DEBUG})...")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)

