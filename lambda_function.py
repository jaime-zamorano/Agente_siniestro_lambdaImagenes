import json
import boto3
import base64
from datetime import datetime

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-2")
dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
tabla_logs = dynamodb.Table("LogsAgenteSiniestros")

BUCKET = "tattersall-siniestro-documentos"


def invocar_claude_vision(image_bytes, prompt):
    """Invoca Claude Vision con una imagen y un prompt."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}},
                {"type": "text", "text": prompt}
            ]
        }]
    })

    response = bedrock.invoke_model(
        modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        contentType="application/json",
        accept="application/json",
        body=body
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def parsear_json(text):
    """Extrae el primer JSON válido de un texto."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return None


def verificar_documento(image_bytes, nombre_documento):
    """Verifica si la imagen corresponde al tipo de documento esperado."""
    prompt = f"""Analiza esta imagen y determina si es una {nombre_documento}.
Responde SOLO con un JSON válido:
{{"es_documento_valido": true/false, "motivo": "explicación breve"}}"""

    text = invocar_claude_vision(image_bytes, prompt)
    return parsear_json(text) or {"es_documento_valido": False, "motivo": "No se pudo analizar la imagen"}


def guardar_en_dynamodb(session_id, datos, lado):
    """Agrega la interacción OCR a la conversación existente en DynamoDB."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    texto_usuario = f"[Imagen {lado} enviada]"
    texto_agente = f"He extraído los datos del {lado}:\n"
    for k, v in datos.items():
        if v:
            texto_agente += f"- {k.replace('_', ' ').title()}: {v}\n"

    try:
        tabla_logs.update_item(
            Key={"Idsession": session_id},
            UpdateExpression="SET conversacion = list_append(conversacion, :nuevos)",
            ExpressionAttributeValues={
                ":nuevos": [
                    {"rol": "user", "texto": texto_usuario, "timestamp": timestamp},
                    {"rol": "agent", "texto": texto_agente.strip(), "timestamp": timestamp}
                ]
            }
        )
    except Exception as e:
        print(f"Error guardando en DynamoDB: {e}")


def guardar_error_en_dynamodb(session_id, error_msg):
    """Registra un error en la conversacion de DynamoDB."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    try:
        tabla_logs.update_item(
            Key={"Idsession": session_id},
            UpdateExpression="SET conversacion = list_append(conversacion, :nuevos)",
            ExpressionAttributeValues={
                ":nuevos": [
                    {"rol": "agent", "texto": f"[ERROR OCR] {error_msg}", "timestamp": timestamp}
                ]
            }
        )
    except Exception as e:
        print(f"Error guardando log de error en DynamoDB: {e}")


# ==================== SERVICIO LICENCIA DE CONDUCIR ====================

def procesar_licencia(session_id, lado):
    """Servicio para procesar licencia de conducir."""
    prefix = "anverso-licencia" if lado == "anverso" else "reverso-licencia"
    s3_key = f"Licencia/conductor/{prefix}_{session_id}.jpeg"

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
        image_bytes = obj["Body"].read()

        verificacion = verificar_documento(image_bytes, "LICENCIA DE CONDUCIR")
        if not verificacion.get("es_documento_valido", False):
            return {"success": False, "error": "documento_no_valido", "mensaje": verificacion.get("motivo")}

        if lado == "anverso":
            prompt = """Extrae los siguientes campos de esta licencia de conducir chilena (anverso).
Responde SOLO con un JSON válido con estas claves exactas:
{
  "rut": "",
  "apellidos": "",
  "nombres": "",
  "clase_licencia": "",
  "fecha_ultimo_control": "",
  "fecha_vencimiento": "",
  "municipalidad": ""
}
Si no puedes leer un campo, déjalo como cadena vacía."""
        else:
            prompt = """Extrae los datos visibles de este reverso de licencia de conducir chilena.
Responde SOLO con un JSON válido con los campos que puedas identificar."""

        text = invocar_claude_vision(image_bytes, prompt)
        datos = parsear_json(text) or {}
        guardar_en_dynamodb(session_id, datos, lado)
        return {"success": True, "lado": lado, "datos": datos}

    except s3.exceptions.NoSuchKey:
        error_msg = f"Imagen no encontrada en s3://{BUCKET}/{s3_key}"
        guardar_error_en_dynamodb(session_id, error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error al obtener imagen de S3: {str(e)}"
        guardar_error_en_dynamodb(session_id, error_msg)
        return {"error": error_msg}


# ==================== SERVICIO CÉDULA DE IDENTIDAD ====================

def procesar_cedula(session_id, lado):
    """Servicio para procesar cédula de identidad."""
    prefix = "anverso-carnet" if lado == "anverso" else "reverso-carnet"
    s3_key = f"carnets/conductor/{prefix}-{session_id}.jpeg"

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
        image_bytes = obj["Body"].read()

        verificacion = verificar_documento(image_bytes, "CÉDULA DE IDENTIDAD chilena que contiene los textos 'CÉDULA DE IDENTIDAD' y 'REPÚBLICA DE CHILE' visibles en el documento")
        if not verificacion.get("es_documento_valido", False):
            return {"success": False, "error": "documento_no_valido", "mensaje": verificacion.get("motivo")}

        if lado == "anverso":
            prompt = """Extrae los siguientes campos de esta cédula de identidad chilena (anverso).
Responde SOLO con un JSON válido con estas claves exactas:
{
  "Apellidos": "",
  "Nombres": "",
  "Nacionalidad": "",
  "Sexo": "",
  "Fecha_Nacimiento": "",
  "Numero_Documento": "",
  "Fecha_Emision": "",
  "Fecha_vencimiento": "",
  "Run": "",
  "Nacio_en": "",
  "Profesion": ""
}
Si no puedes leer un campo, déjalo como cadena vacía."""
        else:
            prompt = """Extrae los datos visibles de este reverso de cédula de identidad chilena.
Responde SOLO con un JSON válido con los campos que puedas identificar."""

        text = invocar_claude_vision(image_bytes, prompt)
        datos = parsear_json(text) or {}
        guardar_en_dynamodb(session_id, datos, lado)
        return {"success": True, "lado": lado, "datos": datos}

    except s3.exceptions.NoSuchKey:
        error_msg = f"Imagen no encontrada en s3://{BUCKET}/{s3_key}"
        guardar_error_en_dynamodb(session_id, error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error al obtener imagen de S3: {str(e)}"
        guardar_error_en_dynamodb(session_id, error_msg)
        return {"error": error_msg}


# ==================== HANDLER ====================

def lambda_handler(event, context):
    action_group = event.get("actionGroup", "")
    function_name = event.get("function", "")
    parameters = event.get("parameters", [])
    params = {p["name"]: p["value"] for p in parameters}

    session_id = params.get("session_id", "")
    lado = params.get("lado", "anverso")

    if not session_id:
        result = {"error": "session_id es requerido"}
    elif function_name == "procesar_cedula_identidad":
        result = procesar_cedula(session_id, lado)
    else:
        result = procesar_licencia(session_id, lado)

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "function": function_name,
            "functionResponse": {
                "responseBody": {
                    "TEXT": {
                        "body": json.dumps(result, ensure_ascii=False)
                    }
                }
            }
        }
    }
