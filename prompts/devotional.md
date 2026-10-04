# Construction (internal rationale — PRUNED-STYLE PLAN, not user-visible)
The devotional must be written entirely in Brazilian Portuguese (pt-BR), in contemporary natural language.
It is an independent devotional — never a summary of the sermon, never mentioning Spurgeon, the
preacher, the sermon, or that this text derives from any source.

## Pipeline inside the model
1. Read the sermon carefully.
2. Grasp the central argument (what is Spurgeon driving at?).
3. Identify the core spiritual principles (2-3 at most, not everything).
4. Identify the Bible passages that carry or imply the message.
5. Compose an original devotional: fresh reflection in today's language plus practical application.
6. Preserve theological fidelity: baptistic/Reformed historic Christianity, no invented doctrine, no
   paraphrase drift. Priorities when interpreting: (a) the sermon's own context, (b) biblical context,
   (c) historic Christian orthodoxy, (d) clarity for a modern reader.
7. Language: contemporary and natural Portuguese, avoiding archaic tender (King-James style terms).
8. Depth over quantity: no filler, no repetition, no academic detours.

## Bible quotations
- The "Texto bíblico" field must be a SHORT quoted passage (1-3 verses), taken from Almeida version
  (public domain, e.g. ARC. If quoting exactly, mark "Almeida" at the end; otherwise give reference only).
- Do not decorate with random verses — each reference must serve the central idea.

## Length calibration
Total ~450-620 words (reading time 3-4 minutes at ~150 wpm for Portuguese).
Reflexão: 3 short paragraphs. Keep the reader thirsting, not exhausted.

## Output contract (STRICT — final must be exactly these 6 top-level keys and nothing else)
{
  "titulo": "...",
  "texto_biblico": {"referencia": "Livro C:V-V", "versiculo": "quotation or null"},
  "reflexao": ["p1", "p2", "p3"],
  "para_refletir": ["q1", "q2", "q3"],
  "aplicacao_hoje": "...",
  "oracao": "..."
}
- Never include extra fields; never merge paragraphs; strings, not lists, in textos/oracao/reflexao quando único.
- No trailing commas or markdown blocks in the JSON.
