#!/usr/bin/env python3
"""Executor do fluxo devocional (Spurgeon -> devocional -> registro -> e-mail).

Uso:
  /opt/data/.venv-google/bin/python src/run_devotional.py --input payload.json
  /opt/data/.venv-google/bin/python src/run_devotional.py --send-only payload.json

payload.json = {"sermon_id": "0001", "devotional": {...estrutura...}}
Etapas: valida JSON -> salva Markdown -> envia e-mail -> so entao marca status=sent.
Se qualquer etapa falhar, o sermao NAO e marcado como processado.
"""
import argparse, base64, json, os, sys
from datetime import date, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import load_state, save_state, load_sermons_index, save_devotional, devotional_to_markdown

EMAIL_TO = None
def _recipients():
    """Destinatários: 'email_to' + 'email_cc'/extras em config.yaml (um por linha 'email_to' ou CSV)."""
    global EMAIL_TO
    if EMAIL_TO is None:
        cfgp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
        tos = []
        if os.path.exists(cfgp):
            for line in open(cfgp, encoding="utf-8"):
                if line.startswith("email_to:"):
                    tos += [x.strip() for x in line.split(":", 1)[1].strip().split(",") if x.strip()]
        EMAIL_TO = ",".join(tos) or os.environ.get("DEVOTIONAL_EMAIL_TO", "erick.guedes@gmail.com")
    return EMAIL_TO

def _email_to():
    return _recipients().split(",")[0]

REQUIRED = ["titulo", "texto_biblico", "reflexao", "para_refletir", "aplicacao_hoje", "oracao"]

def validate(dev):
    missing = [k for k in REQUIRED if not dev.get(k)]
    if missing: raise ValueError(f"campos ausentes: {missing}")
    if not dev["texto_biblico"].get("referencia"): raise ValueError("texto_biblico.referencia ausente")
    if not isinstance(dev["reflexao"], list) or len(dev["reflexao"]) < 2: raise ValueError("reflexao < 2 paragrafos")
    if not isinstance(dev["para_refletir"], list) or len(dev["para_refletir"]) < 1: raise ValueError("para_refletir vazio")

def build_html(dev):
    tv = dev["texto_biblico"]; ver = tv.get("versiculo") or ""
    import html as _html
    esc = lambda s: _html.escape(s or "")
    html = ['<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a;line-height:1.55">']
    html.append(f'<h1 style="font-size:1.35em;margin:0.2em 0">{esc(dev["titulo"])}</h1>')
    html.append(f'<p style="color:#6b7280;font-size:0.9em">{esc(dev["data_lida"])} &middot; leitura de 3-5 min</p>')
    html.append(f'<p><b>Texto b&iacute;blico:</b> {esc(tv["referencia"])}</p>')
    if ver: html.append(f'<blockquote style="margin:1em 0;padding:0.7em 1em;background:#f6f4ef;border-left:3px solid #c9a227;font-style:italic">{esc(ver)}</blockquote>')
    html.append('<h2 style="font-size:1.1em;margin-top:1.2em">Reflex&atilde;o</h2>')
    for p in dev["reflexao"]: html.append(f'<p>{esc(p)}</p>')
    html.append('<h2 style="font-size:1.1em;margin-top:1.2em">Para refletir</h2><ul>')
    for q in dev["para_refletir"]: html.append(f'<li>{esc(q)}</li>')
    html.append('</ul><h2 style="font-size:1.1em;margin-top:1.2em">Aplica&ccedil;&atilde;o para hoje</h2>')
    html.append(f'<p>{esc(dev["aplicacao_hoje"])}</p>')
    html.append('<h2 style="font-size:1.1em;margin-top:1.2em">Ora&ccedil;&atilde;o</h2>')
    html.append(f'<p><i>{esc(dev["oracao"])}</i></p>')
    html.append('<hr style="margin-top:2em"><p style="color:#9ca3af;font-size:0.75em">Devocional di&aacute;rio &middot; gerado a partir das obras de C. H. Spurgeon (dom&iacute;nio p&uacute;blico)</p>')
    html.append("</div>")
    return "\n".join(html)

def build_text(dev):
    tv = dev["texto_biblico"]; lines = [dev["titulo"], "", f"Texto biblico: {tv['referencia']}"]
    if tv.get("versiculo"): lines += [f'\u201c{tv["versiculo"]}\u201d']
    lines += ["", "REFLEXAO", ""] + [p for p in dev["reflexao"]]
    lines += ["", "PARA REFLETIR"] + [f"- {q}" for q in dev["para_refletir"]]
    lines += ["", "APLICACAO PARA HOJE", dev["aplicacao_hoje"], "", "ORACAO", dev["oracao"]]
    return "\n".join(lines)

def send_gmail(subject, html_body, text_body, to=None):
    to = to or _recipients()
    from googleapiclient.discovery import build
    token_path = "/opt/data/google_token.json"
    with open(token_path) as f: tok = json.load(f)
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials(token=tok.get("token"), refresh_token=tok.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=tok.get("client_id"), client_secret=tok.get("client_secret"), scopes=tok.get("scopes"))
    if not creds.valid: creds.refresh(Request())
    svc = build("gmail", "v1", credentials=creds)
    from email.message import EmailMessage
    em = EmailMessage()
    em["From"] = f"Devocional Diario <{_email_to()}>"
    em["To"] = to
    em["Subject"] = subject
    em.set_content(text_body)
    em.add_alternative(html_body, subtype="html")
    raw = base64.urlsafe_b64encode(em.as_bytes()).decode()
    res = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return res.get("id")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--send-only", action="store_true", help="nao reenvia se ja sent")
    a = ap.parse_args()
    payload = json.load(open(a.input, encoding="utf-8"))
    sid = payload["sermon_id"]; dev = payload["devotional"]
    dev["data_lida"] = dev.get("data_lida") or date.today().strftime("%d/%m/%Y")
    validate(dev)
    index = load_sermons_index()
    entry = next((e for e in index if e["id"] == sid), None)
    if not entry: raise SystemExit(f"sermao {sid} nao esta no index.json")
    state = load_state()
    if a.send_only and any(p.get("sermon_id") == sid and p.get("status") == "sent" for p in state["processed"]):
        print(f"SKIP: sermao {sid} ja enviado"); return
    dev["data_lida"] = entry.get("date") or dev["data_lida"]
    md_path = save_devotional(entry, dev)   # 1. markdown salvo
    print("markdown:", md_path)
    subject = f"Devocional Diario - {dev['titulo']}"
    msg_id = send_gmail(subject, build_html(dev), build_text(dev))  # 2. e-mail
    print("gmail_message_id:", msg_id)
    now = datetime.now().isoformat(timespec="seconds")
    state["processed"].append({"sermon_id": sid, "sermon_file": entry["file"],
        "processed_at": now, "devotional_id": date.today().isoformat(), "status": "sent",
        "subject": subject, "gmail_message_id": msg_id})
    state["history"].append({"at": now, "action": "sent", "sermon_id": sid, "message_id": msg_id})
    state["last_run"] = now
    save_state(state)   # 3. so agora marca como processado
    print("state atualizado: status=sent")

if __name__ == "__main__":
    main()
