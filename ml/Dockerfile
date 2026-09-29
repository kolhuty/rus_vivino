FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/huggingface \
    PYTHONPATH=/app \
    WINE_INDEX=/app/artifacts/index.npz \
    WINE_DEVICE=cpu

WORKDIR /app

COPY ml/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ml/wine_recognition ./wine_recognition

COPY data/artifacts/index.npz /app/artifacts/index.npz

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "wine_recognition.api:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
