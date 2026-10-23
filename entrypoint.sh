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

# Exit as soon as either child dies.  In particular, the in-app Pyrogram
# watchdog calls os._exit(1) if the session is stuck; the container must
# then stop so Docker's "restart: always" policy can bring it back.
set +e
wait -n $FLASK_PID $BOT_PID
STATUS=$?

echo "A child process exited (status $STATUS); shutting down..."
cleanup
exit $STATUS
