from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.embedding_service import generate_embedding
from app.deps import get_settings


async def _run(args) -> int:
    settings = get_settings()
    if not settings.embeddings_enabled:
        print("status: embeddings_disabled")
        return 0

    provider = args.provider or settings.embeddings_provider
    model = args.model or settings.embeddings_model
    result = await generate_embedding(
        text=args.text,
        provider=provider,
        model=model,
    )
    head = [round(value, 6) for value in result.embedding[:5]]
    print(f"provider: {result.provider}")
    print(f"model: {result.model}")
    print(f"dimensions: {result.dimensions}")
    print(f"latency_ms: {result.latency_ms}")
    print(f"vector_head: {head}")
    print("status: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Test configured embedding provider.")
    parser.add_argument("--text", type=str, default="hello world")
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
