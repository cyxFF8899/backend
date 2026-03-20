from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or rebuild Chroma index.")
    parser.add_argument("--rebuild", action="store_true", help="Delete old index and rebuild")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    backend_dir = project_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.config import Settings
    from app.rag import IndexService

    settings = Settings.from_env()
    service = IndexService(settings=settings, project_root=project_root)

    count = service.build(rebuild=bool(args.rebuild))
    print(f"Index build finished, docs in collection: {count}")


if __name__ == "__main__":
    main()
