FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código (incluye start.sh)
COPY . .

# Puerto
EXPOSE 8000

# Script de arranque: corre migraciones y luego inicia la app
RUN chmod +x /app/start.sh

# Comando para producción
CMD ["/app/start.sh"]
