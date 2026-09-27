"""Registry for document loaders by MIME type."""

from __future__ import annotations

from typing import Callable

_REGISTRY: dict[str, Callable] = {}


def register(mime_type: str):
    def decorator(func: Callable) -> Callable:
        _REGISTRY[mime_type] = func
        return func
    return decorator


def get_loader(mime_type: str) -> Callable | None:
    return _REGISTRY.get(mime_type)


def list_supported() -> list[str]:
    return list(_REGISTRY.keys())
