
from flask import Flask, request, jsonify
from flask_cors import CORS
from NodoAI import NodoAI  # Importa la classe corretta

app = Flask(__name__)
CORS(app)

# Mappa dei moduli AI
nodi = {
    "traduzione": "https://7d0ff2c3-973d-413e-b898-0ef9242ce498-00-2bopjz1135tl2.riker.replit.dev",
    "voce": "https://fa5eaf9a-3776-4603-89d4-6db457092e0b-00-180z9at4za2og.riker.replit.dev",
    "documenti": "https://25aa5aba-5879-45e3-bca2-e18b5cf623fd-00-39cpeuk7tdz6x.kirk.replit.dev",
    "video": "https://87774083-f815-480f-9002-1f93141ae4d7-00-38f7m32ec368g.riker.replit.dev",
    "media": "https://c92b386d-5f8e-4376-8d42-05cde2043bf0-00-1m7yu23sxbbua.riker.replit.dev",
    "finance": "https://f6619c52-7895-4643-a9df-d243d0ff126f-00-26hfxudsay4t2.picard.replit.dev",
    "code": "https://7b782f3c-d803-4c9f-b0aa-390a5384be0e-00-3o4ya13bfhk1l.spock.replit.dev"
}

nodo = NodoAI(nodi)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "✅ Nodo AI attivo", "moduli": list(nodi.keys())})

@app.route("/ping", methods=["GET"])
def ping():
    stati = nodo.ping_moduli()
    stati["moduli"] = list(nodi.keys())
    stati["status"] = "Nodo AI attivo"
    return jsonify(stati)

@app.route("/inoltra/<modulo>/<endpoint>", methods=["POST"])
def inoltra(modulo, endpoint):
    data = request.get_json()
    risposta = nodo.inoltra_richiesta(modulo, endpoint, data)
    return jsonify(risposta)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
