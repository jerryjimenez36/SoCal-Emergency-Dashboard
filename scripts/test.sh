#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://127.0.0.1:5053/health | python3 -m json.tool
curl -fsS http://127.0.0.1:5053/emergency | python3 -m json.tool
curl -fsS 'http://127.0.0.1:5053/history?limit=10' | python3 -m json.tool
