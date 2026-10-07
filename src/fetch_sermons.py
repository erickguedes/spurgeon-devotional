#!/usr/bin/env python3
"""Ingestão em lote de sermões do archive.spurgeon.org para o pipeline devocional.

Uso (rodar a partir do workdir do projeto):
  python3 src/fetch_sermons.py probe --target-days 90     # varre o acervo em ordem,
                                                          # baixa/indexa até atingir
                                                          # o estoque desejado; mapeia
                                                          # TODO número visitado
  python3 src/fetch_sermons.py probe --limit N            # limita a N URLs varridas
  python3 src/fetch_sermons.py retry --max-attempts 3     # re-tenta os falhados
  python3 src/fetch_sermons.py coverage                   # imprime o mapa

Mapeamento (state/coverage.json):
  probed[n]   = {"status": 200, "bytes": 40179, "at": iso}   -> visitado com sucesso
  ingested[n] = {"local_id": "0011", ...}                    -> convertido com sucesso
  failed[n]   = {"status": 500|0, "attempts": k, "last_at": iso, "last_error": str}
Gaps reais (número não publicado no site) e falhas transitórias ficam em
`failed` com o status HTTP — ambos podem ser re-tentados/reavaliados depois.

IDs locais (0001, 0011, 0012...) são sequenciais e INDEPENDENTES do número PHP.
"""
import argparse
import html as htmllib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERMONS_DIR = os.path.join(WS, "sermons")
INDEX_PATH = os.path.join(SERMONS_DIR, "index.json")
COV_PATH = os.path.join(WS, "state", "coverage.json")

BASE = "https://archive.spurgeon.org/sermons/{:04d}.php"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) hermes-devotional-ingest/1.0"}
RANGE_END = 3600          # limite prático do acervo online
REQUEST_DELAY = 0.7       # s entre pedidos (educação com o servidor)
TIMEOUT = 30

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}

# --------------------------------------------------------------- persistence

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def load_cov():
    cov = load_json(COV_PATH, {})
    cov.setdefault("probed", {})
    cov.setdefault("ingested", {})
    cov.setdefault("failed", {})
    return cov


def save_cov(cov):
    cov["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_json(COV_PATH, cov)


# --------------------------------------------------------------- fetch/parse

def fetch(n, timeout=TIMEOUT):
    url = BASE.format(n)
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return 0, str(e).encode()[:200]


STATUS_BODY_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s*,?\s+(\d{4})",
    re.I)


def extract_date(text):
    m = STATUS_BODY_RE.search(text[:4000])
    if not m:
        return None
    month, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
    if month in MONTHS and 1 <= day <= 31 and 1850 <= year <= 1905:
        try:
            return date(year, MONTHS[month], day).isoformat()
        except ValueError:
            return None
    return None


def parse_page(raw):
    html = raw.decode("utf-8", errors="replace")
    m = re.search(r"<TITLE>(.*?)</TITLE>", html, re.I | re.S)
    title = htmllib.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else None
    # corpo: do fim da tag <BODY...> em diante
    m_body = re.search(r"<BODY[^>]*>", html, flags=re.I)
    body = html[m_body.end():] if m_body else html
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.I | re.S)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"<BR\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</P\s*>", "\n\n", body, flags=re.I)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text).strip()
    # remove rodapé do site
    for marker in ["Collection administered by", "Hosted by WPEngine",
                   "For help and support, please email"]:
        i = text.find(marker)
        if i > 0:
            text = text[:i].strip()
    return title, extract_date(text), text


MIN_BODY_CHARS = 5000   # sermão integral; menos que isso = página incompleta

def to_markdown(n, title, d, text, fid=""):
    fm = (f'---\nid: "{fid}"\nsermon_no: {n}\ntitle: "{title}"\ndate: "{d or ""}"\n'
          f"source: {BASE.format(n)}\nsource_license: public domain\n"
          f'language: en\n---\n\n# {title}\n\n')
    return fm + text + "\n"


# --------------------------------------------------------------- ingest logic

def next_local_id(index):
    ids = [int(e["id"]) for e in index]
    return f"{(max(ids) + 1 if ids else 1):04d}"

def already_ingested(cov):
    return set(cov["ingested"]) | {str(e.get("sermon_no")) for e in load_json(INDEX_PATH, [])}


def ingest_one(n, cov, index):
    status, raw = fetch(n)
    cov["probed"][str(n)] = {"status": status, "at": datetime.now().isoformat(timespec="seconds")}
    if status != 200:
        f = cov["failed"].get(str(n), {"attempts": 0})
        f.update({"status": status, "attempts": f.get("attempts", 0) + 1,
                  "last_at": datetime.now().isoformat(timespec="seconds")})
        cov["failed"][str(n)] = f
        return False, status
    title, d, text = parse_page(raw)
    if not title or len(text) < MIN_BODY_CHARS:
        f = cov["failed"].get(str(n), {"attempts": 0})
        f.update({"status": "short_body", "bytes": len(raw),
                  "attempts": f.get("attempts", 0) + 1,
                  "last_at": datetime.now().isoformat(timespec="seconds"),
                  "last_error": f"title={title!r} len={len(text)}"})
        cov["failed"][str(n)] = f
        return False, "short_body"
    fid = next_local_id(index)
    md = to_markdown(n, title, d, text, fid=fid)
    fname = f"{fid}-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}.md"
    with open(os.path.join(SERMONS_DIR, fname), "w", encoding="utf-8") as f:
        f.write(md)
    index.append({"id": fid, "sermon_no": n, "title": title, "date": d,
                  "file": fname, "source": BASE.format(n), "source_license": "public domain"})
    cov["ingested"][str(n)] = {"local_id": fid, "file": fname,
                               "at": datetime.now().isoformat(timespec="seconds")}
    cov["failed"].pop(str(n), None)
    return True, fid


def count_used():
    state = load_json(os.path.join(WS, "state", "processed.json"), {"processed": []})
    return {p["sermon_id"] for p in state.get("processed", [])}


def target_count(target_days):
    index = load_json(INDEX_PATH, [])
    used = count_used()
    available = sum(1 for e in index if e["id"] not in used)
    return max(0, target_days - available), len(index), available


# --------------------------------------------------------------- commands

def cmd_probe(args):
    cov = load_cov()
    index = load_json(INDEX_PATH, [])
    need, _, available = target_count(args.target_days)
    skip = already_ingested(cov)
    print(f"estoque disponível: {available} | alvo: {args.target_days} | falta baixar: {need}")
    if need == 0:
        print("Nada a fazer.")
        return
    got, visited, failed_run = 0, 0, 0
    last_save = time.time()
    for n in range(args.start, RANGE_END + 1):
        if got >= need or (args.limit and visited >= args.limit):
            break
        if str(n) in skip:
            continue
        status, res = ingest_one(n, cov, index)
        visited += 1
        if status is True or isinstance(res, str) and res.isdigit():
            got += 1
            print(f"  ✓ php={n} -> id={res}")
        else:
            failed_run += 1
            print(f"  ✗ php={n} status={res}")
        if visited % 20 == 0 or time.time() - last_save > 20:
            save_json(INDEX_PATH, index)
            save_cov(cov)
            last_save = time.time()
        time.sleep(REQUEST_DELAY)
    save_json(INDEX_PATH, index)
    save_cov(cov)
    print(f"fim da rodada: {got} novos, {failed_run} falhas, {visited} URLs visitadas")
    print(f"estoque agora: {sum(1 for e in index if e['id'] not in count_used())} sermões livres")


def cmd_retry(args):
    cov = load_cov()
    index = load_json(INDEX_PATH, [])
    failed = sorted(k for k, v in cov["failed"].items()
                    if v.get("attempts", 0) < args.max_attempts)
    print(f"re-tentando {len(failed)} sermões...")
    ok = 0
    for n in failed:
        status, res = ingest_one(n, cov, index)
        if res not in (500, 0, "short_body") and status is not False:
            ok += 1
            print(f"  ✓ php={n} -> id={res}")
        else:
            print(f"  ✗ php={n} status={res}")
        time.sleep(REQUEST_DELAY)
    save_json(INDEX_PATH, index)
    save_cov(cov)
    print(f"{ok} recuperados de {len(failed)}")


def cmd_coverage(_args):
    cov = load_cov()
    index = load_json(INDEX_PATH, [])
    used = count_used()
    print(f"index: {len(index)} sermões | usados: {len(used)} | "
          f"livres: {sum(1 for e in index if e['id'] not in used)}")
    gaps = [int(k) for k, v in cov["failed"].items()]
    print(f"falhados/gaps mapeados ({len(gaps)}): {gaps}")
    okn = sorted(int(k) for k in cov["probed"])
    if okn:
        print(f"varridos com sucesso ({len(okn)}): {okn[0]}..{okn[-1]}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--target-days", type=int, default=90)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--start", type=int, default=1)
    r = sub.add_parser("retry")
    r.add_argument("--max-attempts", type=int, default=3)
    c = sub.add_parser("coverage")
    args = ap.parse_args()
    {"probe": cmd_probe, "retry": cmd_retry, "coverage": cmd_coverage}[args.cmd](args)


if __name__ == "__main__":
    main()
