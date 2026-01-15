#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage:
  sudo bash deploy/setup_domain_caddy_iptables.sh \\
    --domain example.com \\
    --backend-port 8000 \\
    --cert /etc/ssl/cloudflare/cert.pem \\
    --key /etc/ssl/cloudflare/key.pem \\
    [--no-www] \\
    [--no-cloudflare] \\
    [--no-iptables] \\
    [--caddyfile /etc/caddy/Caddyfile]

Keterangan:
  --domain         : Nama domain utama (misal: appgoldare.online)
  --backend-port   : Port backend Gunicorn/Django (default: 8000)
  --cert           : Path file sertifikat SSL
  --key            : Path file private key SSL
  --no-www         : Jangan tambahkan www.DOMAIN ke server block
  --no-cloudflare  : Jangan pakai header CF-Connecting-IP (untuk non-Cloudflare)
  --no-iptables    : Jangan menyentuh iptables (hanya edit Caddy)
  --caddyfile      : Lokasi Caddyfile (default: /etc/caddy/Caddyfile)

Contoh:
  sudo bash deploy/setup_domain_caddy_iptables.sh \\
    --domain appgoldare.online \\
    --backend-port 8000 \\
    --cert /etc/ssl/cloudflare/cert.pem \\
    --key /etc/ssl/cloudflare/key.pem
EOF
}

DOMAIN=""
BACKEND_PORT="8000"
CERT_PATH=""
KEY_PATH=""
CADDYFILE="/etc/caddy/Caddyfile"
WITH_WWW="yes"
WITH_CLOUDFLARE="yes"
WITH_IPTABLES="yes"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT="$2"
      shift 2
      ;;
    --cert)
      CERT_PATH="$2"
      shift 2
      ;;
    --key)
      KEY_PATH="$2"
      shift 2
      ;;
    --caddyfile)
      CADDYFILE="$2"
      shift 2
      ;;
    --no-www)
      WITH_WWW="no"
      shift 1
      ;;
    --no-cloudflare)
      WITH_CLOUDFLARE="no"
      shift 1
      ;;
    --no-iptables)
      WITH_IPTABLES="no"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumen tidak dikenal: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Skrip ini harus dijalankan sebagai root (sudo)."
  exit 1
fi

if [[ -z "$DOMAIN" ]] || [[ -z "$CERT_PATH" ]] || [[ -z "$KEY_PATH" ]]; then
  echo "Error: --domain, --cert, dan --key wajib diisi."
  usage
  exit 1
fi

if [[ ! -f "$CERT_PATH" ]]; then
  echo "Error: file sertifikat tidak ditemukan: $CERT_PATH"
  exit 1
fi

if [[ ! -f "$KEY_PATH" ]]; then
  echo "Error: file private key tidak ditemukan: $KEY_PATH"
  exit 1
fi

if [[ ! -f "$CADDYFILE" ]]; then
  echo "Error: Caddyfile tidak ditemukan di $CADDYFILE"
  exit 1
fi

SERVER_NAMES="$DOMAIN"
if [[ "$WITH_WWW" == "yes" ]]; then
  SERVER_NAMES="$DOMAIN www.$DOMAIN"
fi

BACKUP_PATH="${CADDYFILE}.bak-$(date +%Y%m%d%H%M%S)"
cp "$CADDYFILE" "$BACKUP_PATH"
echo "Backup Caddyfile dibuat di: $BACKUP_PATH"

if grep -qE "^[[:space:]]*${DOMAIN}( |$)" "$CADDYFILE"; then
  echo "Peringatan: blok untuk domain $DOMAIN sudah ada di $CADDYFILE."
  echo "Silakan cek manual untuk menghindari duplikasi."
else
  echo "Menambahkan blok Caddy untuk domain $SERVER_NAMES ..."

  {
    echo ""
    echo "$SERVER_NAMES {"
    echo "	tls $CERT_PATH $KEY_PATH"
    echo ""
    echo "	reverse_proxy 127.0.0.1:$BACKEND_PORT {"
    echo "		header_up Host {host}"
    echo "		header_up X-Forwarded-Proto https"
    if [[ "$WITH_CLOUDFLARE" == "yes" ]]; then
      echo "		header_up X-Real-IP {http.request.header.CF-Connecting-IP}"
    else
      echo "		header_up X-Real-IP {remote_host}"
    fi
    echo "	}"
    echo "}"
  } >> "$CADDYFILE"

  echo "Blok Caddy berhasil ditambahkan."
fi

if [[ "$WITH_IPTABLES" == "yes" ]]; then
  if command -v iptables >/dev/null 2>&1; then
    echo "Mengatur iptables untuk membuka port 80 dan 443 (TCP)..."
    iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || iptables -A INPUT -p tcp --dport 80 -j ACCEPT
    iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -A INPUT -p tcp --dport 443 -j ACCEPT
    echo "Rules iptables untuk port 80 dan 443 sudah di-set."
  else
    echo "Peringatan: iptables tidak ditemukan, bagian iptables dilewati."
  fi
else
  echo "Bagian iptables dilewati sesuai opsi --no-iptables."
fi

if command -v systemctl >/dev/null 2>&1; then
  echo "Reload service Caddy..."
  systemctl reload caddy
  echo "Reload Caddy selesai."
else
  echo "systemctl tidak ditemukan, silakan reload Caddy secara manual."
fi

echo "Selesai. Pastikan juga ALLOWED_HOSTS di .env sudah menyertakan: $DOMAIN dan www.$DOMAIN (jika digunakan)."

