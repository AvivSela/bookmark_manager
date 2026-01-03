#!/bin/bash

set -e

echo "🔄 Restarting Kubernetes deployments..."
kubectl rollout restart deployment

echo "⏳ Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=120s deployment --all

echo "✅ All services restarted successfully!"
echo ""
echo "📊 Current status:"
kubectl get pods
