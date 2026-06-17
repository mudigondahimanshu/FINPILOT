# FinPilot ML service — model training + inference (activated in Phase 3).
# Pinned to Python 3.11 for broad ML wheel compatibility (torch/xgboost/onnx).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

CMD ["python", "-c", "print('FinPilot ML service — populated in Phase 3')"]
