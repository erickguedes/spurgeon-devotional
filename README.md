# Spurgeon Devotional Diario

Transforma sermoes de Charles H. Spurgeon (dominio publico) em devocionais
curtos em portugues (pt-BR, leitura de 3–5 min) e envia por e-mail todos os
dias as 08:00 (America/Sao_Paulo). Executado pelo Hermes.

## Estrutura

```text
spurgeon-devotional/
├── sermons/            # sermoes originais (NUNCA modificados) + index.json
├── devotionals/        # devocionais gerados: YYYY/MM/DD.md
├── prompts/            # prompt de geracao (devotional.md)
├── src/                # lib.py, run_devotional.py, next_sermon.py
├── state/processed.json# registro: quais sermoes foram usados (status, IDs)
├── config.yaml         # e-mail destino, modelo, horario
└── README.md
```

## Fluxo diario

1. `next_sermon.py` escolhe o primeiro sermao sem registro em `state/processed.json`.
2. O Hermes le o sermao e gera o devocional (JSON) seguindo `prompts/devotional.md`
   (pt-BR, sem citar Spurgeon no corpo, fiel ao conteudo teologico).
3. `run_devotional.py --input payload.json`:
   valida → salva `devotionals/YYYY/MM/DD.md` → envia e-mail (Gmail API) →
   **so entao** marca `status: sent` em `state/processed.json`.
4. Se qualquer etapa falha, o sermao NAO e marcado (rodar de novo nao duplica:
   `--send-only` pula sermoes ja enviados).

## Configuracao

- `config.yaml`: `email_to`, `default_model`, `delivery_hour`, `timezone`.
- Credenciais: Gmail usa `/opt/data/google_token.json` (OAuth ja configurado,
  fora do repo). Nenhum segredo vive neste repositorio.
- GitHub: para publicar, criar o repo na conta erick.guedes@gmail.com e
  `git remote add origin <url>` + `git push -u origin main`.
  PAT fine-grained com permissao `contents: write` (push de `state/`).

## Comandos uteis

```bash
# proximo sermao nao utilizado
/opt/data/.venv-google/bin/python src/next_sermon.py

# processar/enviar (apos gerar o payload)
/opt/data/.venv-google/bin/python src/run_devotional.py --input payload.json

# historico
cat state/processed.json
```

## Adicionar mais sermoes

Baixar de https://archive.spurgeon.org/sermons/NNNN.php (texto integral,
dominio publico), salvar como `sermons/NNNN-titulo-slug.md` com front-matter
(`id`, `sermon_no`, `title`, `date`, `source`, `source_license: public domain`)
e registrar em `sermons/index.json` (o `id` precisa ser unico e sequencial).

## Futuro (nao implementado)

Telegram, audio/voz, busca por temas, interface web, multiplas fontes —
a arquitetura (payload JSON + registro em `state/`) ja suporta novos canais
sem mudar o nucleo.
