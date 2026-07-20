#!/usr/bin/env bash
# PartFinder — one-click launcher for macOS / Linux.
# Double-click this file (macOS) or run: ./run.command
set -e
cd "$(dirname "$0")"

PY=python3
command -v $PY >/dev/null 2>&1 || PY=python

echo "Installing dependencies (first run only)…"
$PY -m pip install -q -r requirements.txt

echo "Starting PartFinder…"
$PY server.py
