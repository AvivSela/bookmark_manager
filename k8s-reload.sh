#!/bin/bash

set -e

echo "🔨 Building Docker images..."
docker build -t bookmark-service:latest ./services/bookmark_service
docker build -t enrichment-service:latest ./services/enrichment_service
docker build -t validation-service:latest ./services/validation_service

echo "📦 Loading images into kind cluster..."
kind load docker-image bookmark-service:latest --name bookmarks-cluster
kind load docker-image enrichment-service:latest --name bookmarks-cluster
kind load docker-image validation-service:latest --name bookmarks-cluster

echo "🗑️  Deleting existing Kubernetes resources..."
kubectl delete -f k8s/ --ignore-not-found=true

echo "🚀 Applying Kubernetes manifests..."
kubectl apply -f k8s/

echo "⏳ Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment --all

echo "✅ All services reloaded successfully!"
echo ""
echo "📊 Current status:"
kubectl get pods
