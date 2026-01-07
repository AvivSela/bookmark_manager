#!/bin/bash

################################################################################
# Bookmark Service Environment Cleanup Script
#
# This script removes all Docker and Kubernetes resources to enable a fresh
# environment recreation.
#
# What it does:
#   - Deletes Kind cluster (bookmarks-cluster)
#   - Stops and removes Docker Compose containers
#   - Removes all data volumes (PostgreSQL, Kafka, monitoring)
#   - Removes built service Docker images
#   - Cleans up networks
#
# Usage:
#   ./cleanup.sh
#
# After cleanup, recreate environment with:
#   1. docker-compose up -d          # Start Docker Compose stack
#   2. ./k8s-reload.sh               # Create Kind cluster and deploy K8s
#
################################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Confirmation prompt
confirm_cleanup() {
    print_header "Bookmark Service Environment Cleanup"
    echo "This script will:"
    echo "  1. Delete Kind cluster 'bookmarks-cluster'"
    echo "  2. Stop and remove all Docker Compose containers"
    echo "  3. Remove all data volumes (PostgreSQL, Kafka, monitoring)"
    echo "  4. Remove built service images (bookmark-service, enrichment-service, validation-service)"
    echo "  5. Clean up networks"
    echo ""
    print_warning "This is DESTRUCTIVE and will delete all data!"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Cleanup cancelled."
        exit 0
    fi
}

# Step 1: Kubernetes Cleanup
cleanup_kubernetes() {
    print_header "Step 1: Cleaning up Kubernetes (Kind)"

    # Check if kind is installed
    if ! command -v kind &> /dev/null; then
        print_warning "kind command not found, skipping Kubernetes cleanup"
        return
    fi

    # Check if cluster exists
    if kind get clusters 2>/dev/null | grep -q "bookmarks-cluster"; then
        print_info "Deleting Kind cluster 'bookmarks-cluster'..."
        if kind delete cluster --name bookmarks-cluster; then
            print_success "Kind cluster deleted successfully"
        else
            print_error "Failed to delete Kind cluster"
            return 1
        fi
    else
        print_warning "Kind cluster 'bookmarks-cluster' not found, skipping"
    fi
}

# Step 2: Docker Compose Cleanup
cleanup_docker_compose() {
    print_header "Step 2: Cleaning up Docker Compose"

    # Check if docker-compose.yml exists
    if [[ ! -f "docker-compose.yml" ]]; then
        print_warning "docker-compose.yml not found in current directory, skipping"
        return
    fi

    print_info "Stopping and removing Docker Compose containers..."
    if docker compose down 2>/dev/null; then
        print_success "Docker Compose containers stopped and removed"
    else
        print_warning "Docker Compose down failed or no containers were running"
    fi

    print_info "Removing Docker Compose volumes..."
    local volumes=(
        "bookmark_postgres_data"
        "bookmark_kafka_data"
        "bookmark_pgadmin_data"
        "bookmark_prometheus_data"
        "bookmark_loki_data"
        "bookmark_grafana_data"
    )

    local removed_count=0
    for volume in "${volumes[@]}"; do
        if docker volume ls -q | grep -q "^${volume}$"; then
            if docker volume rm "$volume" 2>/dev/null; then
                print_success "Removed volume: $volume"
                ((removed_count++))
            else
                print_warning "Failed to remove volume: $volume (may be in use)"
            fi
        fi
    done

    if [[ $removed_count -eq 0 ]]; then
        print_warning "No volumes were removed (they may not exist)"
    else
        print_success "Removed $removed_count volume(s)"
    fi

    # Remove network
    print_info "Removing Docker network..."
    if docker network ls | grep -q "bookmark-network"; then
        if docker network rm bookmark-network 2>/dev/null; then
            print_success "Removed network: bookmark-network"
        else
            print_warning "Failed to remove network: bookmark-network (may be in use)"
        fi
    fi
}

# Step 3: Docker Image Cleanup
cleanup_docker_images() {
    print_header "Step 3: Cleaning up Docker Images"

    local images=(
        "bookmark-service"
        "enrichment-service"
        "validation-service"
    )

    local removed_count=0
    for image in "${images[@]}"; do
        # Remove all tags of this image
        if docker images --format "{{.Repository}}" | grep -q "^${image}$"; then
            print_info "Removing image: $image"
            if docker rmi -f $(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^${image}:") 2>/dev/null; then
                print_success "Removed image: $image"
                ((removed_count++))
            else
                print_warning "Failed to remove image: $image"
            fi
        fi
    done

    if [[ $removed_count -eq 0 ]]; then
        print_warning "No service images found to remove"
    else
        print_success "Removed $removed_count service image(s)"
    fi

    # Clean up dangling images
    print_info "Removing dangling images..."
    if docker image prune -f >/dev/null 2>&1; then
        print_success "Removed dangling images"
    fi
}

# Step 4: Verification
verify_cleanup() {
    print_header "Step 4: Verification"

    # Check Kind clusters
    if command -v kind &> /dev/null; then
        print_info "Remaining Kind clusters:"
        local clusters=$(kind get clusters 2>/dev/null)
        if [[ -z "$clusters" ]]; then
            print_success "No Kind clusters found"
        else
            echo "$clusters"
        fi
    fi

    # Check Docker containers
    print_info "Remaining Docker containers:"
    local containers=$(docker ps -a --format "table {{.Names}}\t{{.Status}}" 2>/dev/null)
    if [[ $(echo "$containers" | wc -l) -le 1 ]]; then
        print_success "No Docker containers found"
    else
        echo "$containers"
    fi

    # Check volumes
    print_info "Checking for bookmark-related volumes:"
    local bookmark_volumes=$(docker volume ls --format "{{.Name}}" | grep -i "bookmark" 2>/dev/null || true)
    if [[ -z "$bookmark_volumes" ]]; then
        print_success "No bookmark-related volumes found"
    else
        print_warning "Found remaining volumes:"
        echo "$bookmark_volumes"
    fi

    # Check service images
    print_info "Checking for service images:"
    local service_images=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "(bookmark-service|enrichment-service|validation-service)" 2>/dev/null || true)
    if [[ -z "$service_images" ]]; then
        print_success "No service images found"
    else
        print_warning "Found remaining service images:"
        echo "$service_images"
    fi
}

# Main execution
main() {
    confirm_cleanup

    cleanup_kubernetes
    cleanup_docker_compose
    cleanup_docker_images
    verify_cleanup

    print_header "Cleanup Complete!"
    echo "To recreate your environment, run:"
    echo "  1. docker-compose up -d          # Start Docker Compose stack"
    echo "  2. ./k8s-reload.sh               # Create Kind cluster and deploy K8s"
    echo ""
}

# Run main function
main
