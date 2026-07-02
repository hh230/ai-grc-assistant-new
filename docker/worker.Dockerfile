# Image for the 'worker' app. Scaffold placeholder — build steps added when code lands.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
WORKDIR /app
# COPY + uv sync + run command added in a later PR.
CMD ["python", "-c", "print('worker scaffold — not yet implemented')"]
