import os
import logging
import requests
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv
from NodoAI import NodoAI

# === CONFIG ===
load_dotenv()
FLASK_PORT = int(os.getenv("FLASK_PORT", 3000))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
API_KEY = os.getenv("NODO_AI_API_KEY")

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("nodo_ai.log"), logging.StreamHandler()]
)
logger = logging.getLogger("NodoAI")

# === MODULI CONFIG ===
AI_MODULES_CONFIG = {
    "traduzione": os.getenv("AI_MODULE_TRANSLATION_URL"),
    "voce": os.getenv("AI_MODULE_VOICE_URL"),
    "documenti": os.getenv("AI_MODULE_DOCS_URL"),
    "video": os.getenv("AI_MODULE_VIDEO_URL"),
    "media": os.getenv("AI_MODULE_MEDIA_URL"),
    "finance": os.getenv("AI_MODULE_FINANCE_URL"),
    "code": os.getenv("AI_MODULE_CODE_URL"),
    "apprendimento": os.getenv("AI_MODULE_LEARNING_URL")
}

nodo = NodoAI(AI_MODULES_CONFIG)

# === FLASK SETUP ===
app = Flask(__name__)
CORS(app)
app.config['DEBUG'] = FLASK_DEBUG
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# === DECORATORI ===
def require_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if FLASK_DEBUG:
            return f(*args, **kwargs)
        if not API_KEY:
            abort(500, description="API Key mancante.")
        client_key = request.headers.get("X-API-Key")
        if client_key != API_KEY:
            abort(401, description="API Key non valida.")
        return f(*args, **kwargs)
    return wrapper

def handle_api_exceptions(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Errore interno: {e}")
            abort(500, description="Errore interno del server.")
    return decorated

# === ENDPOINTS ===
@app.route("/", methods=["GET"])
@handle_api_exceptions
def home():
    return jsonify({
        "status": "✅ Nodo AI Gateway attivo",
        "modules": list(AI_MODULES_CONFIG.keys()),
        "timestamp": datetime.now().isoformat()
    })

@app.route("/ping", methods=["GET"])
@require_api_key
@handle_api_exceptions
def ping():
    status = nodo.ping_moduli()
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "moduli": status,
        "totali": len(status)
    })

@app.route("/inoltra/<modulo>/<endpoint>", methods=["GET", "POST"])
@require_api_key
@handle_api_exceptions
def inoltra(modulo, endpoint):
    if modulo not in AI_MODULES_CONFIG:
        abort(404, description=f"Modulo '{modulo}' non configurato.")
    
    dati = {}
    if request.method == "GET":
        dati = request.args.to_dict()
    elif request.method == "POST":
        if request.is_json:
            dati = request.get_json()
        else:
            dati = request.form.to_dict()
    
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    headers["X-API-Key"] = API_KEY
    
    risposta = nodo.inoltra_richiesta(modulo, endpoint, dati, method=request.method, headers=headers)
    return jsonify(risposta)

# === ERRORI COMUNI ===
@app.errorhandler(400)
def bad_request(e): return jsonify(success=False, errore=e.description), 400

@app.errorhandler(401)
def unauthorized(e): return jsonify(success=False, errore=e.description), 401

@app.errorhandler(404)
def not_found(e): return jsonify(success=False, errore=e.description), 404

@app.errorhandler(500)
def server_error(e): return jsonify(success=False, errore="Errore interno del server."), 500

# === AVVIO SERVER ===
if __name__ == "__main__":
    if not API_KEY and not FLASK_DEBUG:
        logger.critical("API Key mancante. Arresto per sicurezza.")
    logger.info(f"Avvio Nodo AI su 0.0.0.0:{FLASK_PORT}")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=FLASK_DEBUG)