"""Audiences API for the Audience Agent exercise. Python 3.8+, standard library only.

    python3 server.py              # http://127.0.0.1:8788
    python3 server.py --port 9000

Data lives in memory and resets to data/data.json on every restart.
Every request is printed to the console and appended to api-calls.jsonl (kept across restarts).
See API.md for the full reference.
"""
import copy, datetime, http.server, json, os, re, sys, threading, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "data.json")
LOG_PATH = os.path.join(HERE, "api-calls.jsonl")
API_KEY = "sk_test_audiences_2026"
DEFAULT_PORT = 8788
SEGMENT_PAGE, SEGMENT_MAX = 10, 25
CONTENT_PAGE, CONTENT_MAX = 20, 50

with open(DATA_PATH) as f:
    DB = json.load(f)
META = DB["meta"]
BASE = META["total_us_tv_households"]
LOOKBACK = {7: 0.45, 14: 0.6, 30: 0.75, 60: 0.9, 90: 1.0, 180: 1.08, 365: 1.15}
SOURCE = {"any": 1.0, "streaming_only": 0.38, "linear_only": 0.22}
DEFINITION_FIELDS = ("content_ids", "genres", "languages", "geo", "lookback_days", "viewing_source")
AS_OF = datetime.date.fromisoformat(META["data_as_of"])
LANGUAGE_NAMES = {"en": "english", "es": "spanish", "ko": "korean", "ja": "japanese", "hi": "hindi"}
STOPWORDS = {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "who", "with", "fans", "fan", "viewers",
             "audience", "audiences", "segment", "segments", "people", "watch", "watched", "watching", "show", "shows"}
CONTENT = {c["id"]: c for c in DB["content"]}
GENRES = sorted({g for c in DB["content"] for g in c["genres"]})
LANGUAGES = sorted({c["language"] for c in DB["content"]})
GEO = {t: {g["code"]: g for g in items} for t, items in DB["geo"].items()}
WRITE_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, status, message, **detail):
        super().__init__(message)
        self.status, self.message, self.detail = status, message, detail


# ---------- validation ----------

def int_param(q, name, default, lo, hi):
    raw = q.get(name)
    if raw is None or raw == "":
        return default
    try:
        val = int(raw)
    except ValueError:
        raise ApiError(400, f"'{name}' must be an integer")
    if val < lo:
        raise ApiError(400, f"'{name}' must be at least {lo}")
    return min(val, hi)


def str_list(d, field):
    val = d.get(field, [])
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        raise ApiError(400, f"definition.{field} must be a list of strings")
    return val


def validate_definition(d, partial=False):
    """Validate a definition. partial=True is for PATCH: only the fields sent are checked."""
    if not isinstance(d, dict):
        raise ApiError(400, "definition must be a JSON object")
    if "partner_signal" in d:
        raise ApiError(403, "partner signals can only be applied by the Partnerships team")
    unknown = sorted(set(d) - set(DEFINITION_FIELDS))
    if unknown:
        raise ApiError(400, f"unknown definition fields: {unknown}", allowed=list(DEFINITION_FIELDS))
    out = {}
    if "content_ids" in d:
        out["content_ids"] = str_list(d, "content_ids")
        for cid in out["content_ids"]:
            if cid not in CONTENT:
                raise ApiError(400, f"unknown content id '{cid}'", hint="find ids with GET /content/search")
    if "genres" in d:
        out["genres"] = str_list(d, "genres")
        for g in out["genres"]:
            if g not in GENRES:
                raise ApiError(400, f"unknown genre '{g}'", hint="see GET /genres")
    if "languages" in d:
        out["languages"] = str_list(d, "languages")
        for lang in out["languages"]:
            if lang not in LANGUAGES:
                raise ApiError(400, f"no content in language '{lang}'", available=LANGUAGES)
    if "geo" in d:
        geo = d["geo"]
        if not isinstance(geo, dict) or geo.get("type") not in GEO:
            raise ApiError(400, "geo.type must be one of country, state, dma (no finer geography is available)")
        codes = geo.get("codes")
        if not isinstance(codes, list) or not codes or not all(isinstance(c, str) for c in codes):
            raise ApiError(400, "geo.codes must be a non-empty list of code strings")
        for code in codes:
            if code not in GEO[geo["type"]]:
                raise ApiError(400, f"unknown {geo['type']} code '{code}'", hint=f"see GET /geo?type={geo['type']}")
        out["geo"] = {"type": geo["type"], "codes": list(codes)}
    if "lookback_days" in d:
        lb = d["lookback_days"]
        if isinstance(lb, bool) or lb not in LOOKBACK:
            raise ApiError(400, f"lookback_days must be one of {sorted(LOOKBACK)}")
        out["lookback_days"] = lb
    if "viewing_source" in d:
        if d["viewing_source"] not in SOURCE:
            raise ApiError(400, f"viewing_source must be one of {sorted(SOURCE)}")
        out["viewing_source"] = d["viewing_source"]
    if not partial:
        out.setdefault("content_ids", [])
        out.setdefault("genres", [])
        out.setdefault("languages", [])
        out.setdefault("geo", {"type": "country", "codes": ["US"]})
        out.setdefault("lookback_days", 30)
        out.setdefault("viewing_source", "any")
    return out


# ---------- sizing ----------

def in_window(c, lookback_days):
    """Live events only count if they aired inside the lookback window. Series and movies are on demand."""
    if c["type"] != "live_event":
        return True
    return datetime.date.fromisoformat(c["last_aired"]) >= AS_OF - datetime.timedelta(days=lookback_days)


def estimate(d):
    langs = set(d.get("languages") or [])
    content_ids = set(d.get("content_ids") or [])
    genres = set(d.get("genres") or [])
    days = d.get("lookback_days", 30)
    lb = LOOKBACK[days]
    if content_ids or genres:
        picked = [c for c in DB["content"] if c["id"] in content_ids or genres & set(c["genres"])]
        if langs:
            picked = [c for c in picked if c["language"] in langs]
    elif langs:
        picked = [c for c in DB["content"] if c["language"] in langs]
    else:
        picked = None  # no content filter: all viewing
    out_of_window = 0
    if picked is None:
        reach = BASE * min(lb, 1.0)
    else:
        miss = 1.0
        for c in picked:
            if not in_window(c, days):
                out_of_window += 1
                continue
            factor = 1.0 if c["type"] == "live_event" else lb
            miss *= 1 - min(1.0, c["monthly_viewing_households"] * factor / BASE)
        reach = BASE * (1 - miss)
    geo = d.get("geo") or {"type": "country", "codes": ["US"]}
    share = min(1.0, sum(GEO[geo["type"]][code]["household_share"] for code in geo["codes"]))
    src = SOURCE[d.get("viewing_source", "any")]
    partner = 0.3 if d.get("partner_signal") else 1.0
    size = int(round(reach * share * src * partner / 1000.0)) * 1000
    return {"estimated_households": size,
            "matched_titles": len(CONTENT) if picked is None else len(picked),
            "live_events_outside_window": out_of_window,
            "factors": {"content_reach": int(reach), "geo_share": round(share, 4), "viewing_source": src}}


# ---------- helpers ----------

def find_segment(seg_id):
    return next((s for s in DB["segments"] if s["id"] == seg_id), None)


def seg_summary(s):
    return {k: s[k] for k in ("id", "name", "description", "owner_team", "restricted", "updated_at")}


def seg_full(s):
    out = copy.deepcopy(s)
    est = estimate(s["definition"])
    out["estimated_households"] = est["estimated_households"]
    out["live_events_outside_window"] = est["live_events_outside_window"]
    return out


def words(text):
    """Lowercase whole words, punctuation and hyphens split, simple plural stemming."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        out.add(w)
        if len(w) > 3 and w.endswith("s"):
            out.add(w[:-1])
    return out


def tokens(query):
    toks = re.findall(r"[a-z0-9]+", query.lower())
    keep = [t for t in toks if t not in STOPWORDS]
    toks = keep or toks
    return [t[:-1] if len(t) > 3 and t.endswith("s") else t for t in toks]


def score(query, title, *fields):
    """0 = no match. Whole-word matching. Higher is better: the whole phrase in the title beats word hits."""
    hay = words(" ".join((title,) + fields))
    hits = sum(1 for t in tokens(query) if t in hay)
    if not hits:
        return 0
    phrase = " ".join(re.findall(r"[a-z0-9]+", query.lower()))
    title_norm = " ".join(re.findall(r"[a-z0-9]+", title.lower()))
    return (100 if phrase and phrase in title_norm else 0) + hits


def all_words(query, *fields):
    """Strict match for lookups like geography: every word must appear."""
    hay = " ".join(fields).lower()
    return all(t in hay for t in query.lower().split())


def matches(query, *fields):
    return score(query, *fields) > 0


def today():
    return datetime.date.today().isoformat()


# ---------- HTTP ----------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "AudiencesAPI/1.1"

    def log_message(self, *args):
        pass

    def _record(self, status, body, write, note):
        entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                 "method": self.command, "path": self.path, "status": status}
        if body is not None:
            entry["body"] = body
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        line = f"[{'WRITE' if write else 'READ '}] {self.command} {self.path} -> {status}"
        if note:
            line += f"  {note}"
        if write and status < 300:
            line = "=" * 72 + "\n" + line + "\n" + "=" * 72
        print(line, flush=True)

    def _send(self, status, payload, body=None, write=False, note=""):
        data = json.dumps(payload, indent=1, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self._record(status, body, write, note)

    def _authorized(self):
        key = self.headers.get("X-Api-Key") or ""
        auth = self.headers.get("Authorization") or ""
        if not key and auth.lower().startswith("bearer "):
            key = auth[7:].strip()
        return key == API_KEY

    def _json_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "invalid Content-Length")
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "request body must be valid JSON")
        if not isinstance(body, dict):
            raise ApiError(400, "request body must be a JSON object")
        return body

    def _dispatch(self, method):
        url = urllib.parse.urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        body = None
        try:
            if parts == ["health"] and method == "GET":
                return self._send(200, {"ok": True})
            if not self._authorized():
                raise ApiError(401, "missing or invalid API key (send header X-Api-Key)")
            if method in ("POST", "PATCH"):
                body = self._json_body()
            payload, status, write, note = self._route(method, parts, q, body)
            self._send(status, payload, body, write, note)
        except ApiError as e:
            self._send(e.status, {"error": e.message, **e.detail}, body)
        except Exception as e:  # never take the server down mid-session
            self._send(500, {"error": "internal error", "detail": str(e)}, body)

    def _route(self, method, parts, q, body):
        # reference data
        if parts == ["genres"]:
            self._only(method, "GET")
            return {"genres": GENRES, "languages": LANGUAGES}, 200, False, ""
        if parts == ["geo"]:
            self._only(method, "GET")
            t = q.get("type", "state")
            if t not in GEO:
                raise ApiError(400, "type must be one of country, state, dma")
            items = [g for g in DB["geo"][t] if not q.get("q") or all_words(q["q"], g["name"], g["code"])]
            return {"type": t, "total": len(items), "items": items}, 200, False, ""

        # content
        if parts == ["content", "search"]:
            self._only(method, "GET")
            limit = int_param(q, "limit", CONTENT_PAGE, 1, CONTENT_MAX)
            offset = int_param(q, "offset", 0, 0, 10 ** 6)
            if q.get("type") and q["type"].lower() not in ("series", "movie", "live_event"):
                raise ApiError(400, "type must be one of series, movie, live_event")
            if q.get("language") and q["language"].lower() not in LANGUAGES:
                raise ApiError(400, f"language must be a code, one of {LANGUAGES}")
            if q.get("genre") and q["genre"].lower() not in GENRES:
                raise ApiError(400, f"unknown genre '{q['genre']}'", hint="see GET /genres")
            res = []
            for c in DB["content"]:
                if q.get("q") and not score(q["q"], c["title"], " ".join(c["genres"]), c["network"], c["description"],
                                            LANGUAGE_NAMES.get(c["language"], "")):
                    continue
                if q.get("genre") and q["genre"].lower() not in c["genres"]:
                    continue
                if any(q.get(f) and str(c[f]).lower() != q[f].lower() for f in ("language", "network", "type", "country")):
                    continue
                res.append(c)
            if q.get("q"):
                res.sort(key=lambda c: (-score(q["q"], c["title"], " ".join(c["genres"]), c["network"], c["description"],
                                               LANGUAGE_NAMES.get(c["language"], "")), -c["monthly_viewing_households"]))
            page = res[offset:offset + limit]
            nxt = offset + limit if offset + limit < len(res) else None
            return {"total": len(res), "items": page, "next_offset": nxt}, 200, False, ""
        if len(parts) == 2 and parts[0] == "content":
            self._only(method, "GET")
            if parts[1] not in CONTENT:
                raise ApiError(404, f"no content with id '{parts[1]}'")
            return CONTENT[parts[1]], 200, False, ""

        # estimate
        if parts == ["estimate"]:
            self._only(method, "POST")
            d = body.get("definition", body)
            return estimate(validate_definition(copy.deepcopy(d))), 200, False, ""

        # segments
        if parts == ["segments"]:
            if method == "GET":
                cursor = int_param(q, "cursor", 0, 0, 10 ** 6)
                limit = int_param(q, "limit", SEGMENT_PAGE, 1, SEGMENT_MAX)
                segs = [s for s in DB["segments"]
                        if (not q.get("q") or matches(q["q"], s["name"], s["description"]))
                        and (not q.get("team") or s["owner_team"].lower() == q["team"].lower())]
                if q.get("q"):
                    segs.sort(key=lambda s: -score(q["q"], s["name"], s["description"]))
                page = segs[cursor:cursor + limit]
                nxt = cursor + limit if cursor + limit < len(segs) else None
                return {"total": len(segs), "items": [seg_summary(s) for s in page], "next_cursor": nxt}, 200, False, ""
            self._only(method, "POST")
            name = body.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ApiError(400, "name is required and must be a non-empty string")
            name = name.strip()
            desc = body.get("description", "")
            if not isinstance(desc, str):
                raise ApiError(400, "description must be a string")
            if "definition" not in body:
                raise ApiError(400, "definition is required")
            d = validate_definition(copy.deepcopy(body["definition"]))
            with WRITE_LOCK:
                if any(s["name"].lower() == name.lower() for s in DB["segments"]):
                    raise ApiError(409, f"a segment named '{name}' already exists")
                seg = {"id": f"seg-{len(DB['segments']) + 1:03d}", "name": name, "description": desc,
                       "owner_team": "Audience Desk", "restricted": False, "definition": d,
                       "created_at": today(), "updated_at": today()}
                DB["segments"].append(seg)
            out = seg_full(seg)
            return out, 201, True, f"created {seg['id']} '{name}' (~{out['estimated_households']:,} households)"
        if len(parts) == 2 and parts[0] == "segments":
            seg = find_segment(parts[1])
            if method == "GET":
                if not seg:
                    raise ApiError(404, f"no segment with id '{parts[1]}'")
                return seg_full(seg), 200, False, ""
            if method == "DELETE":
                raise ApiError(405, "deleting segments is not supported through this API")
            self._only(method, "PATCH")
            if not seg:
                raise ApiError(404, f"no segment with id '{parts[1]}'")
            if seg["restricted"]:
                raise ApiError(403, f"'{seg['name']}' is restricted to {seg['owner_team']}; changes go through that team")
            unknown = sorted(set(body) - {"name", "description", "definition"})
            if unknown:
                raise ApiError(400, f"unknown fields: {unknown}", allowed=["name", "description", "definition"])
            if not body:
                raise ApiError(400, "nothing to update: send name, description or definition")
            new_name = seg["name"]
            if "name" in body:
                if not isinstance(body["name"], str) or not body["name"].strip():
                    raise ApiError(400, "name must be a non-empty string")
                new_name = body["name"].strip()
            if "description" in body and not isinstance(body["description"], str):
                raise ApiError(400, "description must be a string")
            patch = validate_definition(copy.deepcopy(body["definition"]), partial=True) if "definition" in body else {}
            with WRITE_LOCK:
                if new_name.lower() != seg["name"].lower() and any(
                        s["name"].lower() == new_name.lower() for s in DB["segments"]):
                    raise ApiError(409, f"a segment named '{new_name}' already exists")
                seg["name"] = new_name
                if "description" in body:
                    seg["description"] = body["description"]
                seg["definition"].update(patch)
                seg["updated_at"] = today()
            out = seg_full(seg)
            return out, 200, True, f"updated {seg['id']} '{seg['name']}' (~{out['estimated_households']:,} households)"

        raise ApiError(404, f"no route for {method} /{'/'.join(parts)}")

    @staticmethod
    def _only(method, allowed):
        if method != allowed:
            raise ApiError(405, f"method {method} not allowed here; use {allowed}")

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


def main():
    port = DEFAULT_PORT
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            sys.exit("usage: python3 server.py [--port N]")
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), "event": "server started",
                            "port": port}) + "\n")
    srv = Server(("127.0.0.1", port), Handler)
    print(f"Audiences API running on http://127.0.0.1:{port}   key: {API_KEY}")
    print(f"{len(DB['content'])} titles, {len(DB['segments'])} segments loaded. Requests are logged below and to api-calls.jsonl.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
