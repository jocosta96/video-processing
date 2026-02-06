# Arquitetura do Sistema de Processamento de Vídeos — FIAP X

> **Versão**: 1.1  
> **Data**: 2026-02-05  
> **Stack de Implementação**: Python  
> **Atualizado**: Reflete implementação real do sistema

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Requisitos](#2-requisitos)
3. [Arquitetura C4](#3-arquitetura-c4)
4. [Microsserviços e Responsabilidades](#4-microsserviços-e-responsabilidades)
5. [Fluxos Principais](#5-fluxos-principais)
6. [Mensageria](#6-mensageria)
7. [Modelo de Dados](#7-modelo-de-dados)
8. [Armazenamento de Arquivos](#8-armazenamento-de-arquivos)
9. [Segurança](#9-segurança)
10. [Observabilidade](#10-observabilidade)
11. [Testes e Qualidade](#11-testes-e-qualidade)
12. [CI/CD](#12-cicd)
13. [Scripts e Infra](#13-scripts-e-infra)
14. [Decisões Arquiteturais](#14-decisões-arquiteturais)
15. [Entregáveis e Checklist](#15-entregáveis-e-checklist)
16. [Comandos Úteis](#apêndice-a-comandos-úteis)

---

## 1. Visão Geral

### 1.1 Contexto do Problema

O sistema FIAP X permite que usuários enviem vídeos para processamento, onde frames são extraídos (1 frame/segundo via FFmpeg) e compactados em um arquivo `.zip` para download posterior.

### 1.2 Solução Implementada

A arquitetura em Python implementa:
- **Microsserviços** com responsabilidades bem definidas
- **Processamento assíncrono** via filas de mensagens (RabbitMQ)
- **Autenticação** por usuário/senha (JWT)
- **Persistência** de estado e metadados (PostgreSQL)
- **Escalável horizontalmente** via Docker Compose
- **Resiliente** com retry manual e filas duráveis

### 1.3 Componentes Principais

- **fiapx-api**: FastAPI - Autenticação, upload, status, download
- **fiapx-worker**: Worker Python + Pika - Processamento de vídeos com FFmpeg
- **fiapx-notifier**: Worker Python + Pika - Notificações por e-mail
- **PostgreSQL**: Banco de dados relacional
- **RabbitMQ**: Message broker para filas assíncronas
- **Redis**: Cache (configurado, uso limitado)
- **MinIO**: Object storage S3-compatible

### 1.4 Decisões de Stack

| Componente | Escolha Principal | Alternativa | Justificativa |
|------------|------------------|-------------|---------------|
| Framework HTTP | **FastAPI** | Flask | Async nativo, OpenAPI automático, validação com Pydantic |
| Worker/Fila | **Pika + RabbitMQ** | Celery + RabbitMQ | Implementação direta com pika, retry manual, controle granular |
| Banco de Dados | **PostgreSQL** | MySQL | JSONB, constraints robustas, escalabilidade |
| Cache | **Redis** | Memcached | Estruturas avançadas, pub/sub, locks distribuídos |
| Storage | **MinIO** (S3-compatible) | Local/GCS | S3 API, self-hosted, URLs assinadas |
| Infra | **Docker Compose** | - | Ambiente de desenvolvimento e staging |

### 1.5 Status de Implementação

> **Última atualização**: 2026-02-05

| Componente | Status | Notas |
|------------|--------|-------|
| **API Gateway** | ✅ Implementado | FastAPI com auth JWT, routers completos |
| **Video Worker** | ✅ Implementado | Pika consumer, FFmpeg, retry manual |
| **Notifier** | ✅ Implementado | Pika consumer, SMTP (MailHog) |
| **PostgreSQL** | ✅ Implementado | Alembic migrations, models User/Job |
| **RabbitMQ** | ✅ Implementado | Filas video.process, notification.send |
| **MinIO** | ✅ Implementado | S3-compatible storage, presigned URLs |
| **Redis** | ⚠️ Configurado | Infraestrutura pronta, uso limitado |
| **Autenticação** | ⚠️ Parcial | JWT implementado |
| **Testes** | ⚠️ Parcial | Unit + Integration implementados |
| **Observabilidade** | ⚠️ Básico | Logs estruturados |

---

## 2. Requisitos

### 2.1 Requisitos Funcionais

| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF01 | Usuário deve se cadastrar e autenticar com usuário/senha | Alta |
| RF02 | Usuário pode enviar um ou mais vídeos para processamento | Alta |
| RF03 | Sistema deve processar múltiplos vídeos simultaneamente | Alta |
| RF04 | Sistema não deve perder requisições em picos de carga | Alta |
| RF05 | Usuário pode visualizar lista de seus vídeos e status | Alta |
| RF06 | Usuário pode baixar o ZIP de frames após processamento | Alta |
| RF07 | Usuário é notificado por e-mail em caso de erro | Média |

### 2.2 Requisitos Não Funcionais

| ID | Requisito | Especificação |
|----|-----------|---------------|
| RNF01 | Disponibilidade | 99.5% uptime |
| RNF02 | Latência de upload | < 5s para vídeos até 100MB |
| RNF03 | Throughput | 100 uploads simultâneos sem perda |
| RNF04 | Tamanho máximo de vídeo | 500MB (configurável) |
| RNF05 | Retenção de arquivos | 7 dias (configurável) |
| RNF06 | Formatos suportados | .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm |
| RNF07 | Tempo máximo de processamento | 30 minutos por vídeo |
| RNF08 | Segurança | HTTPS, JWT, URLs assinadas |

---

## 3. Arquitetura C4

### 3.1 C4 — Context Diagram

```mermaid
C4Context
    title Sistema de Processamento de Vídeos - FIAP X (Context)

    Person(user, "Usuário/Investidor", "Envia vídeos e baixa frames processados")

    System(fiapx, "FIAP X", "Sistema de processamento de vídeos para extração de frames")

    System_Ext(email, "Serviço de E-mail", "SendGrid/SES - Notificações")
    System_Ext(storage, "Object Storage", "MinIO/S3 - Armazenamento de arquivos")

    Rel(user, fiapx, "Envia vídeos, consulta status, baixa ZIPs", "HTTPS/REST")
    Rel(fiapx, email, "Envia notificações de erro", "SMTP/API")
    Rel(fiapx, storage, "Armazena vídeos e ZIPs", "S3 API")
```

### 3.2 C4 — Container Diagram

```mermaid
C4Container
    title Sistema de Processamento de Vídeos - FIAP X (Containers)

    Person(user, "Usuário", "")

    Container_Boundary(fiapx, "FIAP X System") {
        Container(api, "API Gateway", "Python/FastAPI", "Autenticação, upload, status, download")
        Container(worker, "Video Worker", "Python/Pika", "Processa vídeos, extrai frames, gera ZIP")
        Container(notifier, "Notification Service", "Python/Pika", "Envia e-mails de erro/sucesso")

        ContainerDb(postgres, "PostgreSQL", "Database", "Usuários, jobs, metadados")
        ContainerDb(redis, "Redis", "Cache/Broker", "Cache, sessões, message broker")
        Container(rabbitmq, "RabbitMQ", "Message Broker", "Filas de processamento")
    }

    System_Ext(minio, "MinIO", "Object Storage")
    System_Ext(email, "E-mail Service", "SendGrid/SES")

    Rel(user, api, "REST API", "HTTPS")
    Rel(api, postgres, "Lê/Escreve", "TCP")
    Rel(api, redis, "Cache/Sessão", "TCP")
    Rel(api, rabbitmq, "Publica jobs", "AMQP")
    Rel(api, minio, "Upload vídeos", "S3 API")

    Rel(worker, rabbitmq, "Consome jobs", "AMQP")
    Rel(worker, postgres, "Atualiza status", "TCP")
    Rel(worker, minio, "Lê vídeo, grava ZIP", "S3 API")
    Rel(worker, redis, "Locks, dedup", "TCP")

    Rel(notifier, rabbitmq, "Consome eventos", "AMQP")
    Rel(notifier, email, "Envia e-mail", "SMTP/API")
    Rel(notifier, postgres, "Lê dados usuário", "TCP")
```

### 3.3 Diagrama de Componentes Simplificado

```mermaid
flowchart TB
    subgraph "Frontend/Client"
        UI[Web UI / CLI]
    end

    subgraph "API Layer"
        APIGW[API Gateway<br/>FastAPI]
        AUTH[Auth Module<br/>JWT/OAuth2]
    end

    subgraph "Message Layer"
        RMQ[(RabbitMQ)]
        REDIS[(Redis)]
    end

    subgraph "Worker Layer"
        W1[Worker 1]
        W2[Worker 2]
        WN[Worker N]
    end

    subgraph "Storage Layer"
        PG[(PostgreSQL)]
        MINIO[(MinIO/S3)]
    end

    subgraph "Notification"
        NOTIF[Notifier Service]
        EMAIL[Email Provider]
    end

    UI --> APIGW
    APIGW --> AUTH
    APIGW --> RMQ
    APIGW --> PG
    APIGW --> MINIO
    APIGW --> REDIS

    RMQ --> W1
    RMQ --> W2
    RMQ --> WN

    W1 --> PG
    W1 --> MINIO
    W1 --> REDIS
    W2 --> PG
    W2 --> MINIO
    WN --> PG
    WN --> MINIO

    RMQ --> NOTIF
    NOTIF --> EMAIL
    NOTIF --> PG
```

---

## 4. Microsserviços e Responsabilidades

### 4.1 Tabela de Serviços

| Serviço | Responsabilidade | DB | Eventos Publicados | Eventos Consumidos | APIs |
|---------|-----------------|----|--------------------|-------------------|------|
| **api-gateway** | Autenticação, upload de vídeos, consulta de status, geração de URLs de download | PostgreSQL (users, jobs) | `job.created`, `job.cancelled` | - | REST: `/auth/*`, `/videos/*`, `/jobs/*` |
| **video-worker** | Processar vídeos, extrair frames, criar ZIP, atualizar status | PostgreSQL (jobs) | `job.completed`, `job.failed` | `job.created` | - |
| **notification-service** | Enviar e-mails de notificação | PostgreSQL (read-only: users) | - | `job.completed`, `job.failed` | - |

### 4.2 Detalhamento dos Serviços

#### 4.2.1 API Gateway (api-gateway)

**Tecnologias**: FastAPI, SQLAlchemy, Pydantic, python-jose (JWT)

**Responsabilidades**:
- Autenticação e autorização (JWT)
- Validação de uploads (tamanho, formato)
- Persistência de metadados do job
- Publicação de eventos na fila
- Geração de URLs assinadas para download

**Endpoints**:

```
POST   /auth/register       - Cadastro de usuário
POST   /auth/login          - Login (retorna JWT)
POST   /auth/refresh        - Refresh token
GET    /auth/me             - Dados do usuário logado

POST   /videos/upload       - Upload de vídeo (multipart)
GET    /videos              - Lista vídeos do usuário
GET    /videos/{id}         - Detalhes de um vídeo/job
DELETE /videos/{id}         - Cancela job pendente

GET    /jobs/{id}/download  - URL assinada para download do ZIP
GET    /jobs/{id}/status    - Status detalhado do job
```

#### 4.2.2 Video Worker (video-worker)

**Tecnologias**: Pika (RabbitMQ client), FFmpeg (subprocess), boto3 (S3)

**Responsabilidades**:
- Consumir jobs da fila `video.process`
- Baixar vídeo do MinIO
- Extrair frames com FFmpeg (`fps=1`)
- Criar arquivo ZIP
- Upload do ZIP para MinIO
- Atualizar status no banco
- Publicar evento de conclusão/erro

**Configurações**:
- Concorrência: 2 workers (configurável via WORKER_CONCURRENCY)
- Timeout: 30 minutos por task
- Retry: 3 tentativas com backoff exponencial manual
- Prefetch: 1 (evita starvation)
- Implementação: Consumidor direto com pika.BlockingConnection

#### 4.2.3 Notification Service (notification-service)

**Tecnologias**: Pika (RabbitMQ client), SMTP (MailHog em dev)

**Responsabilidades**:
- Consumir eventos da fila `notification.send`
- Enviar e-mail de notificação ao usuário
- Templates de e-mail para sucesso/erro

**Implementação**: Consumidor direto com pika.BlockingConnection

---

## 5. Fluxos Principais

### 5.1 Fluxo de Upload e Processamento

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuário
    participant API as API Gateway
    participant PG as PostgreSQL
    participant S3 as MinIO
    participant RMQ as RabbitMQ
    participant W as Video Worker
    participant N as Notifier

    U->>API: POST /auth/login
    API->>PG: Valida credenciais
    PG-->>API: OK
    API-->>U: JWT Token

    U->>API: POST /videos/upload (video.mp4)
    API->>API: Valida arquivo (tamanho, formato)
    API->>S3: Upload vídeo (videos/{user_id}/{job_id}/input.mp4)
    S3-->>API: OK
    API->>PG: INSERT job (status=UPLOADED)
    PG-->>API: job_id
    API->>RMQ: Publish job.created {job_id, user_id, video_path}
    API-->>U: 202 Accepted {job_id, status: QUEUED}

    RMQ->>W: Consume job.created
    W->>PG: UPDATE job SET status=PROCESSING
    W->>S3: Download vídeo
    S3-->>W: video bytes
    W->>W: FFmpeg: extrair frames (fps=1)
    W->>W: Criar ZIP com frames
    W->>S3: Upload ZIP (videos/{user_id}/{job_id}/output.zip)
    S3-->>W: OK
    W->>PG: UPDATE job SET status=DONE, zip_path=...
    W->>RMQ: Publish job.completed {job_id, user_id}

    RMQ->>N: Consume job.completed
    N->>PG: SELECT user email
    N->>N: Enviar e-mail de sucesso

    U->>API: GET /videos/{job_id}
    API->>PG: SELECT job
    PG-->>API: job (status=DONE)
    API-->>U: {status: DONE, download_available: true}

    U->>API: GET /jobs/{job_id}/download
    API->>S3: Generate presigned URL
    S3-->>API: signed URL (15min TTL)
    API-->>U: {download_url: "https://..."}
    U->>S3: GET signed URL
    S3-->>U: output.zip
```

### 5.2 Fluxo de Erro e Retry

```mermaid
sequenceDiagram
    autonumber
    participant RMQ as RabbitMQ
    participant W as Video Worker
    participant PG as PostgreSQL
    participant DLQ as Dead Letter Queue
    participant N as Notifier

    RMQ->>W: Consume job.created
    W->>PG: UPDATE status=PROCESSING
    W->>W: FFmpeg falha (codec não suportado)
    W-->>RMQ: NACK + requeue (attempt 1/3)

    Note over RMQ,W: Backoff: 30s

    RMQ->>W: Retry 2
    W->>W: FFmpeg falha novamente
    W-->>RMQ: NACK + requeue (attempt 2/3)

    Note over RMQ,W: Backoff: 60s

    RMQ->>W: Retry 3 (final)
    W->>W: FFmpeg falha novamente
    W->>PG: UPDATE status=FAILED, error_message=...
    W->>RMQ: Publish job.failed
    W-->>RMQ: ACK (remove from queue)
    RMQ->>DLQ: Move to DLQ (for analysis)

    RMQ->>N: Consume job.failed
    N->>N: Enviar e-mail de erro ao usuário
```

### 5.3 State Machine de Status do Job

```mermaid
stateDiagram-v2
    [*] --> UPLOADED: Vídeo recebido

    UPLOADED --> QUEUED: Job publicado na fila

    QUEUED --> PROCESSING: Worker inicia processamento

    PROCESSING --> DONE: Processamento concluído
    PROCESSING --> FAILED: Erro após 3 tentativas
    PROCESSING --> PROCESSING: Retry (tentativa < 3)

    QUEUED --> CANCELLED: Usuário cancela

    DONE --> EXPIRED: TTL expirado (7 dias)
    FAILED --> [*]: Fim (notificação enviada)
    CANCELLED --> [*]: Fim
    EXPIRED --> [*]: Arquivos removidos

    note right of PROCESSING
        Tentativas: máx 3
        Backoff: 30s, 60s, 120s
    end note

    note right of DONE
        ZIP disponível
        URL assinada válida por 15min
    end note
```

### 5.4 Transições de Status

| Estado Atual | Evento | Novo Estado | Ação |
|--------------|--------|-------------|------|
| - | Upload recebido | UPLOADED | Salva vídeo no S3 |
| UPLOADED | Job publicado | QUEUED | Mensagem na fila |
| QUEUED | Worker pega job | PROCESSING | Inicia extração |
| PROCESSING | Sucesso | DONE | ZIP criado |
| PROCESSING | Erro (retry < 3) | PROCESSING | Requeue com backoff |
| PROCESSING | Erro (retry = 3) | FAILED | Move para DLQ, notifica |
| QUEUED | Usuário cancela | CANCELLED | Remove da fila |
| DONE | TTL expirado | EXPIRED | Remove arquivos |

---

## 6. Mensageria

### 6.1 Arquitetura de Filas

```mermaid
flowchart LR
    subgraph "Exchanges"
        EX_VIDEO[video.exchange<br/>type: direct]
        EX_NOTIFY[notification.exchange<br/>type: fanout]
    end

    subgraph "Queues"
        Q_PROCESS[video.process<br/>durable, lazy]
        Q_DLQ[video.process.dlq<br/>durable]
        Q_NOTIFY[notification.send<br/>durable]
    end

    subgraph "Consumers"
        W1[Worker 1]
        W2[Worker 2]
        N1[Notifier]
    end

    EX_VIDEO -->|routing_key: process| Q_PROCESS
    Q_PROCESS -->|on reject/expire| Q_DLQ
    EX_NOTIFY --> Q_NOTIFY

    Q_PROCESS --> W1
    Q_PROCESS --> W2
    Q_NOTIFY --> N1
```

### 6.2 Configuração das Filas

#### Queue: `video.process`

```yaml
name: video.process
durable: true
arguments:
  x-dead-letter-exchange: ""
  x-dead-letter-routing-key: video.process.dlq
  x-message-ttl: 1800000  # 30 min (evita jobs órfãos)
  x-queue-mode: lazy      # Persiste no disco (memória baixa)
```

#### Queue: `video.process.dlq`

```yaml
name: video.process.dlq
durable: true
arguments:
  x-message-ttl: 604800000  # 7 dias para análise
```

#### Queue: `notification.send`

```yaml
name: notification.send
durable: true
arguments:
  x-message-ttl: 86400000  # 24h
```

### 6.3 Formato das Mensagens

#### Evento: `job.created`

```json
{
  "event_type": "job.created",
  "event_id": "uuid-v4",
  "timestamp": "2026-02-03T10:30:00Z",
  "payload": {
    "job_id": "uuid-v4",
    "user_id": "uuid-v4",
    "video_path": "videos/user123/job456/input.mp4",
    "video_size_bytes": 52428800,
    "video_format": "mp4",
    "created_at": "2026-02-03T10:30:00Z"
  },
  "metadata": {
    "retry_count": 0,
    "max_retries": 3,
    "idempotency_key": "job_uuid-v4"
  }
}
```

#### Evento: `job.completed`

```json
{
  "event_type": "job.completed",
  "event_id": "uuid-v4",
  "timestamp": "2026-02-03T10:35:00Z",
  "payload": {
    "job_id": "uuid-v4",
    "user_id": "uuid-v4",
    "zip_path": "videos/user123/job456/output.zip",
    "frame_count": 120,
    "processing_time_seconds": 45,
    "zip_size_bytes": 15728640
  }
}
```

#### Evento: `job.failed`

```json
{
  "event_type": "job.failed",
  "event_id": "uuid-v4",
  "timestamp": "2026-02-03T10:35:00Z",
  "payload": {
    "job_id": "uuid-v4",
    "user_id": "uuid-v4",
    "error_code": "FFMPEG_CODEC_ERROR",
    "error_message": "Unsupported codec: hevc",
    "retry_count": 3
  }
}
```

### 6.4 Retry e Backoff

**Implementação Atual**: Retry manual com pika

```python
# Worker implementation (fiapx-worker/src/main.py)
def on_message(channel, method, properties, body):
    message = json.loads(body)
    job_id = message["job_id"]
    
    # Get retry count from headers
    retry_count = 0
    if properties.headers and "x-retry-count" in properties.headers:
        retry_count = properties.headers["x-retry-count"]
    
    result = process_video(job_id, video_path, retry_count)
    
    if result.get("status") == "failed" and result.get("retry"):
        # Retry with exponential backoff
        retry_count += 1
        delay = settings.retry_delay * (2 ** (retry_count - 1))
        time.sleep(min(delay, 300))  # max 5 min
        
        # Republish with retry count
        channel.basic_publish(
            exchange="",
            routing_key="video.process",
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                headers={"x-retry-count": retry_count}
            )
        )
    
    channel.basic_ack(delivery_tag=method.delivery_tag)
```

### 6.5 Idempotência e Deduplicação

**Implementação Atual**: Controle via status no banco de dados PostgreSQL

O sistema garante idempotência através do status do job armazenado no PostgreSQL. Jobs não são reprocessados se já estiverem em status PROCESSING ou DONE.

### 6.6 Backpressure

**Controle de carga no worker**:

```python
# RabbitMQ config (fiapx-worker/src/main.py)
channel.basic_qos(prefetch_count=1)  # Pega 1 task por vez

# Concurrency via environment
WORKER_CONCURRENCY=2  # Configurável via variável de ambiente

# ACK após processamento completo
channel.basic_ack(delivery_tag=method.delivery_tag)
```

---

## 7. Modelo de Dados

### 7.1 Diagrama ER

```mermaid
erDiagram
    USERS ||--o{ JOBS : "has many"
    JOBS ||--o| JOB_EVENTS : "has many"

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string name
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    JOBS {
        uuid id PK
        uuid user_id FK
        string status
        string video_path
        string zip_path
        bigint video_size_bytes
        string video_format
        int frame_count
        bigint zip_size_bytes
        int processing_time_seconds
        string error_code
        text error_message
        int retry_count
        timestamp created_at
        timestamp started_at
        timestamp completed_at
        timestamp expires_at
    }

    JOB_EVENTS {
        uuid id PK
        uuid job_id FK
        string event_type
        string old_status
        string new_status
        jsonb metadata
        timestamp created_at
    }
```

### 7.2 DDL Simplificado

**Implementado**: Via Alembic migrations em `fiapx-api/alembic/versions/001_initial.py`

```sql
-- Implementado via Alembic
-- Extensão para UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enum de status
CREATE TYPE job_status AS ENUM (
    'UPLOADED', 'QUEUED', 'PROCESSING', 'DONE', 'FAILED', 'CANCELLED', 'EXPIRED'
);

-- Tabela de usuários
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- Tabela de jobs
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status job_status NOT NULL DEFAULT 'UPLOADED',

    -- Input
    video_path VARCHAR(512) NOT NULL,
    video_size_bytes BIGINT NOT NULL,
    video_format VARCHAR(10) NOT NULL,

    -- Output
    zip_path VARCHAR(512),
    frame_count INTEGER,
    zip_size_bytes BIGINT,
    processing_time_seconds INTEGER,

    -- Error handling
    error_code VARCHAR(50),
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT chk_status_consistency CHECK (
        (status IN ('DONE') AND zip_path IS NOT NULL) OR
        (status NOT IN ('DONE'))
    )
);

-- Índices para queries comuns
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX idx_jobs_expires_at ON jobs(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- Tabela de eventos (audit log)
CREATE TABLE job_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    old_status job_status,
    new_status job_status,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_events_job_id ON job_events(job_id);
CREATE INDEX idx_job_events_created_at ON job_events(created_at);

-- Trigger para audit log automático
CREATE OR REPLACE FUNCTION log_job_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO job_events (job_id, event_type, old_status, new_status)
        VALUES (NEW.id, 'STATUS_CHANGE', OLD.status, NEW.status);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_job_status_change
    AFTER UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION log_job_status_change();

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
```

### 7.3 Redis

**Status**: Infraestrutura configurada no Docker Compose

Redis está disponível na infraestrutura mas atualmente não é utilizado pelos serviços. O controle de estado é feito via PostgreSQL.

---

## 8. Armazenamento de Arquivos

### 8.1 Estrutura de Diretórios no MinIO/S3

```
bucket: fiapx-videos
├── videos/
│   └── {user_id}/
│       └── {job_id}/
│           ├── input.{ext}     # Vídeo original
│           └── output.zip      # ZIP com frames
└── temp/
    └── {job_id}/
        └── frames/            # Frames temporários (durante processamento)
```

### 8.2 Políticas de Bucket

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "fiapx-api"},
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::fiapx-videos/videos/*"
    },
    {
      "Effect": "Allow",
      "Principal": {"Service": "fiapx-worker"},
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::fiapx-videos/*"
    }
  ]
}
```

### 8.3 Lifecycle Rules

```yaml
# Expiração automática de arquivos
lifecycle_rules:
  - id: expire-old-files
    status: Enabled
    filter:
      prefix: videos/
    expiration:
      days: 7

  - id: cleanup-temp
    status: Enabled
    filter:
      prefix: temp/
    expiration:
      days: 1
```

### 8.4 URLs Assinadas para Download

```python
from datetime import timedelta
import boto3

def generate_download_url(zip_path: str, expires_in: int = 900) -> str:
    """Gera URL assinada válida por 15 minutos (default)"""
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY
    )

    url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.MINIO_BUCKET,
            'Key': zip_path,
            'ResponseContentDisposition': f'attachment; filename="frames.zip"'
        },
        ExpiresIn=expires_in
    )
    return url
```

---

## 9. Segurança

### 9.1 Autenticação (AuthN)

**Método**: JWT (JSON Web Tokens)

**Implementado**: Access tokens com JWT

**Estrutura do JWT**:
```python
{
  "sub": "user_uuid",       # User ID
  "email": "user@example.com",
  "iat": 1706954400,        # Issued at
  "exp": 1706958000,        # Expires (1h)
}
```

Algoritmo: HS256  
Expiração: 1 hora  
Armazenamento: Validado em memória, sem persistência em Redis

**Fluxo de Autenticação Implementado**:

1. Login: `POST /auth/login` com email/password
2. API valida credenciais no PostgreSQL
3. Retorna JWT access token (válido por 1h)
4. Cliente usa token no header `Authorization: Bearer {token}`
5. API valida JWT em cada request

### 9.2 Autorização (AuthZ)

**Modelo**: Ownership-based (usuário só acessa seus próprios recursos)

**Implementado**: ✅

```python
# Implementado em fiapx-api/src/api/dependencies.py
async def verify_job_ownership(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return job

# Uso nos routers
@router.get("/jobs/{job_id}")
async def get_job(job: Job = Depends(verify_job_ownership)):
    return job
```

### 9.3 Segurança de Senhas

```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Custo computacional
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

**Requisitos de senha**:
- Mínimo 8 caracteres
- Pelo menos 1 letra maiúscula
- Pelo menos 1 número
- Pelo menos 1 caractere especial

### 9.4 Download Seguro

1. **URL assinada**: Válida por 15 minutos
2. **Verificação de ownership**: Apenas dono do job pode gerar URL
3. **Rate limiting**: Máximo 10 downloads/minuto por usuário
4. **Audit log**: Registra todos os downloads

```python
@router.get("/jobs/{job_id}/download")
@rate_limit(max_requests=10, window_seconds=60)
async def get_download_url(
    job: Job = Depends(verify_job_ownership)
):
    if job.status != JobStatus.DONE:
        raise HTTPException(400, "Job not completed")

    if job.expires_at and job.expires_at < datetime.utcnow():
        raise HTTPException(410, "File expired")

    url = generate_download_url(job.zip_path)

    # Audit log
    logger.info(f"Download URL generated", extra={
        "job_id": str(job.id),
        "user_id": str(job.user_id),
        "action": "download_url_generated"
    })

    return {"download_url": url, "expires_in": 900}
```

### 9.5 Proteções Adicionais

| Proteção | Status | Implementação |
|----------|--------|---------------|
| CORS | ✅ Implementado | Whitelist de origens configurável |
| Input Validation | ✅ Implementado | Pydantic schemas em todos os endpoints |
| SQL Injection | ✅ Protegido | SQLAlchemy ORM (parametrized queries) |
| File Upload | ✅ Implementado | Validação de extensão e tamanho |
| XSS | ✅ Implementado | Headers básicos (X-Content-Type-Options, X-Frame-Options) |

### 9.6 Headers de Segurança

```python
# FastAPI middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

---

## 10. Observabilidade

### 10.1 Arquitetura de Observabilidade

**Status**: Implementação básica (logs estruturados)

**Implementado**:
- ✅ Logs estruturados com structlog (JSON)
- ✅ Health check endpoints
- ✅ Logging em todos os serviços

```mermaid
flowchart TB
    subgraph "Applications (Implementado)"
        API[API Gateway]
        W[Workers]
        N[Notifier]
    end

    subgraph "Observability (Básica)"
        LOGS[Structured Logs<br/>structlog]
        HEALTH[Health Checks]
    end

    API -->|logs JSON| LOGS
    W -->|logs JSON| LOGS
    N -->|logs JSON| LOGS
    
    API --> HEALTH
```

### 10.2 Logs Estruturados

**Formato**: JSON estruturado com contexto

```python
import structlog

logger = structlog.get_logger()

# Configuração
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

# Uso
logger.info(
    "job_processing_started",
    job_id=str(job.id),
    user_id=str(job.user_id),
    video_size=job.video_size_bytes,
    trace_id=get_current_trace_id()
)
```

**Exemplo de log**:
```json
{
  "timestamp": "2026-02-03T10:30:00.123Z",
  "level": "info",
  "event": "job_processing_started",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "video_size": 52428800,
  "trace_id": "abc123def456",
  "service": "video-worker",
  "environment": "production"
}
```

### 10.3 Métricas

**Implementação Atual**: 
- Logs estruturados com structlog (JSON)
- Métricas via queries no PostgreSQL
- Job status e timestamps no banco de dados
- Monitoramento de filas via RabbitMQ Management UI

### 10.4 Tracing Distribuído

Correlação via `job_id` nos logs estruturados de todos os serviços. Cada log contém o `job_id` permitindo rastrear o fluxo completo através dos microsserviços.

### 10.5 Monitoramento

**Ferramentas Disponíveis**:
- RabbitMQ Management UI (http://localhost:15672) - Filas, mensagens, consumers
- MinIO Console (http://localhost:9001) - Arquivos, buckets
- Logs estruturados em JSON para debugging
- Health checks via endpoint `/health`
- PostgreSQL para queries de status e métricas de jobs

---

## 11. Testes e Qualidade

### 11.1 Pirâmide de Testes

```mermaid
graph TB
    subgraph "Pirâmide de Testes"
        E2E[E2E Tests<br/>5%]
        INT[Integration Tests<br/>25%]
        UNIT[Unit Tests<br/>70%]
    end

    E2E --> INT --> UNIT

    style UNIT fill:#90EE90
    style INT fill:#FFD700
    style E2E fill:#FF6B6B
```

### 11.2 Estratégia de Testes

| Tipo | Cobertura | Ferramentas | Foco |
|------|-----------|-------------|------|
| **Unit** | 70% | pytest, pytest-mock | Lógica de negócio, validações, transformações |
| **Integration** | 25% | pytest, testcontainers | APIs, banco, filas, S3 |
| **E2E** | 5% | pytest, httpx | Fluxos completos (upload→download) |
| **Contract** | - | Pact | Contratos entre serviços |

### 11.3 Testes Unitários

```python
# tests/unit/test_video_processor.py
import pytest
from unittest.mock import Mock, patch
from app.services.video_processor import VideoProcessor

class TestVideoProcessor:

    def test_validate_video_format_accepts_mp4(self):
        processor = VideoProcessor()
        assert processor.validate_format("video.mp4") is True

    def test_validate_video_format_rejects_exe(self):
        processor = VideoProcessor()
        assert processor.validate_format("malware.exe") is False

    def test_validate_video_size_within_limit(self):
        processor = VideoProcessor(max_size_bytes=500_000_000)
        assert processor.validate_size(100_000_000) is True

    def test_validate_video_size_exceeds_limit(self):
        processor = VideoProcessor(max_size_bytes=500_000_000)
        assert processor.validate_size(600_000_000) is False

    @patch('subprocess.run')
    def test_extract_frames_calls_ffmpeg_correctly(self, mock_run):
        mock_run.return_value = Mock(returncode=0)
        processor = VideoProcessor()

        processor.extract_frames("/tmp/video.mp4", "/tmp/output")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ffmpeg" in args
        assert "-vf" in args
        assert "fps=1" in args
```

### 11.4 Testes de Integração

```python
# tests/integration/test_api_jobs.py
import pytest
from httpx import AsyncClient
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:15") as pg:
        yield pg.get_connection_url()

@pytest.fixture(scope="module")
def redis():
    with RedisContainer("redis:7") as r:
        yield r.get_connection_url()

@pytest.mark.asyncio
async def test_upload_video_creates_job(
    client: AsyncClient,
    auth_headers: dict,
    sample_video: bytes
):
    response = await client.post(
        "/videos/upload",
        files={"file": ("test.mp4", sample_video, "video/mp4")},
        headers=auth_headers
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "QUEUED"

@pytest.mark.asyncio
async def test_get_jobs_returns_user_jobs_only(
    client: AsyncClient,
    auth_headers_user1: dict,
    auth_headers_user2: dict,
    create_job_for_user1: str
):
    # User 1 vê seu job
    response = await client.get("/videos", headers=auth_headers_user1)
    assert response.status_code == 200
    assert len(response.json()) == 1

    # User 2 não vê job do User 1
    response = await client.get("/videos", headers=auth_headers_user2)
    assert response.status_code == 200
    assert len(response.json()) == 0
```





### 11.5 Critérios de Qualidade

| Critério | Meta | Status |
|----------|------|--------|
| Cobertura de código | ≥ 80% | ✅ Atingido |
| Testes passando | 100% | ✅ Todos passando |
| Estrutura de testes | Unit + Integration | ✅ Implementado |

**Comandos de validação**:

```bash
# Executar testes com coverage
cd fiapx-api && pytest --cov=src --cov-report=html
cd fiapx-worker && pytest --cov=src --cov-report=html
cd fiapx-notifier && pytest --cov=src --cov-report=html

# Ver relatório de coverage
open htmlcov/index.html
```

---

## 12. Build e Deploy

### 12.1 Build Local

**Implementação Atual**:
- ✅ Testes locais com pytest
- ✅ Docker build manual por serviço
- ✅ Docker Compose para ambiente completo

### 12.2 Testes e Build

```bash
# Testes por serviço
cd fiapx-api && pytest tests/
cd fiapx-worker && pytest tests/
cd fiapx-notifier && pytest tests/

# Build de imagens
cd fiapx-api && docker build -t fiapx-api .
cd fiapx-worker && docker build -t fiapx-worker .
cd fiapx-notifier && docker build -t fiapx-notifier .

# Ou build via compose
cd infra && docker-compose build
```

### 12.3 Ambiente

**Ambiente Local**: Docker Compose (`http://localhost:8000`)

```bash
cd infra
docker-compose up -d

# Acessar serviços
curl http://localhost:8000/health    # API
open http://localhost:15672          # RabbitMQ UI
open http://localhost:9001           # MinIO Console
open http://localhost:8025           # MailHog (email)
```

---

## 13. Scripts e Infra

### 13.1 Docker Compose (Dev/Staging)

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://fiapx:fiapx@postgres:5432/fiapx
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - MINIO_ENDPOINT=http://minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_BUCKET=fiapx-videos
      - JWT_SECRET=${JWT_SECRET:-dev-secret-change-in-prod}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: worker
    environment:
      - DATABASE_URL=postgresql://fiapx:fiapx@postgres:5432/fiapx
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - MINIO_ENDPOINT=http://minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - MINIO_BUCKET=fiapx-videos
    depends_on:
      - api
    deploy:
      replicas: 2

  notifier:
    build:
      context: .
      dockerfile: Dockerfile
      target: notifier
    environment:
      - DATABASE_URL=postgresql://fiapx:fiapx@postgres:5432/fiapx
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - SMTP_HOST=${SMTP_HOST:-mailhog}
      - SMTP_PORT=${SMTP_PORT:-1025}
    depends_on:
      - rabbitmq

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=fiapx
      - POSTGRES_PASSWORD=fiapx
      - POSTGRES_DB=fiapx
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fiapx"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      - RABBITMQ_DEFAULT_USER=guest
      - RABBITMQ_DEFAULT_PASS=guest
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_running"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3

  minio-init:
    image: minio/mc
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set myminio http://minio:9000 minioadmin minioadmin;
      mc mb myminio/fiapx-videos --ignore-existing;
      mc anonymous set download myminio/fiapx-videos;
      exit 0;
      "

  # Observability
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

  # Dev tools
  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"
      - "8025:8025"

volumes:
  postgres_data:
  minio_data:
  grafana_data:
```

### 13.2 Dockerfile Multi-stage

**Implementação Atual**: Dockerfiles separados por serviço

- `fiapx-api/Dockerfile` - API Gateway
- `fiapx-worker/Dockerfile` - Video Worker
- `fiapx-notifier/Dockerfile` - Notification Service

Cada serviço tem seu próprio Dockerfile e requirements.txt.

```dockerfile
# Exemplo: fiapx-api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# Exemplo: fiapx-worker/Dockerfile  
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "src/main.py"]
```


                name: fiapx-secrets
            - configMapRef:
                name: fiapx-config
---
# k8s/worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fiapx-worker
spec:
  replicas: 4
  selector:
    matchLabels:
      app: fiapx-worker
  template:
    spec:
      containers:
        - name: worker
          image: ghcr.io/fiapx/worker:latest
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2000m"
---
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fiapx-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fiapx-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: External
      external:
        metric:
          name: rabbitmq_queue_messages
          selector:
            matchLabels:
              queue: video.process
        target:
          type: AverageValue
          averageValue: "10"
```

### 13.4 Script de Inicialização

```bash
#!/bin/bash
# scripts/setup.sh

set -e

echo "=== FIAP X Setup ==="

# Verifica dependências
command -v docker >/dev/null 2>&1 || { echo "Docker não encontrado"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose não encontrado"; exit 1; }

# Cria .env se não existir
if [ ! -f .env ]; then
    echo "Criando .env..."
    cp .env.example .env
    # Gera JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
fi

# Sobe containers
echo "Iniciando containers..."
docker-compose up -d

# Aguarda serviços
echo "Aguardando serviços..."
sleep 10

# Roda migrations
echo "Executando migrations..."
docker-compose exec api alembic upgrade head

# Cria bucket no MinIO
echo "Configurando MinIO..."
docker-compose exec minio-init mc mb myminio/fiapx-videos --ignore-existing || true

echo "=== Setup completo! ==="
echo "API: http://localhost:8000"
echo "RabbitMQ: http://localhost:15672"
echo "MinIO: http://localhost:9001"
echo "Grafana: http://localhost:3000"
echo "Mailhog: http://localhost:8025"
```

---

## 14. Decisões Arquiteturais

### 14.1 Escolhas Técnicas Principais

| Decisão | Escolha | Alternativa | Justificativa |
|---------|---------|-------------|---------------|
| **Framework Web** | FastAPI | Flask, Django | Performance async, OpenAPI automático |
| **Message Broker** | RabbitMQ | Redis, Kafka | Maturidade, durabilidade de mensagens |
| **Client de Fila** | Pika direto | Celery | Controle granular, simplicidade |
| **Banco de Dados** | PostgreSQL | MySQL, MongoDB | JSONB, constraints, estabilidade |
| **Object Storage** | MinIO | S3, Local | S3-compatible, self-hosted |
| **Containerização** | Docker Compose | K8s direto | Simplicidade em dev/staging |

### 14.2 Trade-offs

**Pika direto vs Celery**:
- ✅ Vantagens: Controle total do retry, sem overhead, código mais simples
- ❌ Desvantagens: Retry manual, sem monitoring automático (Flower)

**Microsserviços separados vs Monolito**:
- ✅ Vantagens: Escalabilidade independente, isolamento de falhas
- ❌ Desvantagens: Maior complexidade operacional, debugging distribuído

**Processamento Síncrono vs Assíncrono**:
- ✅ Escolha: Assíncrono com filas
- ✅ Vantagens: Resiliência, não perde requests em picos
- ❌ Desvantagens: Latência maior (não é real-time)

### 14.3 Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação Implementada |
|-------|--------------|---------|------------------------|
| FFmpeg timeout em vídeos grandes | Média | Alto | Timeout de 30min, limite de 500MB |
| Pico de uploads sobrecarrega workers | Alta | Médio | Filas duráveis, prefetch=1, retry com backoff |
| Perda de mensagens na fila | Baixa | Alto | Filas duráveis, ACK após processamento completo |
| Jobs órfãos (worker morre) | Média | Médio | Status persistido no PostgreSQL |
| Disco cheio (arquivos temporários) | Média | Alto | Limpeza após processar, armazenamento no MinIO |

### 14.4 Limitações Conhecidas

1. **Retry manual** → Implementado no worker, sem Celery
2. **Sem refresh token** → Access token de 1h, requer novo login
3. **Sem rate limiting** → Proteção básica via validação de tamanho
4. **Upload único** → Vídeos enviados inteiros (limite 500MB)
5. **Testes manuais** → Testes automatizados unit + integration
6. **Deploy manual** → Via Docker Compose
7. **Monitoramento básico** → Logs + RabbitMQ UI + PostgreSQL queries

---

## 15. Riscos e Decisões (Trade-offs)

### 15.1 Decisões Arquiteturais

| Decisão | Opção A | Opção B | Escolha | Justificativa |
|---------|---------|---------|---------|---------------|
| **Framework HTTP** | FastAPI | Flask | FastAPI | Async nativo, OpenAPI, Pydantic |
| **Message Broker** | RabbitMQ | Kafka | RabbitMQ | Mais simples, suficiente para volume esperado, DLQ nativo |
| **Task Queue** | Celery | Arq | Celery | Maturidade, monitoring (Flower), retry policies |
| **Banco** | PostgreSQL | MySQL | PostgreSQL | JSONB, better constraints, ecosystem |
| **Storage** | MinIO | Local FS | MinIO | S3 API, presigned URLs, escalável |
| **Infra (dev)** | Compose | K8s local | Compose | Simplicidade para desenvolvimento |
| **Infra (prod)** | K8s | ECS | K8s | HPA, portabilidade, comunidade |

### 15.2 Riscos Técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| FFmpeg timeout em vídeos grandes | Média | Alto | Timeout configurável, limite de tamanho |
| Pico de uploads sobrecarrega workers | Alta | Médio | Fila durable, backpressure, HPA |
| Perda de mensagens na fila | Baixa | Alto | Fila durable, acks_late, DLQ |
| Vazamento de URLs assinadas | Baixa | Médio | TTL curto (15min), audit log |
| Falha de notificação de erro | Média | Baixo | Retry de notificações, fallback para polling |

### 15.3 Débitos Técnicos Aceitos

1. **Frontend embutido** → Separar em projeto dedicado (React/Vue) no futuro
2. **Sem rate limiting por IP** → Adicionar quando necessário
3. **Sem suporte a chunks** → Para vídeos muito grandes, implementar upload multipart
4. **Sem webhook de callback** → Usuário precisa fazer polling ou esperar e-mail

---

## 16. Entregáveis e Checklist do Vídeo

### 16.1 Entregáveis

| # | Entregável | Descrição | Localização | Status |
|---|------------|-----------|-------------|--------|
| 1 | **Documentação de Arquitetura** | Este documento | `ARCHITECTURE.md` | ✅ |
| 2 | **Repositório GitHub** | Código fonte Python | Local (fiap-tc/) | ✅ |
| 3 | **Docker Compose** | Setup completo para dev | `infra/docker-compose.yml` | ✅ |
| 4 | **Dockerfile** | Dockerfiles por serviço | `fiapx-*/Dockerfile` | ✅ |
| 5 | **Scripts de Setup** | Automação de ambiente | `infra/scripts/setup.sh` | ✅ |
| 6 | **Testes** | Unit, integration | `*/tests/` | ⚠️ |

| 8 | **Migrations** | Alembic migrations | `fiapx-api/alembic/` | ✅ |

| 10 | **Collection Postman** | Exemplos de API | `fiapx-api/docs/` | ✅ |

### 16.2 Estrutura do Repositório (Implementada)

```
fiap-tc/
├── ARCHITECTURE.md
├── Makefile
├── pytest.ini
├── README.md
├── fiapx-api/
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial.py
│   ├── alembic.ini
│   ├── API_TESTING.md
│   ├── Dockerfile
│   ├── docs/
│   │   └── postman_collection.json
│   ├── htmlcov/          # Coverage reports
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── main.py
│   │   │   ├── dependencies.py
│   │   │   ├── routers/
│   │   │   │   ├── auth.py
│   │   │   │   ├── health.py
│   │   │   │   ├── jobs.py
│   │   │   │   └── videos.py
│   │   │   └── schemas/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── messaging.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── base.py
│   │   │   ├── job.py
│   │   │   ├── types.py
│   │   │   └── user.py
│   │   └── services/
│   │       └── storage.py
│   └── tests/
│       ├── conftest.py
│       ├── integration/
│       │   ├── test_auth.py
│       │   ├── test_jobs.py
│       │   └── test_videos.py
│       └── unit/
│           ├── test_schemas.py
│           └── test_security.py
├── fiapx-worker/
│   ├── Dockerfile
│   ├── htmlcov/
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── src/
│   │   ├── main.py         # Pika consumer
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── models/
│   │   ├── services/
│   │   └── tasks/
│   │       └── video.py
│   └── tests/
│       ├── integration/
│       └── unit/
│           ├── test_video_processor.py
│           └── test_video_tasks.py
├── fiapx-notifier/
│   ├── Dockerfile
│   ├── htmlcov/
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-test.txt
│   ├── src/
│   │   ├── main.py         # Pika consumer
│   │   ├── core/
│   │   ├── models/
│   │   └── tasks/
│   │       └── notification.py
│   └── tests/
│       └── unit/
│           └── test_notification.py
├── infra/
│   ├── config/
│   ├── docker-compose.yml
│   ├── docker-compose.test.yml
│   ├── k8s/
│   └── scripts/
│       └── setup.sh
└── tests/
    └── conftest.py
```

### 16.3 Checklist do Vídeo (10 minutos)

```markdown
## Roteiro do Vídeo de Apresentação

### Introdução (1 min)
- [ ] Apresentação do grupo
- [ ] Contexto do problema (processamento de vídeos)
- [ ] Objetivo: Sistema escalável com microsserviços

### Arquitetura (3 min)
- [ ] Mostrar diagrama C4 Context
- [ ] Mostrar diagrama C4 Container
- [ ] Explicar escolha de tecnologias (FastAPI, Pika, RabbitMQ)
- [ ] Destacar: filas para escalabilidade, retry manual, workers independentes

### Demo Funcional (4 min)
- [ ] Subir ambiente: `cd infra && docker-compose up -d`
- [ ] Fazer cadastro/login (Postman ou curl)
- [ ] Upload de vídeo
- [ ] Mostrar job na fila (RabbitMQ UI: http://localhost:15672)
- [ ] Acompanhar status (QUEUED → PROCESSING → DONE)
- [ ] Download do ZIP via URL assinada
- [ ] Mostrar frames extraídos

### Qualidade e Testes (1.5 min)
- [ ] Mostrar testes rodando: `pytest --cov`
- [ ] Mostrar cobertura de código (htmlcov/)
- [ ] Mencionar estrutura de testes (unit + integration)
- [ ] Destacar uso de testcontainers

### Fechamento (0.5 min)
- [ ] Recapitular: microsserviços, filas, autenticação
- [ ] Pontos de melhoria: CI/CD, Prometheus, K8s
- [ ] Agradecer

### Dicas
- Gravar em resolução 1080p
- Usar zoom em código/diagramas
- Preparar ambiente antes (containers já rodando)
- Ter vídeo de teste pronto (< 30s para demo rápida)
```

### 16.4 Critérios de Avaliação

| Critério | Peso | Como Demonstrar |
|----------|------|-----------------|
| Arquitetura escalável | 25% | Diagrama + explicação de filas/workers |
| Zero perda em picos | 20% | DLQ, retry, persistência da fila |
| Segurança (auth) | 15% | Login funcional, JWT, URL assinada |
| Status por usuário | 15% | Listagem de jobs, state machine |
| Qualidade (testes) | 15% | Cobertura, pipeline verde |
| Documentação | 10% | Este documento, README, comments |

---

## Apêndice A: Comandos Úteis

```bash
# Desenvolvimento
cd infra
docker-compose up -d                    # Sobe ambiente
docker-compose logs -f api              # Logs da API
docker-compose logs -f worker           # Logs do Worker

# Migrations
cd fiapx-api
alembic upgrade head                    # Aplica migrations
alembic revision --autogenerate -m "msg" # Cria nova migration

# Testes
cd fiapx-api
pytest tests/unit -v                    # Unit tests da API
pytest tests/integration -v             # Integration tests da API
pytest --cov=src --cov-report=html      # Coverage report

cd ../fiapx-worker
pytest tests/unit -v                    # Unit tests do Worker

cd ../fiapx-notifier
pytest tests/unit -v                    # Unit tests do Notifier

# RabbitMQ
# Management UI: http://localhost:15672 (guest/guest)

# MinIO
# Console: http://localhost:9001 (minioadmin/minioadmin)
# Endpoint: http://localhost:9000

# MailHog (dev email)
# Web UI: http://localhost:8025

# Monitoramento
curl http://localhost:8000/health       # Health check
curl http://localhost:8000/docs         # OpenAPI docs
```

---

## Apêndice B: Variáveis de Ambiente

```bash
# .env.example

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Database
DATABASE_URL=postgresql://fiapx:fiapx@localhost:5432/fiapx

# Redis
REDIS_URL=redis://localhost:6379

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672

# MinIO/S3
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=fiapx-videos

# Security
JWT_SECRET=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Email
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=noreply@fiapx.com

# Limits
MAX_VIDEO_SIZE_MB=500
VIDEO_RETENTION_DAYS=7
PRESIGNED_URL_EXPIRY_SECONDS=900
```

---

*Documento atualizado em 2026-02-05 | FIAP X - Sistema de Processamento de Vídeos*
