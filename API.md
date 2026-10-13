# Audiences API Reference

Base URL: `http://127.0.0.1:8788` (or whatever `--port` you start it on).

**Authentication.** Every route except `/health` needs the header `X-Api-Key: sk_test_audiences_2026`. `Authorization: Bearer sk_test_audiences_2026` also works.

**Format.** JSON in, JSON out. Errors always look like:

```json
{"error": "human-readable message", "...": "optional extra fields such as hint or allowed"}
```

| Status | Meaning |
|---|---|
| 200 / 201 | OK / created |
| 400 | Bad input; the message says what to fix |
| 401 | Missing or wrong API key |
| 403 | Not allowed (changing a restricted segment, or setting a partner signal) |
| 404 | Unknown id or route |
| 405 | Method not supported on that route |
| 409 | Name already taken |

**State.** Data is in memory. Restarting the server resets it to `data/data.json`. Every request is printed in the server window (writes get a banner) and appended to `api-calls.jsonl`, which is kept across restarts.

**Data date.** The data is as of **2026-10-11**. Lookback windows count back from that date.

---

## Reference data

### `GET /health`
`{"ok": true}`. No key needed.

### `GET /genres`
Every genre and language that appears in the catalog.
```json
{"genres": ["action", "adventure", "animals", "..."], "languages": ["en", "es", "hi", "ja", "ko"]}
```

### `GET /geo?type=country|state|dma&q=`
Geography codes with each one's share of US TV households. `type` defaults to `state`. `q` filters by name or code (every word must match).
```json
{"type": "dma", "total": 1, "items": [{"code": "807", "name": "San Francisco-Oakland-San Jose", "type": "dma", "states": ["CA"], "household_share": 0.021}]}
```

---

## Content

### `GET /content/search`
| Param | Meaning |
|---|---|
| `q` | Free text. Matches whole words (plurals count, so "dramas" finds "drama") in the title, genres, network, description or language name. Any of your words can match; filler words like "the", "fans" or "audience" are ignored. Best matches first: the exact phrase in the title ranks highest. |
| `genre`, `language`, `network`, `type`, `country` | Exact filters. `type` is `series`, `movie` or `live_event`; `language` is a code like `ko`; `genre` must exist in `/genres`. Invalid values return 400. |
| `limit` | Page size, default 20, max 50 |
| `offset` | Start position, default 0 |

```json
{"total": 2, "next_offset": null, "items": [
  {"id": "ct-026", "title": "The Office", "type": "series", "genres": ["comedy", "sitcom"], "network": "Peacock",
   "language": "en", "country": "US", "year": 2005, "description": "...", "monthly_viewing_households": 9000000,
   "last_aired": null}
]}
```
- `monthly_viewing_households`: households that watch in a typical month (for a live event, the households that watched it).
- `last_aired`: for live events, the date it last aired; `null` for series and movies, which are on demand.
Keep requesting with `offset=next_offset` until `next_offset` is `null`.

### `GET /content/{id}`
One title, same shape as above.

---

## Segments

### `GET /segments`
| Param | Meaning |
|---|---|
| `q` | Free text, same whole-word matching as content search, against name and description, best matches first |
| `team` | Owning team, e.g. `Sales` |
| `cursor` | Start position, default 0 |
| `limit` | Page size, default 10, max 25 |

Returns summaries. Follow `next_cursor` until it's `null`.
```json
{"total": 40, "next_cursor": 10, "items": [
  {"id": "seg-001", "name": "Cord Cutters", "description": "Households that watched TV only through streaming apps in the last 90 days.",
   "owner_team": "Agency Services", "restricted": false, "updated_at": "2026-06-11"}
]}
```

### `GET /segments/{id}`
The full segment, with its definition and current size.
```json
{"id": "seg-029", "name": "Golf Fans", "description": "Golf viewers.", "owner_team": "Sales", "restricted": false,
 "definition": {"content_ids": [], "genres": ["golf"], "languages": [], "geo": {"type": "country", "codes": ["US"]},
                "lookback_days": 90, "viewing_source": "any"},
 "created_at": "2025-04-01", "updated_at": "2026-04-15", "estimated_households": 400000, "live_events_outside_window": 1}
```
`estimated_households` is the current size. `live_events_outside_window` says how many matched live events no longer count because they aired before the lookback window (here, The Masters in April).

Segments built by the Partnerships team can carry an extra `partner_signal` field in their definition. It can't be set or changed through this API.

### `POST /segments`
Creates a segment. Returns 201 with the full segment.
```json
{"name": "Golf Weekend Viewers", "description": "optional", "definition": {"genres": ["golf"], "lookback_days": 30}}
```
- `name` is required and must be unique (case-insensitive), otherwise 409.
- Definition fields you leave out get defaults (see below).
- New segments are owned by `Audience Desk`, the team this API key belongs to.

### `PATCH /segments/{id}`
Updates `name`, `description` and/or `definition`. Returns 200 with the full segment.
- Definition fields you send **replace** those fields; fields you don't send stay as they were. For example, `{"definition": {"lookback_days": 90}}` only changes the lookback.
- Restricted segments return 403.

### Deleting
Not supported (405).

---

## Estimating size

### `POST /estimate`
Returns the estimated number of households for a definition without saving anything. The body can be `{"definition": {...}}` or the definition itself.
```json
{"estimated_households": 1189000, "matched_titles": 1, "live_events_outside_window": 0,
 "factors": {"content_reach": 18000000, "geo_share": 0.1739, "viewing_source": 0.38}}
```
- `live_events_outside_window`: how many of the matched live events aired before the lookback window and so count for nothing. If it's above 0, a longer `lookback_days` may be what the person meant.
- Estimates are deterministic: the same definition always returns the same number.

---

## The segment definition

```json
{
  "content_ids": ["ct-001"],
  "genres": ["basketball"],
  "languages": ["es"],
  "geo": {"type": "state", "codes": ["TX", "OK"]},
  "lookback_days": 30,
  "viewing_source": "any"
}
```

| Field | Meaning | Default |
|---|---|---|
| `content_ids` | Households that watched **any** of these titles (ids from `/content/search`) | `[]` |
| `genres` | ...or anything in **any** of these genres (see `/genres`) | `[]` |
| `languages` | Limit to content in these languages | `[]` (all) |
| `geo` | `type` is `country`, `state` or `dma`, with a list of `codes` (see `/geo`). Nothing finer exists. | `{"type": "country", "codes": ["US"]}` |
| `lookback_days` | How far back viewing counts, from the data date: one of `7, 14, 30, 60, 90, 180, 365`. Live events only count if they aired inside the window; series and movies always count, and longer windows reach more households. | `30` |
| `viewing_source` | `any`, `streaming_only` (watched only through streaming apps) or `linear_only` (cable and broadcast only) | `any` |

With no `content_ids`, `genres` or `languages`, the definition covers all viewing.
