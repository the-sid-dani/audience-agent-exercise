# Audience Agent Exercise

A live build exercise: build an agent that helps people find and choose TV audiences, against a local Audiences API.

**Start with [`BRIEF.md`](BRIEF.md).** It explains the whole exercise: the situation, what to build, the rules, how the 90 minutes runs, and what we're looking for.

## Quick start

Requires Python 3.8+. Nothing to install.

```bash
python3 server.py      # Audiences API on http://127.0.0.1:8788   (--port N to change)
python3 check.py       # second terminal: checks every endpoint responds (--port N if you changed it)
```

API key: `sk_test_audiences_2026` (header `X-Api-Key`).

```bash
curl -s -H "X-Api-Key: sk_test_audiences_2026" "http://127.0.0.1:8788/segments?q=golf"
```

## What's here

| File | |
|---|---|
| `BRIEF.md` | The exercise: read this first |
| `API.md` | Full API reference |
| `server.py` | The Audiences API (standard library only) |
| `data/data.json` | The data behind it (invented for this exercise) |
| `check.py` | Pre-flight check for the running server |

Put your agent anywhere you like, in this folder or next to it.
