#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
ENV_FILE="$APP_DIR/.env"
PID_FILE="$APP_DIR/run/gunicorn.pid"
LOG_DIR="$APP_DIR/logs"
RUN_DIR="$APP_DIR/run"

# Detect gunicorn binary: prefer venv, fallback to system or python -m
detect_gunicorn_bin() {
  # Prefer venv gunicorn only if it actually runs
  if [[ -x "$APP_DIR/venv/bin/gunicorn" ]]; then
    if "$APP_DIR/venv/bin/gunicorn" --version >/dev/null 2>&1; then
      echo "$APP_DIR/venv/bin/gunicorn"
      return 0
    fi
  fi
  if command -v gunicorn >/dev/null 2>&1; then
    command -v gunicorn
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3 -m gunicorn"
    return 0
  fi
  return 1
}

GUNICORN_BIN="$(detect_gunicorn_bin || true)"
if [[ -z "$GUNICORN_BIN" ]]; then
  echo "Error: Gunicorn binary not found. Install it or create a venv at $APP_DIR/venv."
  exit 1
fi

GUNICORN_CMD="$GUNICORN_BIN --chdir $APP_DIR -c $APP_DIR/deploy/gunicorn.conf.py config.wsgi:application"

# Pastikan direktori ada dan dimiliki oleh www-data agar bisa tulis
mkdir -p "$LOG_DIR" "$RUN_DIR"
chown -R www-data:www-data "$LOG_DIR" "$RUN_DIR" || true
chmod 0750 "$LOG_DIR" "$RUN_DIR" || true

source "$APP_DIR/venv/bin/activate" || true
# Load environment variables from .env safely
if [[ -f "$ENV_FILE" ]]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

start() {
  echo "Starting Gunicorn..."
  # Increase file descriptors for many keepalive connections
  ulimit -n 4096 || true
  # Jalankan dalam shell www-data supaya redireksi log dilakukan oleh www-data
  # serta file PID dibuat di dalam RUN_DIR dengan izin yang benar
  echo "Using Gunicorn binary: $GUNICORN_BIN" >> "$LOG_DIR/gunicorn.out"
  if id -u www-data >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo -u www-data bash -lc "umask 007; nohup $GUNICORN_CMD --pid '$PID_FILE' >> '$LOG_DIR/gunicorn.out' 2>> '$LOG_DIR/gunicorn.err' &"
  else
    bash -lc "umask 007; nohup $GUNICORN_CMD --pid '$PID_FILE' >> '$LOG_DIR/gunicorn.out' 2>> '$LOG_DIR/gunicorn.err' &"
  fi
  # Wait for PID file and port listen
  for i in {1..50}; do
    if [[ -f "$PID_FILE" ]]; then
      # Confirm port 8000 listening
      if ss -ltnp 2>/dev/null | grep -q "127.0.0.1:8000"; then
        echo "Gunicorn started with PID $(cat "$PID_FILE") and listening on 127.0.0.1:8000"
        return 0
      fi
    fi
    sleep 0.2
  done
  echo "Failed to verify Gunicorn start; recent error logs:"
  tail -n 100 "$LOG_DIR/gunicorn.err" || true
  return 1
}

stop() {
  if [[ -f "$PID_FILE" ]]; then
    kill -TERM "$(cat "$PID_FILE")" && rm -f "$PID_FILE"
    echo "Gunicorn stopped"
  else
    echo "No PID file; Gunicorn not running?"
  fi
}

restart() { stop || true; sleep 1; start; }

status() {
  if [[ -f "$PID_FILE" ]] && ps -p "$(cat "$PID_FILE")" > /dev/null; then
    echo "Gunicorn running (PID $(cat "$PID_FILE"))"
  else
    echo "Gunicorn not running"
  fi
}

logs() {
  tail -n 200 -f "$LOG_DIR/gunicorn.out" "$LOG_DIR/gunicorn.err"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  logs) logs ;;
  *) echo "Usage: $0 {start|stop|restart|status|logs}"; exit 1 ;;
 esac
