"""
Wrapper Flask para ejecutar la Lambda localmente con Swagger UI.
Uso: python app.py
Swagger UI: http://localhost:5000/swagger
"""

from flask import Flask, request, jsonify, send_file
from flask_swagger_ui import get_swaggerui_blueprint
from lambda_function import lambda_handler

app = Flask(__name__)

# --- Swagger UI ---
SWAGGER_URL = "/swagger"
API_URL = "/openapi.json"

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "OCR Imágenes Siniestros - Local"}
)
app.register_blueprint(swaggerui_blueprint)


@app.route("/openapi.json")
def openapi_spec():
    return send_file("openapi_schema.json", mimetype="application/json")


@app.route("/procesar-carnet", methods=["POST"])
def procesar_carnet():
    """Simula la invocación del Bedrock Agent hacia la Lambda."""
    session_id = request.args.get("session_id", "")
    lado = request.args.get("lado", "anverso")

    # Construir evento como lo envía Bedrock Agent
    event = {
        "actionGroup": "procesar-carnet-ocr",
        "function": "procesarCarnet",
        "parameters": [
            {"name": "session_id", "value": session_id},
            {"name": "lado", "value": lado}
        ]
    }

    # Invocar la Lambda
    response = lambda_handler(event, None)

    # Extraer el body de la respuesta del agente
    try:
        body_text = response["response"]["functionResponse"]["responseBody"]["TEXT"]["body"]
        result = __import__("json").loads(body_text)
        status_code = 200 if "error" not in result else (400 if "requerido" in result.get("error", "") else 404)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n* Lambda OCR corriendo localmente")
    print("* Swagger UI: http://localhost:5000/swagger\n")
    app.run(debug=True, port=5000)
