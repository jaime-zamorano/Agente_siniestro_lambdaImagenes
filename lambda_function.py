import json
import boto3
import base64
from datetime import datetime

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-2")
dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
tabla_logs = dynamodb.Table("LogsAgenteSiniestros")

BUCKET = "tattersall-siniestro-documentos"


def extraer_datos_carnet(image_bytes, lado):
    """Invoca Claude Vision para extraer datos del carnet."""
    if lado == "anverso":
        prompt = """Extrae los siguientes campos de este carnet de identidad chileno (anverso).
Responde SOLO con un JSON válido con estas claves exactas:
{
  "rut": "",
  "apellidos": "",
  "nombres": "",
  "nacionalidad": "",
  "sexo": "",
  "fecha_nacimiento": "",
  "fecha_emision": "",
  "fecha_vencimiento": "",
  "numero_documento": ""
}
Si no puedes leer un campo, déjalo como cadena vacía."""
    else:
        prompt = """Extrae los datos visibles de este reverso de carnet de identidad chileno.
Responde SOLO con un JSON válido con los campos que puedas identificar."""

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
    text = result["content"][0]["text"]

    # Extraer JSON de la respuesta
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return {}


def guardar_en_dynamodb(session_id, datos_carnet, lado):
    """Agrega la interacción OCR a la conversación existente en DynamoDB."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    texto_usuario = f"[Imagen carnet {lado} enviada]"
    texto_agente = f"He extraído los datos del {lado} del carnet:\n"
    for k, v in datos_carnet.items():
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
    """Registra un error de carga S3 en la conversacion de DynamoDB."""
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    try:
        tabla_logs.update_item(
            Key={"Idsession": session_id},
            UpdateExpression="SET conversacion = list_append(conversacion, :nuevos)",
            ExpressionAttributeValues={
                ":nuevos": [
                    {
                        "rol": "agent",
                        "texto": f"[ERROR OCR] {error_msg}",
                        "timestamp": timestamp
                    }
                ]
            }
        )
    except Exception as e:
        print(f"Error guardando log de error en DynamoDB: {e}")


def lambda_handler(event, context):
    # Extraer parámetros del Bedrock Agent
    action_group = event.get("actionGroup", "")
    function_name = event.get("function", "")
    parameters = event.get("parameters", [])
    params = {p["name"]: p["value"] for p in parameters}

    session_id = params.get("session_id", "")
    lado = params.get("lado", "anverso")

    if not session_id:
        result = {"error": "session_id es requerido"}
    else:
        # Construir ruta S3
        prefix = "anverso-licencia" if lado == "anverso" else "reverso-licencia"
        s3_key = f"Licencia/conductor/{prefix}_{session_id}.jpeg"

        try:
            obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
            image_bytes = obj["Body"].read()

            datos_carnet = extraer_datos_carnet(image_bytes, lado)
            guardar_en_dynamodb(session_id, datos_carnet, lado)

            result = {"success": True, "lado": lado, "datos": datos_carnet}
        except s3.exceptions.NoSuchKey:
            error_msg = f"Imagen no encontrada en s3://{BUCKET}/{s3_key}"
            guardar_error_en_dynamodb(session_id, error_msg)
            result = {"error": error_msg}
        except Exception as e:
            error_msg = f"Error al obtener imagen de S3: {str(e)}"
            guardar_error_en_dynamodb(session_id, error_msg)
            result = {"error": error_msg}

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
