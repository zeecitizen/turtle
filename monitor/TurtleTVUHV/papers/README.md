# 📄 Research · from paper to EA setting

The **Research** tab of Turtle TV (http://127.0.0.1:8773 → `📄 Research`) turns a
research-paper PDF into a candidate saved setting for `Saad_strategy_15min`, judged
in MT5. Zee's request, verbatim:

> Build a page on turtle tv called : Research (similar to Dexter's Lab page and others in the menu) -> on this page: 1. i can upload a research paper PDF 2. Button : Create saved setting out of Research paper 3. List of research papers in the system with their overview (winrate in MT5 etc) -> has a Button Save this new setting to settings. when i press the button, it calls Claude Fable 5.1 at high with Ultra Code to build an EA from our default saved setting + new knowledge from the research paper (e.g. new exit etc) -> then it validates its implemented EA settings extracted from research paper in MT5 and populates and saves the research paper under list 3. given above in bullets. the idea is that i zeeshan reads a research paper on the internet -> downloads it -> gives it to claude via this webpage to parse and build into an EA and test and validate and finally save the results in a list from which i can then pick it up by clicking Save setting which then brings it to our saved settings (or asks to invoke Claude to help saving it if it requires additional code in our EA settings ) -> in saved settings we can mark the settings from research papers with their research paper name etc to know that this one came from a research paper

This folder (`monitor/saad_view/papers/`) is the whole machine behind that tab:

| File | Owner | What |
|---|---|---|
| `job.py` | server side | runs one headless Claude job for one paper (`python papers/job.py <id> [--base NAME] [--dry] [--notes TEXT]`) |
| `PROMPT.md` | server side | the prompt template the job fills and sends to Claude (`{placeholders}`) |
| `store/<id>/` | job + server | one folder per uploaded paper (layout below) |
| `README.md` | this file | the protocol for humans **and** for the headless Claude |
| `selftest.py` | QA | HTTP end-to-end test in dry mode (`python papers/selftest.py`) |

The endpoints live in `monitor/saad_view/server.py`; the page in
`monitor/saad_view/static/research.js` (`pResearch()`).

Project rules that bind everything here (they are also in the repo's `CLAUDE.md`,
which the headless Claude reads automatically because its cwd is the repo root):

* **Python numbers are a hypothesis. Only MT5 promotes.** Every Turtle TV tester
  figure on the page and in `result.json` is labelled *hypothesis*; the MT5
  random-delay column is the verdict.
* New EA behaviour defaults **OFF**, bumps the version, and gets its
  `VERSION_HISTORY.md` + `VERSION.md` rows. **Agents never commit.**
* `LAWS.md` is Zeeshan's. Read-only.
* Never touch the live MT5 terminal (PID 19700). Rigs `axi5`, `axi6` are for
  validation, `axi4` for compiles.

---

## 1. End to end

```
Zee downloads a PDF
   │
   ▼  (1) upload  ──────────────  POST /api/research_upload {name, b64}
store/<id>/paper.pdf + paper.txt (pypdf) + meta.json {status: uploaded}
   │
   ▼  (2) build  ───────────────  POST /api/research_build {id, base?, notes?, dry?}
papers/job.py runs claude.exe headless (Claude Fable 5.1, LOW effort, no ultracode - switched 2026-11-02 to save credits)
   ├─ reads the paper, lists its ideas, maps each to EA inputs / new code
   ├─ starts from the base saved setting, builds candidates in the Turtle TV tester (hypothesis)
   ├─ if new EA code is needed: input defaulting OFF in mt5/Saad_strategy_15min.mq5
   │     + make_view_ea.py + compile on axi4 + VERSION rows (no commit)
   ├─ drops the candidate into settings/saved/"<id> candidate.json"
   ├─ MT5-validates it: research/mt5_years.py axi5,axi6 "save:<id> candidate" 2023,2024,2025,2026 none,random
   └─ writes store/<id>/result.json + setting.json, meta.json {status: done|failed}
   │
   ▼  (3) list  ────────────────  GET /api/research
the page shows title · summary · ideas · tester-vs-MT5 table · verdict per paper
   │
   ▼  (4) save  ────────────────  POST /api/research_save {id}
settings/saved/"<stamp> 📄 <short title>.json" with "source": {kind: research_paper, ...}
→ the saved-settings table shows a 📄 badge with the paper's name
   │
   ▼  (5) optional assist  ─────  POST /api/research_assist {id}
if result.needs_code.required: a second Claude job implements the EA code the candidate needs
```

Phases the page shows while a job runs (`meta.phase`): `starting` → `reading` →
`mapping` → `tester` → `code` (only if needed) → `mt5` → `writing` → `done` /
`failed`. The job sets them from Claude's own progress lines; a job that dies
without reaching `writing` is `failed` with `error` filled in.

---

## 2. Store layout

```
monitor/saad_view/papers/store/<id>/
    paper.pdf        the upload, byte for byte
    paper.txt        pypdf text, written at upload (fallback for the Claude Read tool)
    meta.json        {id, file, title, uploaded, pages, base_setting, status, phase,
                      started, finished, error, exit_code, dry}
    prompt.md        the exact prompt sent to Claude (PROMPT.md with placeholders filled)
    log.jsonl        claude --output-format stream-json, one JSON object per line
    log.txt          human-readable tail: assistant text + tool names (what /api/research_log serves)
    result.json      written BY THE CLAUDE JOB — the contract in §3
    setting.json     the candidate saved setting (settings/saved schema + "source")
```

`id` = `YYYY-MM-DD HH-MM-SS-<slug>` where slug is the file name reduced to safe
ASCII (`[A-Za-z0-9._-]`), at most 40 characters, **no commas** (the ids become
MT5 gate names and `mt5_years.py` splits its gate list on commas).

`meta.status` ∈ `uploaded | running | done | failed`.

`title` = first non-empty line of `paper.txt`, else the file name. The job may
overwrite it in `result.json` with the paper's real title.

---

## 3. The `result.json` contract (verbatim)

The job writes it; the page renders it; a missing key renders as `–`. Keys and
shapes are fixed so the three parts (server, page, job) fit without talking.

```
{
  "id":       "<store id>",
  "title":    "<paper title>",
  "authors":  "<authors, one string>",
  "year":     2025,
  "summary":  "<= 120 words",
  "ideas": [
    { "idea": "<one idea from the paper>",
      "where": "entry | exit | sizing | filter | other",
      "implementable": true | false | "needs_code",
      "mapping": "<which EA inputs carry it, or what new code would>" }
  ],
  "base_setting": { "name": "<saved setting name>", "result": { ...its result block... } },
  "setting": {
    "name": "<candidate name, no commas>",
    "inputs": { "<EA input>": "<value as string>", ... 181 of them ... },
    "changed": { "<input that differs from the EA defaults>": "<value>" },
    "note": "<what the paper changed and why>",
    "ds": "m15", "mode": "ea"
  },
  "needs_code": {
    "required": false,
    "version":  "<EA version that carries the new input, e.g. 1.40>",
    "files":    ["mt5/Saad_strategy_15min.mq5", "monitor/saad_view/make_view_ea.py"],
    "inputs":   ["InpNewThing"],
    "summary":  "<what the code does>"
  },
  "tester": {                                   HYPOTHESIS - Turtle TV tester (Python)
    "n": 0, "wr": 0.0, "net": 0.0, "pf": 0.0, "worst_loss": 0.0, "dd": 0.0,
    "per_year": { "2023": { "n": 0, "wr": 0.0, "net": 0.0 }, ... }
  },
  "mt5": {                                      THE JUDGE - MT5 Strategy Tester
    "rows": [ { "year": 2023, "delay": "none|random", "trades": 0, "net": 0.0,
                "wr": 0.0, "worst": 0.0, "pf": 0.0 }, ... ],
    "total_none":   { "trades": 0, "net": 0.0, "wr": 0.0 },
    "total_random": { "trades": 0, "net": 0.0, "wr": 0.0 }
  },
  "base_mt5": { same shape as "mt5", for the base setting
                (reuse research/mt5_years.json rows when present) },
  "verdict":  "<one paragraph: does the paper's idea improve the base in MT5 under
               random delay, honestly; Python numbers = hypothesis>",
  "status":   "done | failed",
  "built":    "<ISO timestamp>",
  "dry":      true            (only present when the job ran with --dry)
}
```

Units: `net`, `worst`, `worst_loss`, `dd` in account dollars at the validation
size ($100k, 2 lots for MT5; the tester's own size for `tester`); `wr` in percent
(97.2 not 0.972); `year` an integer.

`setting` must be a complete saved-setting file (same schema as
`settings/saved/*.json`: `name, inputs, changed, ds, mode, result, lab,
lab_describe, note`) so that `/api/research_save` can copy it as-is and the
Turtle TV page can load it like any other save.

---

## 4. How the headless Claude is invoked

`job.find_claude()` picks the newest
`C:\Users\zeesh\.vscode\extensions\anthropic.claude-code-*-win32-*\resources\native-binary\claude.exe`
(2.1.314 at the time of writing) and falls back to `claude` on `PATH` — the VM
has a different install, so the path is detected at runtime, never hard-coded.
`GET /api/research` reports `claude: {exe, found}` so the page can say up front
when nothing is there.

The command the job runs, cwd = repo root `C:\Users\zeesh\turtle`:

```
claude.exe -p "<prompt>" \
   --model claude-fable-5-1 --effort low \
   --permission-mode acceptEdits \
   --allowedTools "Bash Read Write Edit Glob Grep Workflow Agent ToolSearch WebSearch WebFetch" \
   --disallowedTools "Bash(git commit*) Bash(git push*)" \
   --output-format stream-json --verbose \
   --add-dir C:\Users\zeesh\turtle\monitor\saad_view\papers\store\<id> \
   --append-system-prompt "<the rules: Fable 5.1 low effort, no commit/push, no live terminal, LAWS.md read-only>"
```

* The prompt no longer contains the word ultracode (removed 2026-11-02: credits) — it used to switch on multi-agent
  orchestration (the Workflow tool) for the session.
* stdout is one JSON object per line → appended to `log.jsonl`; assistant text and
  tool names are also appended to `log.txt`, which is what the page tails.
* The job's `meta.exit_code` is Claude's exit code; `error` gets the last
  `error`/`result.is_error` message from the stream.

### What the prompt makes Claude do (PROMPT.md, in order)

1. Read `paper.pdf` (the Read tool handles PDFs; `paper.txt` is the fallback).
2. Summarise; list the ideas; map each to EA inputs that already exist vs new code.
3. Start from the base setting's inputs; build the candidate(s) in the Turtle TV
   tester from Python (`sim.simulate(server.full_inputs(inputs), ds='m15')`);
   keep the stop/TP geometry unless the paper is about exits — and say so.
4. If new EA code is needed: add it as an input defaulting OFF to
   `mt5/Saad_strategy_15min.mq5` + `make_view_ea.py`, compile on `axi4`
   (`monitor/strategy_lab/axi_rig.compile_ea(ea, rig='axi4')`), write the
   `VERSION_HISTORY.md` + `VERSION.md` rows. **No commit.**
5. Write `setting.json`; drop the same candidate into `settings/saved/"<id>
   candidate.json"`; MT5-validate with
   `python monitor/saad_view/research/mt5_years.py axi5,axi6 "save:<id> candidate" 2023,2024,2025,2026 none,random`
   (M15 chart, XAUUSD_BB3 2023-25 / XAUUSD_BB 2026, $100k, 2 lots; rows appended
   to `research/mt5_years.json`). The candidate file may stay in `settings/saved/`;
   the Save button writes the final provenance copy and must work whether or not
   the candidate file is still there.
6. Write `result.json` per §3 — every Python number labelled a hypothesis, the MT5
   random-delay column quoted as the verdict.
7. Print a 3-line summary.

---

## 5. Running a job by hand

```
cd C:\Users\zeesh\turtle\monitor\saad_view
set PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe

# real job (20-90 minutes; uses the 5-hour budget)
%PY% papers\job.py "<id>" --base "2026-11-01 08-38-10" --notes "focus on the exit idea in section 4"

# dry run: no Claude, writes a complete fake result.json + setting.json marked "dry": true
%PY% papers\job.py "<id>" --dry
```

Re-running a job on the same id overwrites `prompt.md`, `log.*`, `result.json`,
`setting.json` and resets `meta.status`. The upload (`paper.pdf`, `paper.txt`) is
never touched. To re-validate only, run `mt5_years.py` directly with the
`save:<id> candidate` gate, or with the new `file:<path>` gate (any saved-setting
JSON by path, e.g. `file:monitor/saad_view/papers/store/<id>/setting.json`).

Dry mode is also reachable over HTTP: `POST /api/research_build {id, dry: true}`.
The server must honour that field (it is what `selftest.py` relies on); a dry job
finishes in seconds and its result carries `"dry": true` so nobody mistakes it
for a validated paper.

---

## 6. Endpoints

| Method · path | Body | Returns |
|---|---|---|
| GET `/api/research` | – | `{papers: [meta + result (if any) + has_setting], running: {id, phase, seconds} \| null, claude: {exe, found}, bases: [saved names], default_base}` |
| POST `/api/research_upload` | `{name, b64}` | `{ok, id, title, pages}` |
| POST `/api/research_build` | `{id, base?, notes?, dry?}` | `{ok, id}` or `{error}` (busy / claude.exe missing / unknown id) |
| GET `/api/research_log?id=` | – | `{lines: [last 200 lines of log.txt], status}` |
| POST `/api/research_stop` | `{id}` | `{ok}` — kills the process, status `failed`, error `stopped` |
| POST `/api/research_save` | `{id}` | `{ok, name, needs_code}` — the saved-settings copy with provenance |
| POST `/api/research_assist` | `{id}` | `{ok}` — second Claude job: implement `needs_code` |
| POST `/api/research_delete` | `{id}` | `{ok}` — removes `store/<id>/` (not any saved-settings copy) |

`default_base` = the newest saved setting whose name contains `standard`, else
`2026-11-01 08-38-10`.

---

## 7. Provenance in saved settings

`/api/research_save` writes `settings/saved/"<stamp> 📄 <short title>.json"` =
`setting.json` plus

```
"source": {
  "kind":       "research_paper",
  "paper":      "<title>",
  "id":         "<store id>",
  "pdf":        "<original file name>",
  "built":      "<result.built>",
  "needs_code": { ...result.needs_code... }
}
```

The saved-settings table (`static/app.js`) shows a `📄 <paper>` badge on such rows
(title attribute = id + built). That is how Zee knows which saves came from a
paper, and from which one.

### `needs_code`

`needs_code.required: true` means the candidate's inputs refer to EA behaviour that
does not exist yet in the shipped `Saad_strategy_15min.mq5`, or exists only in the
uncommitted working tree. The setting is still saved (the provenance copy records
the gap), and the page shows a warning with **🤖 ASK CLAUDE TO IMPLEMENT THE EA
CODE** → `/api/research_assist`. The assist job is a second headless Claude run
whose prompt is "implement the EA code the candidate needs" from
`result.needs_code`: new input(s) defaulting OFF, version bump, `make_view_ea.py`,
compile on `axi4`, VERSION rows, no commit. It logs into the same `store/<id>/`
(`assist_log.*`) and updates `needs_code` in `result.json` when done.

---

## 8. Limits

* **One job at a time.** `/api/research_build` and `/api/research_assist` answer
  `{error: "busy"}` while any research job runs (the MT5 rigs and the Claude
  budget are shared). Check `GET /api/research → running`.
* **The 5-hour usage limit.** A run can end with *"You've hit your 5-hour limit"*;
  the job marks the paper `failed` with that text in `meta.error`, and the page
  shows it as a clear error with a **Retry** button. Nothing is lost: the upload
  stays, re-build later.
* **20-90 minutes per paper** is normal (reading + tester + compile + four years of
  MT5 twice). Dry mode: seconds.
* **The VM path difference.** On the VM, Claude Code is not under
  `.vscode\extensions\...`; `find_claude()` falls back to `claude` on `PATH`. If
  `GET /api/research → claude.found` is false, install or add it to `PATH`.
* **Nothing is committed by any agent.** EA edits, VERSION rows and the candidate
  save sit in the working tree for Zee to review and commit.
* **No commas** in ids, candidate names or saved names that will be MT5 gates.
* The server restart after a server-side change: stop the `pythonw server.py`
  processes, `cd C:\Users\zeesh\turtle && start pythonw monitor\saad_view\server.py`
  — after checking `GET /api/status` that no opt / exitlab / mission job is running.

---

## 9. Self-test

```
%PY% monitor\saad_view\papers\selftest.py              # against http://127.0.0.1:8773
%PY% monitor\saad_view\papers\selftest.py --schema     # just print the result.json key schema
%PY% monitor\saad_view\papers\selftest.py --keep       # leave the store entry + saved file for inspection
```

Steps, each printed PASS/FAIL (exit 1 on any FAIL): upload the example PDF
(`C:\Users\zeesh\turtle\research\HierarchicalExecutionArchitecturesinTransformer-DrivenAlgorithmicTrading.pdf`,
11 pages) → store entry + non-empty `paper.txt` + title → dry build → poll until
`done` (≤ 60 s) → `result.json` keys → save → saved file exists with
`source.kind == research_paper` and `GET /api/saved` lists it with the badge data →
delete → remove the saved test file. It never runs the real Claude job.
