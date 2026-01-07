#!/bin/bash

################################################################################
# Bookmark Service Kubernetes Setup Script
#
# This script creates a fresh Kind cluster and deploys all services.
# It also connects the Kind cluster to the Docker Compose network so that
# Kubernetes pods can access PostgreSQL, Kafka, and Loki.
#
# Prerequisites:
#   - Docker Compose services must be running (docker compose up -d)
#   - kind-config.yaml must exist
#
# Usage:
#   ./k8s-setup.sh
#
################################################################################

set -e

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔧 Creating Kind cluster 'bookmarks-cluster'...${NC}"
if kind get clusters 2>/dev/null | grep -q "bookmarks-cluster"; then
    echo -e "${GREEN}✓${NC} Cluster already exists, skipping creation"
else
    kind create cluster --config kind-config.yaml --name bookmarks-cluster
    echo -e "${GREEN}✓${NC} Kind cluster created"
fi

echo -e "${BLUE}🔗 Connecting Kind cluster to Docker Compose network...${NC}"
# Check if Docker Compose network exists
if docker network ls | grep -q "bookmark_bookmark-network"; then
    # Check if already connected
    if docker inspect bookmarks-cluster-control-plane | grep -q "bookmark_bookmark-network"; then
        echo -e "${GREEN}✓${NC} Cluster already connected to Docker Compose network"
    else
        docker network connect bookmark_bookmark-network bookmarks-cluster-control-plane
        echo -e "${GREEN}✓${NC} Cluster connected to Docker Compose network"
    fi
else
    echo -e "${YELLOW}⚠${NC} Docker Compose network not found. Make sure to run 'docker compose up -d' first."
    echo -e "${YELLOW}⚠${NC} Continuing anyway, but pods may fail to connect to PostgreSQL/Kafka..."
fi

echo -e "${BLUE}🔨 Building Docker images...${NC}"
docker build -t bookmark-service:latest ./services/bookmark_service
docker build -t enrichment-service:latest ./services/enrichment_service
docker build -t validation-service:latest ./services/validation_service
echo -e "${GREEN}✓${NC} Docker images built"

echo -e "${BLUE}📦 Loading images into kind cluster...${NC}"
kind load docker-image bookmark-service:latest --name bookmarks-cluster
kind load docker-image enrichment-service:latest --name bookmarks-cluster
kind load docker-image validation-service:latest --name bookmarks-cluster
echo -e "${GREEN}✓${NC} Images loaded into cluster"

echo -e "${BLUE}🚀 Applying Kubernetes manifests...${NC}"
kubectl apply -f k8s/
echo -e "${GREEN}✓${NC} Manifests applied"

echo -e "${BLUE}⏳ Waiting for deployments to be ready...${NC}"
kubectl wait --for=condition=available --timeout=120s deployment --all

echo -e "${GREEN}✅ All services deployed successfully!${NC}"
echo ""
echo "📊 Current status:"
kubectl get pods
echo ""
echo "🌐 Access your services:"
echo "  - Bookmark Service: http://bookmark.test/api/v1/bookmarks/"
echo "  - Enrichment Service: NodePort 30801"
echo "  - Validation Service: NodePort 30802"
echo ""
echo "📝 Note: Make sure 'bookmark.test' is in your /etc/hosts pointing to 127.0.0.1"
echo ""
echo "🔍 Useful commands:"
echo "  - View logs: kubectl logs -f deployment/bookmark-service"
echo "  - Check status: kubectl get pods"
echo "  - Restart services: kubectl rollout restart deployment/bookmark-service"
