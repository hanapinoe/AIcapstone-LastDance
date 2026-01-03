FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.cpu.txt /app/requirements.docker.cpu.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.docker.cpu.txt

COPY . /app

EXPOSE 8000
CMD ["uvicorn", "Backend.app.controllers.APIhandler:app", "--host", "0.0.0.0", "--port", "8000"]