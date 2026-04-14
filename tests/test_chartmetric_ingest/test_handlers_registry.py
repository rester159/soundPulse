"""Unit tests for the handler registry — register / get / duplicate guard."""
from __future__ import annotations

import pytest

from chartmetric_ingest import handlers as cmq_handlers


@pytest.fixture(autouse=True)
def _reset_registry():
    cmq_handlers.clear_for_tests()
    yield
    cmq_handlers.clear_for_tests()


def test_register_and_get():
    @cmq_handlers.register("my_handler")
    async def my_handler(body, ctx, db):
        pass

    assert cmq_handlers.get("my_handler") is my_handler
    assert "my_handler" in cmq_handlers.all_handlers()


def test_unknown_handler_returns_none():
    assert cmq_handlers.get("does_not_exist") is None


def test_duplicate_registration_raises():
    @cmq_handlers.register("dup")
    async def first(body, ctx, db):
        pass

    with pytest.raises(RuntimeError, match="already registered"):
        @cmq_handlers.register("dup")
        async def second(body, ctx, db):
            pass


def test_all_handlers_sorted():
    @cmq_handlers.register("z_last")
    async def z(body, ctx, db): pass
    @cmq_handlers.register("a_first")
    async def a(body, ctx, db): pass
    @cmq_handlers.register("m_middle")
    async def m(body, ctx, db): pass

    assert cmq_handlers.all_handlers() == ["a_first", "m_middle", "z_last"]
