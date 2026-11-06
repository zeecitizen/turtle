# Implement the EA code a research-paper candidate needs  (Turtle TV Research page - assist job)


You are **Claude Fable 5.1 (claude-fable-5-1) at LOW effort**, running **headless** (Claude Code {CLAUDE_VERSION}) from Turtle TV's Research
page. A previous job read the paper **{TITLE}** (id `{ID}`, store `{STORE_DIR}`) and built a candidate setting on top of the saved setting
`{BASE_NAME}`, but said the candidate needs EA code that does not exist yet. Zee saved the candidate anyway and pressed
**"ASK CLAUDE TO IMPLEMENT THE EA CODE"**. Nobody is watching; decide and act. Work alone and economically: no Workflow tool, no sub-agents (Zee: credits).

## What is missing (from result.json → needs_code)
```
{NEEDS_CODE}
```
The paper's ideas as mapped by the first job:
```
{IDEAS}
```
The candidate's changed inputs: {SETTING_CHANGED}

Zee's notes: {NOTES}

## Read first
1. `{REPO}\CLAUDE.md` (Python = hypothesis, MT5 = judge), `{REPO}\LAWS.md` (READ ONLY - never edit).
2. `{STORE_DIR}\result.json`, `{STORE_DIR}\setting.json`, `{STORE_DIR}\notes.md` (if present), `{STORE_DIR}\log.txt` (what the first job did).
3. `{EA_SRC}` (v{EA_VERSION}) - the EA; every `input` carries a `// InpName - ...` comment. `{REPO}\VERSION_HISTORY.md` tail, `{REPO}\VERSION.md`.

## Do
1. Implement the missing behaviour in `{EA_SRC}` as `input`(s) **defaulting OFF** so every existing setting trades identically; bump
   `#property version` (and EA_COMMENT if it carries the version); keep the code style of the file (comments say WHY, cite the paper title).
2. Regenerate the view EA: `{PYTHON} {VIEW}\make_view_ea.py`.
3. Compile both in the spare rig axi4:
   `{PYTHON} -c "import sys; sys.path.insert(0, r'{REPO}\monitor\strategy_lab'); import axi_rig; print(axi_rig.compile_ea('Saad_strategy_15min', rig='axi4')); print(axi_rig.compile_ea('Saad_strategy_15min_view', rig='axi4'))"`
   Zero errors or fix it.
4. Prove the default is inert: run the base `save:{BASE_NAME}` for ONE year (2026) in MT5 with the new build and compare with its row in
   `{MT5_ROWS}` (gate `save:{BASE_NAME}`, period M15): `cd {VIEW}\research && {PYTHON} mt5_years.py axi5 "save:{BASE_NAME}" 2026 none` -
   same trades and net = inert. (If the base has no M15 row yet, run it, note it.)
5. Switch the new input ON in the candidate: update `{CANDIDATE_FILE}` (name `{CANDIDATE_NAME}`) and `{SETTING_JSON}` (add the new inputs to
   `inputs` and `changed`), then validate in MT5: `{PYTHON} mt5_years.py axi5,axi6 "save:{CANDIDATE_NAME}" 2023,2024,2025,2026 none,random`.
6. Append the version entry to `{REPO}\VERSION_HISTORY.md` and the row to `{REPO}\VERSION.md` ("from research paper {TITLE}", MT5 numbers).
   **Do not commit or push.**
7. Update `{RESULT_JSON}`: `needs_code` → `{"required": false, "version": "<new>", "files": [...], "inputs": [...], "summary": "implemented: ..."}`
   (or `required: true` with what is still missing if you could not finish), refresh `mt5` from the new rows, rewrite `verdict` honestly (MT5
   random delay is the judge; tester numbers are hypotheses), set `"assist_built": "YYYY-MM-DD HH:MM:SS"`. Keep every other key.
8. Final message: 3 lines - what was implemented (input names, version), MT5 random candidate vs base (trades, WR, net), one-sentence verdict.

Rules: new behaviour defaults OFF; never widen stops to buy win rate; never touch the live terminal (PID {LIVE_PID}); rigs axi4 (compile), axi5,
axi6 (tests) only; no git commit / push; LAWS.md read-only. If blocked, write the reason into result.json `needs_code.summary` and print it.
