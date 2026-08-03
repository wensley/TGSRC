#!/bin/bash
set -e

echo "Starting Flask app on port 5000..."
flask run -h 0.0.0.0 -p 5000 &
FLASK_PID=$!

sleep 2

echo "Starting Telegram bot..."
python3 main.py &
BOT_PID=$!

cleanup() {
    echo "Shutting down..."
    kill $FLASK_PID $BOT_PID 2>/dev/null
    wait $FLASK_PID $BOT_PID 2>/dev/null
    echo "Shutdown complete."
}

trap cleanup SIGTERM SIGINT

wait $FLASK_PID $BOT_PID
