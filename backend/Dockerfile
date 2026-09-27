FROM python:3.13.1-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY certs/russian_trusted_root_ca.crt certs/russian_trusted_sub_ca.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
COPY requirements.lock ./
RUN pip install --requirement requirements.lock
COPY . .
RUN chmod +x /app/start.sh \
    && useradd --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["/app/start.sh"]
