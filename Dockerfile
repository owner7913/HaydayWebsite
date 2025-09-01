FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Set environment variable for Fly.io
ENV PORT=8080

# Use JSON array for CMD, no comments allowed inside
CMD ["gunicorn", \
    "-w", "2", \
    "-k", "gthread", \
    "--threads", "8", \
    "--timeout", "60", \
    "--preload", \
    "--log-level", "debug", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "-b", "0.0.0.0:8080", \
    "app:app"]
