# Kubernetes - FIAP X

## Estrutura

```
k8s/
├── 00-namespace.yaml          # Namespace fiapx
├── 01-secrets.yaml            # Secrets (credenciais)
├── 02-configmaps.yaml         # ConfigMaps (configurações)
├── kustomization.yaml         # Kustomize para deploy unificado
├── deploy.sh                  # Script de deploy automatizado
│
├── api/                       # API Gateway (FastAPI)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml               # Auto-scaling (2-5 réplicas)
│   ├── ingress.yaml           # Ingress NGINX
│   └── migration-job.yaml     # Alembic migrations
│
├── worker/                    # Video Processing Worker
│   ├── deployment.yaml        # 2 réplicas iniciais
│   └── hpa.yaml               # Auto-scaling (2-8 réplicas)
│
├── notifier/                  # Notification Service
│   └── deployment.yaml
│
├── postgres/                  # PostgreSQL 15
│   ├── deployment.yaml
│   ├── service.yaml
│   └── pvc.yaml               # 5Gi storage
│
├── redis/                     # Redis 7
│   ├── deployment.yaml
│   ├── service.yaml
│   └── pvc.yaml               # 1Gi storage
│
├── rabbitmq/                  # RabbitMQ 3 (Management)
│   ├── deployment.yaml
│   ├── service.yaml
│   └── pvc.yaml               # 2Gi storage
│
├── minio/                     # MinIO (S3-compatible)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── pvc.yaml               # 10Gi storage
│   └── init-job.yaml          # Cria bucket fiapx-videos
│
├── mailhog/                   # MailHog (dev email)
│   ├── deployment.yaml
│   └── service.yaml
│
└── monitoring/                # Observabilidade
    ├── prometheus-configmap.yaml
    ├── prometheus-deployment.yaml
    ├── prometheus-service.yaml
    ├── grafana-pvc.yaml       # 2Gi storage
    ├── grafana-deployment.yaml
    └── grafana-service.yaml
```

## Pré-requisitos

- Kubernetes cluster (minikube, kind, EKS, GKE, etc.)
- `kubectl` configurado
- Docker images construídas

## Deploy Rápido

### Usando o script (recomendado)

```bash
# Dar permissão de execução
chmod +x infra/k8s/deploy.sh

# Build das imagens + deploy
./infra/k8s/deploy.sh build

# Apenas deploy (imagens já construídas)
./infra/k8s/deploy.sh deploy

# Ver status
./infra/k8s/deploy.sh status

# Port-forward para acesso local
./infra/k8s/deploy.sh port-forward

# Deletar tudo
./infra/k8s/deploy.sh delete
```

### Usando Kustomize

```bash
# Deploy tudo de uma vez
kubectl apply -k infra/k8s/

# Deletar tudo
kubectl delete -k infra/k8s/
```

### Deploy manual passo a passo

```bash
# 1. Criar namespace, secrets e config
kubectl apply -f infra/k8s/00-namespace.yaml
kubectl apply -f infra/k8s/01-secrets.yaml
kubectl apply -f infra/k8s/02-configmaps.yaml

# 2. Infraestrutura
kubectl apply -f infra/k8s/postgres/
kubectl apply -f infra/k8s/redis/
kubectl apply -f infra/k8s/rabbitmq/
kubectl apply -f infra/k8s/minio/
kubectl apply -f infra/k8s/mailhog/

# 3. Aplicação
kubectl apply -f infra/k8s/api/
kubectl apply -f infra/k8s/worker/
kubectl apply -f infra/k8s/notifier/

# 4. Monitoring
kubectl apply -f infra/k8s/monitoring/
```

## Build das Imagens Docker

```bash
# API
docker build -t fiapx-api:latest ./fiapx-api

# Worker
docker build -t fiapx-worker:latest ./fiapx-worker

# Notifier
docker build -t fiapx-notifier:latest ./fiapx-notifier
```

> Para uso com registry (ECR, GCR, Docker Hub), taguear e fazer push:
> ```bash
> docker tag fiapx-api:latest <registry>/fiapx-api:latest
> docker push <registry>/fiapx-api:latest
> ```
> E atualizar os `image:` nos deployments.

## Acesso aos Serviços (port-forward)

```bash
# API
kubectl port-forward svc/api 8000:8000 -n fiapx

# RabbitMQ Management
kubectl port-forward svc/rabbitmq 15672:15672 -n fiapx

# MinIO Console
kubectl port-forward svc/minio 9001:9001 -n fiapx

# Grafana
kubectl port-forward svc/grafana 3000:3000 -n fiapx

# Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n fiapx

# Mailhog
kubectl port-forward svc/mailhog 8025:8025 -n fiapx
```

## Serviços e Portas

| Serviço     | Porta Interna | URL Local (port-forward) | Credenciais            |
|-------------|---------------|--------------------------|------------------------|
| API         | 8000          | http://localhost:8000     | JWT Auth               |
| PostgreSQL  | 5432          | -                        | fiapx/fiapx            |
| Redis       | 6379          | -                        | -                      |
| RabbitMQ    | 5672/15672    | http://localhost:15672    | guest/guest            |
| MinIO       | 9000/9001     | http://localhost:9001     | minioadmin/minioadmin  |
| Mailhog     | 1025/8025     | http://localhost:8025     | -                      |
| Prometheus  | 9090          | http://localhost:9090     | -                      |
| Grafana     | 3000          | http://localhost:3000     | admin/admin            |

## Auto-scaling

- **API**: 2-5 réplicas (CPU > 70% ou Memory > 80%)
- **Worker**: 2-8 réplicas (CPU > 60% ou Memory > 75%)

## Produção

Para produção, considere:

1. **Secrets**: Use um gerenciador como AWS Secrets Manager, Vault, ou Sealed Secrets
2. **Images**: Use tags específicas em vez de `:latest`
3. **Registry**: Push para um registry privado (ECR, GCR)
4. **Storage**: Use StorageClass com provisioner adequado
5. **Ingress**: Configure TLS/HTTPS com cert-manager
6. **Network Policies**: Restrinja comunicação entre pods
7. **Resource Limits**: Ajuste com base nas métricas reais
8. **PostgreSQL**: Considere operadores como CloudNativePG ou serviço gerenciado (RDS)
9. **RabbitMQ**: Considere o RabbitMQ Cluster Operator
10. **MinIO**: Use S3 nativo em cloud (AWS S3, GCS)
