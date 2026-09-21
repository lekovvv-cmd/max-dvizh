FROM python:3.13.1-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app
WORKDIR /app
COPY requirements.lock ./
RUN pip install --requirement requirements.lock
COPY . .
RUN chmod +x /app/start.sh \
    && useradd --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["/app/start.sh"]
