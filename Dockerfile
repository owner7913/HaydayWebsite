FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
 
# --- System deps: CA bundle (TLS) + Pillow image libs (small) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      libjpeg62-turbo \
      zlib1g \
      libpng16-16 \
   && update-ca-certificates \
   && rm -rf /var/lib/apt/lists/*

ARG MONGODB_DATABASE_TOOLS_VERSION=100.17.0
RUN set -eux; \
    curl -fsSL "https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian12-x86_64-${MONGODB_DATABASE_TOOLS_VERSION}.tgz" -o /tmp/mongodb-database-tools.tgz; \
    tar -xzf /tmp/mongodb-database-tools.tgz -C /tmp; \
    cp /tmp/mongodb-database-tools-*/bin/* /usr/local/bin/; \
    chmod +x /usr/local/bin/mongo*; \
    rm -rf /tmp/mongodb-database-tools*

# --- Python deps ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- App code ---
COPY . .

# --- Gunicorn ---
CMD ["gunicorn","-w","3","-k","gthread","--threads","8","--timeout","60","--log-level","info","--access-logfile","-","--error-logfile","-","-b","0.0.0.0:8080","app:app"]
