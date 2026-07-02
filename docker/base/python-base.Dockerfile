# Shared Python base image for reproducible backend/AI builds.
FROM python:3.12-slim AS python-base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir uv
WORKDIR /app
