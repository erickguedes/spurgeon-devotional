#!/usr/bin/env python3
"""Imprime o próximo sermão não utilizado como JSON."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load_state, load_sermons_index, next_unused_sermon

state = load_state()
index = load_sermons_index()
entry = next_unused_sermon(state, index)
if entry is None:
    print(json.dumps({"done": True, "message": "Todos os sermoes ja foram utilizados."}))
else:
    used = len({p.get("sermon_id") for p in state.get("processed", [])})
    entry_out = dict(entry)
    entry_out["progress"] = {"used": used, "total": len(index)}
    print(json.dumps(entry_out, ensure_ascii=False))
