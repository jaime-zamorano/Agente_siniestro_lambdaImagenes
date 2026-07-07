# Lambda OCR Imágenes

Lambda Python que extrae datos de licencia de conducir y cédula de identidad chilena usando Claude Vision (Bedrock), invocada por un Agente de Bedrock.

## Arquitectura

```
App Kotlin → API Gateway → Bedrock Agent → Lambda OCR → S3 (imagen) → Claude Vision → DynamoDB + Respuesta
```

## Servicios

### 1. Procesar Licencia de Conducir
- **function_name**: `procesarLicencia`
- **Ruta S3**: `Licencia/conductor/anverso-licencia_{session_id}.jpeg` / `reverso-licencia_{session_id}.jpeg`
- **Campos extraídos**: rut, apellidos, nombres, clase_licencia, fecha_emision, fecha_vencimiento, municipalidad

### 2. Procesar Cédula de Identidad
- **function_name**: `procesarCedulaIdentidad`
- **Ruta S3**: `carnets/conductor/anverso-carnet-{session_id}.jpeg` / `reverso-carnet-{session_id}.jpeg`
- **Campos extraídos**: Apellidos, Nombres, Nacionalidad, Sexo, Fecha_Nacimiento, Numero_Documento, Fecha_Emision, Fecha_vencimiento, Run, Nacio_en, Profesion

## Archivos

- `lambda_function.py` - Código de la Lambda
- `openapi_schema.json` - Schema OpenAPI para el Action Group de Bedrock
- `app.py` - Wrapper Flask para testing local con Swagger UI
- `requirements-dev.txt` - Dependencias para desarrollo local

## Permisos IAM necesarios

La Lambda necesita:
- `s3:GetObject` en `arn:aws:s3:::tattersall-siniestro-documentos/Licencia/conductor/*`
- `s3:GetObject` en `arn:aws:s3:::tattersall-siniestro-documentos/carnets/conductor/*`
- `bedrock:InvokeModel` en `arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-20250514`
- `dynamodb:UpdateItem` en `arn:aws:dynamodb:us-east-2:235494813360:table/LogsAgenteSiniestros`

## Configurar en Bedrock Agent

1. Ir a **Amazon Bedrock → Agents → Tu Agente**
2. En **Action Groups**, crear uno nuevo:
   - Nombre: `procesar-documentos-ocr`
   - Lambda: `lambda-ocr-imagenes`
   - Schema: Subir `openapi_schema.json`
3. Guardar y preparar el agente

## Variables de entorno

No requiere variables de entorno (usa boto3 con rol IAM).

## Ejemplo de invocación

El agente recibe: "Procesa mi licencia" y automáticamente invoca con:
- `session_id`: `sess_1782498768658_1bd49178-`
- `lado`: `anverso`

El agente recibe: "Procesa mi cédula de identidad" y automáticamente invoca con:
- `session_id`: `sess_1782498768658_1bd49178-`
- `lado`: `anverso`

## Desarrollo local

```bash
pip install -r requirements-dev.txt
python app.py
```

Swagger UI disponible en: http://localhost:5000/swagger
