#!/usr/bin/env python3
"""Shared helpers for the Spurgeon daily-devotional pipeline.

Everything here is stdlib-only so it can run on cronjobs or inside the
Hermes kernel without extra dependencies.
"""
import json
import os
import re
from datetime import datetime, date

WS = os.environ.get("DEVOTIONAL_WS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(WS, "state", "processed.json")
SERMONS_INDEX = os.path.join(WS, "sermons", "index.json")
PROMPT_PATH = os.path.join(WS, "prompts", "devotional.md")
DEVOTIONALS_DIR = os.path.join(WS, "devotionals")

# ---------------------------------------------------------------- serialization

def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"processed": []}
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_PATH)


def load_sermons_index() -> list:
    if not os.path.exists(SERMONS_INDEX):
        raise FileNotFoundError(f"sermons index not found: {SERMONS_INDEX}")
    with open(SERMONS_INDEX, encoding="utf-8") as f:
        return json.load(f)


def next_unused_sermon(state: dict, index: list) -> dict | None:
    """First sermon in index.json whose id was never used (processed = anything non-empty)."""
    done = {p.get("sermon_id") for p in state.get("processed", [])}
    for entry in index:
        if entry["id"] not in done:
            return entry
    return None


def devotional_path_for(d: str | datetime | None = None) -> str:
    """Path of the devotional markdown for date d (YYYY-MM-DD)."""
    if isinstance(d, datetime):
        d = d.date().isoformat()
    elif d is None:
        d = date.today().isoformat()
    y, m = d.split("-")[:2]
    return os.path.join(DEVOTIONALS_DIR, y, m, f"{d}.md")


# ---------------------------------------------------------------- sermon loader

def load_sermon(entry: dict) -> str:
    path = os.path.join(WS, "sermons", entry["file"])
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- devotional write

def devotional_to_markdown(dev: dict, entry: dict) -> str:
    tv = dev.get("texto_biblico", {})
    ref = tv.get("referencia", "")
    ver = tv.get("versiculo") or ""
    verses = f'\n> {ver}  \n> — *{ref}* (Almeida)\n' if ver else f'\n_{ref}_\n'
    lines = [
        f"# {dev.get('titulo','').strip()}",
        "",
        f"**Texto bíblico:** {ref}",
        verses,
        "## Reflexão",
        "",
    ]
    for p in dev.get("reflexao", []):
        lines += [p.strip(), ""]
    lines += ["## Para refletir", ""]
    for q in dev.get("para_refletir", []):
        lines += [f"- {q}"]
    lines += ["", "## Aplicação para hoje", "", dev.get("aplicacao_hoje", "").strip(), "",
              "## Oração", "", dev.get("oracao", "").strip(), ""]
    return "\n".join(lines)


def save_devotional(entry: dict, dev: dict) -> str:
    d_iso = date.today().isoformat()
    path = devotional_path_for(d_iso)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(devotional_to_markdown(dev, entry))
    return path
