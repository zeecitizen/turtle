"""papers - Turtle TV's Research page (Zee 2026-11-01: "i zeeshan reads a research paper on the internet -> downloads it -> gives it to claude via
this webpage to parse and build into an EA and test and validate and finally save the results in a list").

store/<id>/   one folder per uploaded paper: paper.pdf, paper.txt, meta.json, prompt.md, log.jsonl, log.txt, result.json, setting.json
job.py        the runner: find_claude(), build_prompt(), run(id, base, notes, dry), stop(id), state()
PROMPT.md     the instruction the headless Claude Fable 5.1 follows (placeholders {LIKE_THIS}); PROMPT_ASSIST.md = the "implement the EA code" job
README.md     the protocol for humans and for the headless Claude (agent J); selftest.py = HTTP end-to-end test in dry mode
"""
