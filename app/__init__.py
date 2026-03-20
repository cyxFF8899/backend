from __future__ import annotations


def create_app():
    from .main import create_app as _create_app

    return _create_app()


def __getattr__(name: str):
    if name == "app":
        from .main import app as _app

        return _app
    raise AttributeError(f"module 'app' has no attribute {name!r}")


__all__ = ["app", "create_app"]
