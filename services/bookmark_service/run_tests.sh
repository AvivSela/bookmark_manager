#!/bin/bash
# Test runner script for bookmark service
# Runs tests without Docker using SQLite in-memory database

set -a
source .env.test
set +a

exec .venv/bin/pytest "$@"
