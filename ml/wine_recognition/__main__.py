import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Wine image retrieval")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-index")
    build.add_argument("--catalog", type=Path, default=Path("data/catalog.jsonl"))
    build.add_argument("--output", type=Path, default=Path("artifacts/index.npz"))
    build.add_argument("--model-id", default="google/siglip2-base-patch16-224")
    build.add_argument("--revision", default="main")
    build.add_argument("--batch-size", type=int)
    build.add_argument("--catalog-version", default="catalog-v1")
    predict = commands.add_parser("predict")
    predict.add_argument("--image", required=True, type=Path)
    predict.add_argument("--index", type=Path, default=Path("artifacts/index.npz"))
    predict.add_argument("--output", type=Path, default=Path("prediction.json"))
    predict.add_argument("--diagnostic", action="store_true")
    predict.add_argument("--no-localizer", action="store_true")
    for sub in (build, predict):
        sub.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = parser.parse_args()
    if args.command == "build-index":
        from .encoder import create_encoder
        from .index import build_index
        encoder = create_encoder(args.model_id, args.revision, args.device)
        batch_size = args.batch_size or encoder.recommended_batch_size
        build_index(args.catalog, encoder, batch_size, args.catalog_version).save(args.output)
    else:
        from .service import WineRecognizer
        result = WineRecognizer.load(
            args.index, args.device, localize=not args.no_localizer
        ).predict(args.image, args.diagnostic)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
