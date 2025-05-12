#!/bin/bash

# Find all vscode-server PIDs
PIDS=$(ps aux | grep  ipykernel_launcher | awk '{print $2}')

if [ -z "$PIDS" ]; then
  echo "No jupyter serverrs processes found."
  exit 0
fi

echo "Killing the following jupyter-server processes: $PIDS"

# Graceful kill
kill $PIDS

# Wait for processes to terminate
sleep 3

# Force kill any remaining
for PID in $PIDS; do
  if kill -0 "$PID" 2>/dev/null; then
    echo "Process $PID still running, sending SIGKILL..."
    kill -9 "$PID"
  fi
done
