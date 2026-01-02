#!/bin/bash
# Test runner script for validation service
# Runs tests without Docker using the local virtual environment

set -a
source .env.test
set +a

exec .venv/bin/pytest "$@"
