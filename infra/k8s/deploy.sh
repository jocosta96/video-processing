#!/bin/bash
set -e

# =============================================================================
# FIAP X - Kubernetes Deploy Script
# =============================================================================
# Usage:
#   ./deploy.sh                    # Deploy all resources
#   ./deploy.sh build              # Build images and deploy
#   ./deploy.sh delete             # Delete all resources
#   ./deploy.sh status             # Show status of all resources
#   ./deploy.sh logs [service]     # Show logs for a service
#   ./deploy.sh port-forward       # Setup port-forwarding for local dev
#   ./deploy.sh migrate            # Run database migrations
#   ./deploy.sh restart [service]  # Restart a deployment
# =============================================================================

NAMESPACE="fiapx"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
K8S_DIR="$SCRIPT_DIR"

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Detect if running inside minikube
# =============================================================================
is_minikube() {
    command -v minikube &>/dev/null && minikube status &>/dev/null
}

# =============================================================================
# Build Docker Images (Dev only)
# =============================================================================
build_images() {
    log_info "Building Docker images for local development..."

    log_info "Building jocosta96/video-processing..."
    docker build -t jocosta96/video-processing:latest "$PROJECT_ROOT/fiapx-api"

    log_info "Building jocosta96/video-processing-worker..."
    docker build -t jocosta96/video-processing-worker:latest "$PROJECT_ROOT/fiapx-worker"

    log_info "Building jocosta96/video-processing-notifier..."
    docker build -t jocosta96/video-processing-notifier:latest "$PROJECT_ROOT/fiapx-notifier"

    log_info "All images built successfully!"

    # Load images into minikube if applicable
    if is_minikube; then
        log_info "Minikube detected. Loading images into minikube..."
        minikube image load jocosta96/video-processing:latest
        minikube image load jocosta96/video-processing-worker:latest
        minikube image load jocosta96/video-processing-notifier:latest
        log_info "Images loaded into minikube."
    fi
}

# =============================================================================
# Deploy to Kubernetes
# =============================================================================
deploy() {
    log_info "Deploying FIAP X to Kubernetes (using DockerHub images)..."

    # Apply base resources first
    log_info "Creating namespace and config..."
    kubectl apply -f "$K8S_DIR/00-namespace.yaml"
    kubectl apply -f "$K8S_DIR/01-secrets.yaml"
    kubectl apply -f "$K8S_DIR/02-configmaps.yaml"

    # Deploy infrastructure
    log_info "Deploying PostgreSQL..."
    kubectl apply -f "$K8S_DIR/postgres/"

    log_info "Deploying Redis..."
    kubectl apply -f "$K8S_DIR/redis/"

    log_info "Deploying RabbitMQ..."
    kubectl apply -f "$K8S_DIR/rabbitmq/"

    log_info "Deploying MinIO..."
    kubectl apply -f "$K8S_DIR/minio/pvc.yaml"
    kubectl apply -f "$K8S_DIR/minio/deployment.yaml"
    kubectl apply -f "$K8S_DIR/minio/service.yaml"

    log_info "Deploying Mailhog..."
    kubectl apply -f "$K8S_DIR/mailhog/"

    # Wait for infrastructure to be ready
    log_info "Waiting for infrastructure pods..."
    kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l app.kubernetes.io/name=postgres --timeout=120s 2>/dev/null || true
    kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l app.kubernetes.io/name=redis --timeout=60s 2>/dev/null || true
    kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l app.kubernetes.io/name=rabbitmq --timeout=120s 2>/dev/null || true
    kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l app.kubernetes.io/name=minio --timeout=60s 2>/dev/null || true

    # Run MinIO init job
    log_info "Initializing MinIO bucket..."
    kubectl delete job minio-init -n "$NAMESPACE" 2>/dev/null || true
    kubectl apply -f "$K8S_DIR/minio/init-job.yaml"

    # Deploy application services
    log_info "Deploying API..."
    kubectl apply -f "$K8S_DIR/api/deployment.yaml"
    kubectl apply -f "$K8S_DIR/api/service.yaml"
    kubectl apply -f "$K8S_DIR/api/hpa.yaml"
    kubectl apply -f "$K8S_DIR/api/ingress.yaml"

    log_info "Deploying Worker..."
    kubectl apply -f "$K8S_DIR/worker/"

    log_info "Deploying Notifier..."
    kubectl apply -f "$K8S_DIR/notifier/"

    # Wait for API to be ready before running migrations
    log_info "Waiting for API pods..."
    kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l app.kubernetes.io/name=api --timeout=120s 2>/dev/null || true

    # Run database migration
    log_info "Running database migrations..."
    kubectl delete job api-migration -n "$NAMESPACE" 2>/dev/null || true
    kubectl apply -f "$K8S_DIR/api/migration-job.yaml"
    kubectl -n "$NAMESPACE" wait --for=condition=complete job/api-migration --timeout=60s 2>/dev/null || log_warn "Migration job may still be running. Check with: kubectl logs job/api-migration -n $NAMESPACE"

    # Deploy monitoring
    log_info "Deploying Monitoring (Prometheus + Grafana)..."
    kubectl apply -f "$K8S_DIR/monitoring/"

    log_info ""
    log_info "========================================="
    log_info "  FIAP X deployed successfully!"
    log_info "========================================="
    log_info ""
    log_info "Run './deploy.sh status' to check the status"
    log_info "Run './deploy.sh port-forward' to access services locally"
    log_info "Run './deploy.sh logs api' to see API logs"
}

# =============================================================================
# Delete all resources
# =============================================================================
delete() {
    log_warn "Deleting all FIAP X resources..."
    kubectl delete namespace "$NAMESPACE" --ignore-not-found=true
    log_info "All resources deleted."
}

# =============================================================================
# Show status
# =============================================================================
status() {
    log_info "FIAP X Cluster Status"
    echo ""

    log_info "=== Pods ==="
    kubectl get pods -n "$NAMESPACE" -o wide 2>/dev/null || log_warn "Namespace $NAMESPACE not found"
    echo ""

    log_info "=== Services ==="
    kubectl get svc -n "$NAMESPACE" 2>/dev/null || true
    echo ""

    log_info "=== Deployments ==="
    kubectl get deployments -n "$NAMESPACE" 2>/dev/null || true
    echo ""

    log_info "=== HPA ==="
    kubectl get hpa -n "$NAMESPACE" 2>/dev/null || true
    echo ""

    log_info "=== PVC ==="
    kubectl get pvc -n "$NAMESPACE" 2>/dev/null || true
    echo ""

    log_info "=== Jobs ==="
    kubectl get jobs -n "$NAMESPACE" 2>/dev/null || true
    echo ""

    log_info "=== Ingress ==="
    kubectl get ingress -n "$NAMESPACE" 2>/dev/null || true
}

# =============================================================================
# Port-forward for local development
# =============================================================================
port_forward() {
    log_info "Setting up port-forwarding..."
    log_info ""
    log_info "Services will be available at:"
    log_info "  API:         http://localhost:8000/docs"
    log_info "  RabbitMQ:    http://localhost:15672   (guest/guest)"
    log_info "  MinIO:       http://localhost:9001    (minioadmin/minioadmin)"
    log_info "  Grafana:     http://localhost:3000    (admin/admin)"
    log_info "  Prometheus:  http://localhost:9090"
    log_info "  Mailhog:     http://localhost:8025"
    log_info ""
    log_info "Press Ctrl+C to stop all port-forwards"
    log_info ""

    # Start port-forwards in background
    kubectl port-forward svc/api 8000:8000 -n "$NAMESPACE" &
    kubectl port-forward svc/rabbitmq 15672:15672 -n "$NAMESPACE" &
    kubectl port-forward svc/minio 9000:9000 9001:9001 -n "$NAMESPACE" &
    kubectl port-forward svc/grafana 3000:3000 -n "$NAMESPACE" &
    kubectl port-forward svc/prometheus 9090:9090 -n "$NAMESPACE" &
    kubectl port-forward svc/mailhog 8025:8025 -n "$NAMESPACE" &

    # Wait for Ctrl+C
    trap "kill 0" EXIT
    wait
}

# =============================================================================
# Show logs
# =============================================================================
show_logs() {
    local service="${1:-api}"
    log_info "Showing logs for $service..."
    kubectl logs -f "deployment/$service" -n "$NAMESPACE" --tail=100 --all-containers=true
}

# =============================================================================
# Run database migrations
# =============================================================================
migrate() {
    log_info "Running database migrations..."
    kubectl delete job api-migration -n "$NAMESPACE" 2>/dev/null || true
    kubectl apply -f "$K8S_DIR/api/migration-job.yaml"
    kubectl -n "$NAMESPACE" wait --for=condition=complete job/api-migration --timeout=60s 2>/dev/null || true
    log_info "Migration logs:"
    kubectl logs job/api-migration -n "$NAMESPACE" --tail=20
}

# =============================================================================
# Restart a deployment
# =============================================================================
restart_service() {
    local service="${1:-api}"
    log_info "Restarting $service..."
    kubectl rollout restart "deployment/$service" -n "$NAMESPACE"
    kubectl rollout status "deployment/$service" -n "$NAMESPACE" --timeout=60s
    log_info "$service restarted successfully."
}

# =============================================================================
# Main
# =============================================================================
case "${1:-deploy}" in
    build)
        build_images
        deploy
        ;;
    deploy)
        deploy
        ;;
    delete)
        delete
        ;;
    status)
        status
        ;;
    logs)
        show_logs "$2"
        ;;
    migrate)
        migrate
        ;;
    restart)
        restart_service "$2"
        ;;
    port-forward|pf)
        port_forward
        ;;
    *)
        echo "Usage: $0 {build|deploy|delete|status|logs|migrate|restart|port-forward}"
        echo ""
        echo "Commands:"
        echo "  build          Build local images and deploy (dev only)"
        echo "  deploy         Deploy using DockerHub images (default)"
        echo "  delete         Delete all resources"
        echo "  status         Show status of all resources"
        echo "  logs [svc]     Show logs (default: api)"
        echo "  migrate        Run database migrations"
        echo "  restart [svc]  Restart a deployment (default: api)"
        echo "  port-forward   Setup port-forwarding for local dev"
        exit 1
        ;;
esac
