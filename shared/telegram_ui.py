"""Helpers for Telegram-native dashboard rendering."""

from __future__ import annotations


def status_badge(active: bool) -> str:
    return "✅ Done" if active else "⏳ Pending"


def bool_badge(active: bool, yes: str = "✅ Yes", no: str = "❌ No") -> str:
    return yes if active else no
