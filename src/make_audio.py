#!/usr/bin/env python3
"""Gera o áudio do devocional do dia via edge-tts (determinístico, sem LLM).

Uso: python make_audio.py <sermon_id>   (lê devotionals/YYYY/MM/<hoje>-<id>.md)
Saída: devotionals/YYYY/MM/<hoje>-<sermon_id>.mp3
Falha (exit != 0) se o markdown não existir; edge-tts falha => exit != 0.
"""
import re
import subprocess
import sys
from datetime import date

sys.path.insert(0, __import__("os").path.dirname(__file__))
from lib import DEVOTIONALS_DIR

D = date.today().isoformat()
y, m = D.split("-")[:2]
md = f"{DEVOTIONALS_DIR}/{y}/{m}/{D}-{sys.argv[1]}.md"

try:
    txt = open(md, encoding="utf-8").read()
except FileNotFoundError:
    print(f"ERRO: markdown não encontrado: {md}")
    sys.exit(1)

plain = re.sub(r"^# ", "", txt, flags=re.M)
plain = re.sub(r"^\*\*.*?\*\*.*$", "", plain, flags=re.M)
plain = re.sub(r"^> .*$", "", plain, flags=re.M)
plain = re.sub(r"^## ", "", plain, flags=re.M)
plain = re.sub(r"^- ", "", plain, flags=re.M)
plain = re.sub(r"[*_>`#]", "", plain)
plain = re.sub(r"\n{2,}", "\n", plain).strip()

temp_txt = md.rsplit("/", 1)[0] + "/.audio_text.txt"
open(temp_txt, "w", encoding="utf-8").write(plain)

out_mp3 = md.replace(".md", ".mp3")
env = {"PYTHONPATH": "/opt/data/lazy-packages", "PATH": "/usr/bin:/bin"}
r = subprocess.run(
    ["/opt/data/lazy-packages/bin/edge-tts", "--voice", "pt-BR-FranciscaNeural",
     "--file", temp_txt, "--write-media", out_mp3],
    capture_output=True, text=True, timeout=180, env=env)
if r.returncode != 0:
    print("ERRO edge-tts:", (r.stderr or r.stdout or "")[:300])
    sys.exit(1)

import os
print(f"OK: {out_mp3} ({os.path.getsize(out_mp3)} bytes)")
