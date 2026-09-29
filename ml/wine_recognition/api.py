import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from .images import InvalidImage, MAX_BYTES
from .service import WineRecognizer


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.recognizer = await run_in_threadpool(
        WineRecognizer.load, Path(os.getenv("WINE_INDEX", "artifacts/index.npz")),
        os.getenv("WINE_DEVICE", "auto"),
        os.getenv("WINE_LOCALIZER", "1").lower() not in {"0", "false", "no"},
        os.getenv("WINE_DETECTOR_MODEL") or None,
    )
    yield


app = FastAPI(title="Wine visual retrieval", lifespan=lifespan)


@app.get("/")
@app.get("/health")
async def health():
    """Liveness + readiness: сервер поднялся и модель загружена."""
    if not hasattr(app.state, "recognizer"):
        raise HTTPException(503, "model is still loading")
    return {"status": "ok"}


async def predict_upload(image: UploadFile, diagnostic: bool):
    try:
        payload = await image.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 15 MB")
        return await run_in_threadpool(app.state.recognizer.predict, payload, diagnostic)
    except InvalidImage as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        await image.close()


@app.post("/v1/eval/predict")
async def eval_predict(image: UploadFile = File(...)):
    return await predict_upload(image, False)


@app.post("/v1/predict")
async def diagnostic_predict(image: UploadFile = File(...)):
    return await predict_upload(image, True)
