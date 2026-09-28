
import logging
import os

import requests
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

import catalog
import config
import image_cache

from mimetypes import guess_type

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backend")


app = Flask(__name__)
CORS(app)  # allowing frontend requests (localhost:5173)


try:
    catalog.load_catalog(config.DATA_DIR)
except FileNotFoundError:
    raise SystemExit(
        f"error: in {config.DATA_DIR} not found catalog.jsonl"
    )


@app.route("/api/v1/health")
def health():
    ml_ok = False
    try:
        requests.get(f"{config.ML_BASE_URL}/docs", timeout=2)
        ml_ok = True
    except requests.RequestException:
        pass

    return jsonify({
        "status": "ok",
        "catalog_size": len(catalog.get_catalog()),
        "ml": ml_ok,
    })


# EVALUATING ENDPIONT (RETURNS JUST THE slug !!!!)
@app.route("/api/v1/scan", methods=["POST"])
def scan():
    f = request.files.get("image")
    if f is None:
        return jsonify({"error": "No image provided"}), 400

    try:
        r = requests.post(
            f"{config.ML_BASE_URL}/v1/eval/predict",
            files={"image": (f.filename, f.stream, f.mimetype)},
            timeout=config.ML_TIMEOUT,
        )
    except requests.RequestException as e:
        log.error("ML is down: %s", e)
        return jsonify({"error": "ml service unavailable"}), 503

    return jsonify(r.json()), r.status_code


# actual ML endpoint for frontend
@app.route("/api/v1/recognize", methods=["POST"])
def recognize():
    f = request.files.get("image")
    if f is None:
        return jsonify({"error": "no image provided"}), 400

    try:
        r = requests.post(
            f"{config.ML_BASE_URL}/v1/predict",
            files={"image": (f.filename, f.stream, f.mimetype)},
            timeout=config.ML_TIMEOUT,
        )
    except requests.RequestException as e:
        log.error("ml is down: %s", e)
        return jsonify({"error": "ml service unavailable"}), 503

    if r.status_code != 200:
        return jsonify(r.json()), r.status_code

    d = r.json()

    main = catalog.card(d["slug"]) if d.get("slug") else None
    if main:
        main = {**main, "score": d.get("score"), "margin": d.get("margin")}

    others = []
    for candidate in (d.get("top5") or [])[1:]:
        c = catalog.card(candidate["slug"])
        if c:
            others.append({**c, "score": candidate["score"]})

    return jsonify({
        "status": d.get("status"),
        "main": main,
        "others": others,
        "confidence": d.get("confidence"),
        "model_version": d.get("model_version"),
        "catalog_version": d.get("catalog_version"),
        "latency_ms": d.get("latency_ms"),
    })


# supplies frontedn with full wine card (not just the slug)
@app.route("/api/v1/wines/<slug>")
def wine(slug):
    c = catalog.card(slug)
    if c is None:
        return jsonify({"error": "not found"}), 404

    return jsonify(c)


# parses svoe-vino website and retrieves wine image (or looks up the image on the disk if it's present there)
@app.route("/api/v1/images/by-slug/<slug>")
def image_by_slug(slug):
    path = image_cache.get_or_fetch(slug)
    if not path:
        return jsonify({"error": "not found"}), 404
    mime, _ = guess_type(path)
    if not mime or mime == "application/octet-stream":
        ext = os.path.splitext(path)[1].lower()
        mime = {".webp": "image/webp", ".png": "image/png",
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/jpeg")
        
    return send_file(path, mimetype=mime, max_age=7*24*3600)


# outputs any file from data/ directory
@app.route("/api/v1/images/<path:rel>")
def image_rel(rel):
    if ".." in rel.split("/"):  # safety mechanism to not leave data/ dir
        return jsonify({"error": "bad path"}), 400

    full = os.path.join(config.DATA_DIR, rel)
    if not os.path.exists(full):
        return jsonify({"error": "not found"}), 404

    resp = send_from_directory(config.DATA_DIR, rel)
    resp.cache_control.public = True
    resp.cache_control.max_age = 7 * 24 * 3600

    return resp



# local launch
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)

