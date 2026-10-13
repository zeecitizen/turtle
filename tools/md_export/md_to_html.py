"""Markdown -> styled single-page HTML for a claude.ai Artifact (used by the /export-md skill).

    py tools/md_export/md_to_html.py <file.md>
prints JSON: {"html": <output path>, "url": <existing artifact URL or null>, "title": ...}

Per-file settings live in tools/md_export/links.json, keyed by the markdown path relative to the repo:
    {"report.md": {"url": "https://claude.ai/artifact/...", "title": "...", "eyebrow": "...",
                   "subtitle": "...", "facts": [["label", "value"], ...]}}
Anything missing falls back to: title = the first H1, subtitle = the first paragraph if it is in italics.
The HTML goes to tools/md_export/out/<name>.html (a stable path, so republishing keeps the same link)."""
import html, json, re, sys
from pathlib import Path
import markdown

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LINKS = HERE / "links.json"


def build(md_path: Path, cfg: dict) -> str:
    src = md_path.read_text(encoding="utf-8")
    m = re.search(r"^# (.+)$", src, re.M)
    h1 = m.group(1).strip() if m else md_path.stem
    if m: src = src[:m.start()] + src[m.end():]
    sub = cfg.get("subtitle")
    if sub is None:
        it = re.match(r"\s*\*([^*\n][^*]*?)\*\s*\n", src)
        if it: sub, src = it.group(1).replace("\n", " "), src[it.end():]
    title = cfg.get("title") or re.split(r"\s+[—–-]\s+", h1)[0]
    body = markdown.markdown(src, extensions=["tables", "fenced_code", "sane_lists"])
    toc = []

    def h2(mm):
        t = re.sub("<[^>]+>", "", mm.group(1)); n = len(toc)
        num = re.match(r"(\d+)\.\s*(.*)", t)
        label = f"<b>{num.group(1)}</b> {html.escape(num.group(2))}" if num else html.escape(t)
        toc.append(f'<a href="#s{n}">{label}</a>')
        return f'<h2 id="s{n}">{mm.group(1)}</h2>'

    body = re.sub(r"<h2>(.*?)</h2>", h2, body)
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>").replace("<hr />", "")
    facts = "".join(f"<span>{html.escape(k)} <b>{html.escape(v)}</b></span>" for k, v in cfg.get("facts", []))
    eyebrow = html.escape(cfg.get("eyebrow", md_path.name))
    nav = f'<nav aria-label="Sections">{"".join(toc)}</nav>' if len(toc) > 1 else ""
    cols = "250px minmax(0, 1fr)" if nav else "minmax(0, 1fr)"
    return f"""<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Manrope:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* layout: sticky section index on the left, one reading column; tables scroll inside their own frame */
:root {{
  --bg: #f6f7f9; --panel: #ffffff; --ink: #1b2230; --muted: #5d6676; --line: #dfe3ea;
  --gold: #a87412; --gold-soft: #f6ead2; --code: #eef1f5;
  --display: "Bricolage Grotesque", "Segoe UI", system-ui, sans-serif;
  --body: "Manrope", "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #11151c; --panel: #171c25; --ink: #e6e9ef; --muted: #9aa3b2; --line: #2a3140;
  --gold: #e0ad4f; --gold-soft: #2c2415; --code: #1f2633; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #11151c; --panel: #171c25; --ink: #e6e9ef; --muted: #9aa3b2; --line: #2a3140;
  --gold: #e0ad4f; --gold-soft: #2c2415; --code: #1f2633; color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--ink); font: 15px/1.62 var(--body); }}
.wrap {{ max-width: 1240px; margin: 0 auto; padding-inline: 20px; padding-block: 28px 64px;
  display: grid; grid-template-columns: {cols}; gap: 40px; }}
header.top {{ grid-column: 1 / -1; border-bottom: 2px solid var(--gold); padding-bottom: 18px; }}
.eyebrow {{ font: 600 12px/1 var(--mono); letter-spacing: .12em; text-transform: uppercase; color: var(--gold); }}
h1 {{ font: 800 clamp(28px, 4vw, 44px)/1.08 var(--display); margin: 10px 0 8px; text-wrap: balance; }}
.sub {{ color: var(--muted); max-width: 70ch; margin: 0; }}
.facts {{ display: flex; flex-wrap: wrap; gap: 10px 28px; margin-top: 16px; font: 13px var(--mono); }}
.facts:empty {{ display: none; }}
.facts span b {{ color: var(--gold); font-weight: 600; }}
nav {{ position: sticky; top: calc(env(safe-area-inset-top, 0px) + 16px); align-self: start; max-height: calc(100vh - 32px); overflow: auto;
  font-size: 13px; line-height: 1.35; display: flex; flex-direction: column; gap: 2px; }}
nav a {{ color: var(--muted); text-decoration: none; padding: 6px 8px; border-radius: 6px; display: flex; gap: 8px; }}
nav a b {{ font: 600 12px var(--mono); color: var(--gold); min-width: 1.6em; }}
nav a:hover, nav a:focus-visible {{ background: var(--gold-soft); color: var(--ink); outline: none; }}
main {{ min-width: 0; }}
main > p, main > ul, main > ol, main > blockquote, main > h3, main > h4 {{ max-width: 78ch; }}
h2 {{ font: 700 clamp(21px, 2.4vw, 27px)/1.2 var(--display); margin: 56px 0 14px; padding-top: 14px; border-top: 1px solid var(--line); text-wrap: balance; scroll-margin-top: 16px; }}
main > h2:first-child {{ margin-top: 0; }}
h3 {{ font: 700 17px/1.3 var(--body); margin: 30px 0 10px; }}
p {{ margin: 0 0 12px; }} ul, ol {{ margin: 0 0 14px; padding-left: 22px; }} li {{ margin: 3px 0; }}
a {{ color: var(--gold); }}
code {{ font: 0.86em var(--mono); background: var(--code); padding: 1px 5px; border-radius: 4px; }}
pre {{ background: var(--code); padding: 12px 14px; border-radius: 8px; overflow-x: auto; }}
pre code {{ background: none; padding: 0; }}
blockquote {{ margin: 16px 0; padding: 12px 16px; background: var(--gold-soft); border-left: 3px solid var(--gold); border-radius: 0 8px 8px 0; }}
blockquote p {{ margin: 0; }}
.tw {{ overflow-x: auto; margin: 12px 0 20px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel); }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; font-variant-numeric: tabular-nums; }}
th, td {{ padding: 8px 12px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); }}
th {{ font: 600 12px/1.3 var(--body); color: var(--muted); text-transform: uppercase; letter-spacing: .04em; background: var(--code); white-space: nowrap; }}
tr:last-child td {{ border-bottom: 0; }}
td strong {{ color: var(--gold); }}
@media (max-width: 860px) {{
  .wrap {{ grid-template-columns: minmax(0, 1fr); gap: 20px; }}
  nav {{ position: static; max-height: none; flex-direction: row; flex-wrap: wrap; }}
  nav a {{ border: 1px solid var(--line); }}
}}
@media (prefers-reduced-motion: no-preference) {{ html {{ scroll-behavior: smooth; }} }}
</style>
<div class="wrap">
  <header class="top">
    <div class="eyebrow">{eyebrow}</div>
    <h1>{html.escape(cfg.get("heading", title))}</h1>
    {f'<p class="sub">{markdown.markdown(sub)[3:-4]}</p>' if sub else ''}
    <div class="facts">{facts}</div>
  </header>
  {nav}
  <main>{body}</main>
</div>
"""


if __name__ == "__main__":
    md = Path(sys.argv[1])
    if not md.is_absolute(): md = (Path.cwd() / md).resolve()
    if not md.exists():
        hits = [p for p in REPO.rglob(md.name) if ".git" not in p.parts]     # "export readme.md" from anywhere
        if not hits: sys.exit(f"not found: {sys.argv[1]}")
        md = hits[0]
    key = md.relative_to(REPO).as_posix() if md.is_relative_to(REPO) else str(md)
    links = json.loads(LINKS.read_text(encoding="utf-8")) if LINKS.exists() else {}
    cfg = links.get(key, {})
    out = HERE / "out" / (re.sub(r"[^A-Za-z0-9_.-]+", "_", key.rsplit(".", 1)[0]) + ".html")
    out.parent.mkdir(exist_ok=True)
    page = build(md, cfg)
    out.write_text(page, encoding="utf-8")
    print(json.dumps({"key": key, "html": str(out), "url": cfg.get("url"), "title": re.search(r"<title>(.*?)</title>", page).group(1)}))
