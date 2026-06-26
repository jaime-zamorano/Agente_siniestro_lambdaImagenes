# Lambda OCR Imágenes

Lambda Python que extrae datos de carnet de identidad chileno usando Claude Vision (Bedrock), invocada por un Agente de Bedrock.

## Arquitectura

```
App Kotlin → API Gateway → Bedrock Agent → Lambda OCR → S3 (imagen) → Claude Vision → DynamoDB + Respuesta
```

## Archivos

- `lambda_function.py` - Código de la Lambda
- `openapi_schema.json` - Schema OpenAPI para el Action Group de Bedrock

## Permisos IAM necesarios

La Lambda necesita:
- `s3:GetObject` en `arn:aws:s3:::tattersall-siniestro-documentos/carnets/*`
- `bedrock:InvokeModel` en `arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-20250514`
- `dynamodb:UpdateItem` en `arn:aws:dynamodb:us-east-2:235494813360:table/LogsAgenteSiniestros`

## Configurar en Bedrock Agent

1. Ir a **Amazon Bedrock → Agents → Tu Agente**
2. En **Action Groups**, crear uno nuevo:
   - Nombre: `procesar-carnet-ocr`
   - Lambda: `lambda-ocr-imagenes`
   - Schema: Subir `openapi_schema.json`
3. Guardar y preparar el agente

## Ruta S3 esperada

```
s3://tattersall-siniestro-documentos/carnets/{session_id}/anverso-carnet_{session_id}_{correlativo}.jpeg
s3://tattersall-siniestro-documentos/carnets/{session_id}/reverso-carnet_{session_id}_{correlativo}.jpeg
```

## Variables de entorno

No requiere variables de entorno (usa boto3 con rol IAM).

## Ejemplo de invocación

El agente recibe: "Procesa mi carnet" y automáticamente invoca con:
- `session_id`: `sess_1782498768658_1bd49178-`
- `lado`: `anverso`
- `correlativo`: `1`
