---
name: export-md
description: Publish a Markdown file from this repo (e.g. report.md, README.md) as a styled claude.ai Artifact web page, keep the same link on every re-export, and copy the link to the clipboard. Use when Zee says "export <file>.md", "/export-md <file>", "publish report.md", or asks for a link to a .md file.
argument-hint: <file.md>
---

# Export a Markdown file as a claude.ai page

Argument: the Markdown file (`$ARGUMENTS`). If none was given, use `report.md`.

1. **Build the page.** Run:
   ```
   C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe tools/md_export/md_to_html.py <file.md>
   ```
   It prints JSON: `html` (the page to publish), `url` (the existing link, or null), `key`, `title`.
   If it says "not found", tell Zee and stop. If `markdown` is missing, `pip install markdown` and rerun.

2. **Publish with the Artifact tool.**
   - `url` is set: publish `file_path` = `html` with `url` = that link, so the link stays the same. Omit
     `icon`. If the publish is refused because this conversation has not read the artifact, read it
     (`action: "read"`, `url`), then publish again with the same `file_path` and `url`.
   - `url` is null: publish `file_path` = `html` with `icon: "document"` and a one-sentence `description`.
     Then add the new link to `tools/md_export/links.json` under `key` (`{"url": "<link>"}`).

3. **Copy the link to the clipboard:**
   ```
   printf '%s' '<link>' | clip.exe
   ```

4. **Reply in one or two lines:** the link, "copied to clipboard", and whether it was a new page or an
   update. Artifacts are private: if Zee wants a public link, he turns it on from the page's **Share** menu
   (Claude cannot change sharing).

The page builder only reads the file. Don't edit the Markdown itself as part of an export.
