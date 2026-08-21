from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

try:
    import allure
except ImportError:
    allure = None


Decorator = Callable[[Callable[..., Any]], Callable[..., Any]]


def title(name: str) -> Decorator:
    """Return an Allure title decorator or a no-op fallback."""
    if allure:
        return allure.title(name)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator


def feature(name: str) -> Decorator:
    """Return an Allure feature decorator or a no-op fallback."""
    if allure:
        return allure.feature(name)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator


@contextmanager
def step(name: str) -> Iterator[None]:
    """Expose an Allure step while keeping local collection dependency-tolerant."""
    if allure:
        with allure.step(name):
            yield
    else:
        yield


def attach_text(name: str, body: object) -> None:
    """Attach text only when Allure is installed."""
    if not allure:
        return
    allure.attach(str(body), name=name, attachment_type=allure.attachment_type.TEXT)
