#!/bin/bash

# Chess Server Starter Script
# Usage: ./start_server.sh [optional: --debug for verbose mode]

DEBUG=false
if [ "$1" = "--debug" ]; then
  DEBUG=true
fi

# Update STOCKFISH_PATH if needed (edit this line)
STOCKFISH_PATH="/Users/abdel_latrache/stockfish/stockfish"  # Change to your path

echo "Starting Chess Server..."
echo "Stockfish path: $STOCKFISH_PATH"

if [ "$DEBUG" = true ]; then
  python3 app.py --debug
else
 python3 app.py
fi

echo "Server stopped. Run with --debug for verbose logs."