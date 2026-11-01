#!/usr/bin/env bash
# Despliegue en Ubuntu (EC2). Ejecutar DENTRO de la carpeta del proyecto: bash deploy/desplegar_ec2.sh
set -euo pipefail

DB_NAME=dulce_arte
DB_USER=dulce_user
DB_PASS="${DB_PASS:-$(openssl rand -hex 12)}"
IP_PUBLICA="${IP_PUBLICA:-$(curl -s http://checkip.amazonaws.com || echo localhost)}"
APP_DIR="$(pwd)"

sudo apt-get update
sudo apt-get install -y python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx

# Base de datos PostgreSQL
sudo -u postgres psql <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';
  ELSE
    ALTER ROLE ${DB_USER} PASSWORD '${DB_PASS}';
  END IF;
END \$\$;
SQL
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres createdb -O ${DB_USER} ${DB_NAME}

# Variables de entorno
cat > .env <<ENV
DJANGO_SECRET_KEY=$(openssl rand -hex 32)
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${IP_PUBLICA},localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://${IP_PUBLICA}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}
DB_HOST=localhost
DB_PORT=5432
ENV
chmod 600 .env

# Python
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput
mkdir -p media

# Servicios
sudo cp deploy/gunicorn.service /etc/systemd/system/dulce_arte.service
sudo sed -i "s#/home/ubuntu/dulce_arte#${APP_DIR}#g" /etc/systemd/system/dulce_arte.service
sudo cp deploy/nginx.conf /etc/nginx/sites-available/dulce_arte
sudo sed -i "s#/home/ubuntu/dulce_arte#${APP_DIR}#g" /etc/nginx/sites-available/dulce_arte
sudo ln -sf /etc/nginx/sites-available/dulce_arte /etc/nginx/sites-enabled/dulce_arte
sudo rm -f /etc/nginx/sites-enabled/default
sudo chmod 711 "$(dirname "${APP_DIR}")" || true
sudo systemctl daemon-reload
sudo systemctl enable --now dulce_arte
sudo nginx -t && sudo systemctl restart nginx

echo
echo "Listo. Abre http://${IP_PUBLICA}/"
echo "Siguiente paso:  ./venv/bin/python manage.py seed_demo      (datos de ejemplo + usuarios por rol)"
echo "O crea tu admin: ./venv/bin/python manage.py createsuperuser"
