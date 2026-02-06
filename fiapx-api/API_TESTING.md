# FIAP X - Guia de Teste da API

## Swagger UI

Acesse a documentacao interativa em:
```
http://localhost:8000/docs
```

## Exemplos com cURL

### 1. Registrar Usuario

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teste@exemplo.com",
    "password": "MinhaSenh@123",
    "name": "Usuario Teste"
  }'
```

**Resposta:**
```json
{
  "id": "uuid-do-usuario",
  "email": "teste@exemplo.com",
  "name": "Usuario Teste",
  "is_active": true,
  "created_at": "2026-02-03T20:00:00Z"
}
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teste@exemplo.com",
    "password": "MinhaSenh@123"
  }'
```

**Resposta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Salvar o token:**
```bash
export TOKEN="eyJhbGciOiJIUzI1NiIs..."
```

### 3. Verificar Usuario Logado

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Upload de Video

```bash
curl -X POST http://localhost:8000/api/v1/videos/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/caminho/para/video.mp4"
```

**Resposta:**
```json
{
  "job_id": "uuid-do-job",
  "status": "QUEUED",
  "message": "Video queued for processing"
}
```

**Salvar o job_id:**
```bash
export JOB_ID="uuid-do-job"
```

### 5. Listar Videos

```bash
curl -X GET http://localhost:8000/api/v1/videos \
  -H "Authorization: Bearer $TOKEN"
```

**Com paginacao:**
```bash
curl -X GET "http://localhost:8000/api/v1/videos?skip=0&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Ver Detalhes do Video

```bash
curl -X GET http://localhost:8000/api/v1/videos/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

### 7. Verificar Status do Job

```bash
curl -X GET http://localhost:8000/api/v1/jobs/$JOB_ID/status \
  -H "Authorization: Bearer $TOKEN"
```

**Resposta (processando):**
```json
{
  "id": "uuid-do-job",
  "status": "PROCESSING",
  "progress": "extracting_frames",
  "message": "Processing video"
}
```

**Resposta (concluido):**
```json
{
  "id": "uuid-do-job",
  "status": "DONE",
  "progress": null,
  "message": "Ready for download"
}
```

### 8. Obter URL de Download

```bash
curl -X GET http://localhost:8000/api/v1/jobs/$JOB_ID/download \
  -H "Authorization: Bearer $TOKEN"
```

**Resposta:**
```json
{
  "download_url": "http://localhost:9000/fiapx-videos/...",
  "expires_in": 900,
  "filename": "video_frames.zip"
}
```

### 9. Baixar o ZIP

```bash
# Usando a URL retornada
curl -L "URL_DE_DOWNLOAD" -o frames.zip

# Ou em um comando so
curl -X GET http://localhost:8000/api/v1/jobs/$JOB_ID/download \
  -H "Authorization: Bearer $TOKEN" | jq -r '.download_url' | xargs curl -L -o frames.zip
```

### 10. Cancelar Video (se ainda nao processou)

```bash
curl -X DELETE http://localhost:8000/api/v1/videos/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

### 11. Renovar Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "SEU_REFRESH_TOKEN"
  }'
```

---

## Script de Teste Completo

```bash
#!/bin/bash
set -e

API_URL="http://localhost:8000/api/v1"
EMAIL="teste$(date +%s)@exemplo.com"
PASSWORD="MinhaSenh@123"

echo "=== 1. Registrando usuario ==="
curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\", \"name\": \"Teste\"}"
echo -e "\n"

echo "=== 2. Fazendo login ==="
RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
TOKEN=$(echo $RESPONSE | jq -r '.access_token')
echo "Token obtido: ${TOKEN:0:50}..."
echo -e "\n"

echo "=== 3. Verificando usuario ==="
curl -s -X GET "$API_URL/auth/me" \
  -H "Authorization: Bearer $TOKEN"
echo -e "\n"

echo "=== 4. Enviando video ==="
# Criar um video de teste (requer ffmpeg)
ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=1 -y /tmp/test.mp4 2>/dev/null

RESPONSE=$(curl -s -X POST "$API_URL/videos/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.mp4")
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job criado: $JOB_ID"
echo -e "\n"

echo "=== 5. Aguardando processamento ==="
for i in {1..30}; do
  STATUS=$(curl -s -X GET "$API_URL/jobs/$JOB_ID/status" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "DONE" ] || [ "$STATUS" = "FAILED" ]; then
    break
  fi
  sleep 2
done
echo -e "\n"

if [ "$STATUS" = "DONE" ]; then
  echo "=== 6. Obtendo URL de download ==="
  curl -s -X GET "$API_URL/jobs/$JOB_ID/download" \
    -H "Authorization: Bearer $TOKEN"
  echo -e "\n"
fi

echo "=== Teste concluido ==="
```

---

## Codigos de Status HTTP

| Codigo | Significado |
|--------|-------------|
| 200 | Sucesso |
| 201 | Criado com sucesso |
| 202 | Aceito (processamento em background) |
| 204 | Sucesso sem conteudo |
| 400 | Requisicao invalida |
| 401 | Nao autenticado |
| 403 | Acesso negado |
| 404 | Nao encontrado |
| 410 | Recurso expirado |
| 500 | Erro interno |

---

## Status do Job

| Status | Descricao |
|--------|-----------|
| UPLOADED | Video recebido |
| QUEUED | Aguardando processamento |
| PROCESSING | Extraindo frames |
| DONE | Concluido |
| FAILED | Erro |
| CANCELLED | Cancelado |
| EXPIRED | Expirado |
