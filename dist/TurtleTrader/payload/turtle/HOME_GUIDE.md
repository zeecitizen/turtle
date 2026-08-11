# 🏠 home.claudezeeshan.com — User Guide

Welcome to your personal AI home, Zeeshan. This doc explains every feature, how to use it, and what's under the hood.

Built: 2026-06-28 (4:15 AM → 6:45 AM PKT)
Version: 1.0 (Phases 1-6 complete + improvements)
Maintainer: Claude

---

## 🌐 1. Where to access (globally)

| Where you are | URL |
|---|---|
| **Any browser, anywhere** | https://home.claudezeeshan.com |
| Direct path on apex | https://claudezeeshan.com/home |
| Local machine (laptop) | http://localhost:3457/home |
| Local machine (VPS) | http://localhost:3457/home (after RDP) |

Works on: phone, laptop, tablet, friend's PC, work PC, hotel WiFi, anywhere with internet. No app to install. No login screen forced at page load.

---

## 🔐 2. Authentication — TWO ways to unlock

### A. The code word (primary)
Type into the auth box:
```
Zeeshan here 28973
```
Click **Unlock**. Done. Cookie valid 7 days.

### B. Memory challenge (backup)
If you type wrong code, the box will ask a question only you would know:
- "What is the name of Zeeshan's real brother — the one who manages the EA?"
- "Mother's hospital surgery — what's the north-star USD amount?"
- "Foundational doctrine — what do backtests do?"
- (8 questions total, randomized)

Answer with one word/number. Fuzzy match (case-insensitive). If wrong, you get a different question. Keeps cycling until you answer correctly OR type the code.

### Role states
- **guest** (default): see 97 public memory files, see live EA strip, see work history page
- **admin_zeeshan** (authenticated): see 106 memory files (9 private unlocked), chat box appears, RAG retrieval per query

### Logout
Click the gold button (now showing "Logout" when authenticated). Cookie cleared.

---

## 📚 3. Memory browser (sidebar)

Left sidebar lists every memory file. Each is a markdown document about something we learned together.

| Action | How |
|---|---|
| **Search** | type in the search box — matches name + description |
| **Filter by category** | click "Project", "Doctrine", "Ref" tabs |
| **Read a memory** | click any item in the list |
| **See private 🔒** | unlock as admin first |

Categories explained:
- **Project** — `project_*.md` (EA versions, infrastructure, decisions)
- **Doctrine** — `feedback_*.md` (rules, principles, what we believe)
- **Reference** — `reference_*.md` (external systems, contact lookups)
- **Memory** — `memory_*.md` (encrypted soul memories, etc.)

---

## 💬 4. Chat with Claude (the heart of the home)

After authentication, the chat box appears. Every message you send:

1. **RAG retrieval**: TF-IDF index finds top-6 most relevant memory files
2. **Context injection**: those memories become part of Claude's system prompt
3. **Doctrine guard rails**: hospital-fund north star, no-spin, no sexual content (always)
4. **Streaming response**: Claude's reply appears word-by-word (no waiting)
5. **Conversation memory**: last 40 turns saved in browser localStorage

### Chat features

| Button | What it does |
|---|---|
| **Send** (gold) | submit message |
| **🎙️ mic** | voice input (browser Web Speech API) |
| **🔇/🔊 Speak** | toggle — Claude reads replies aloud |
| **⬇ Export** | download conversation as `.md` file |
| **Clear** | wipe localStorage history |

### Keyboard
- `Enter` — send
- `Shift+Enter` — newline

### Cost meter
Bottom-right of chat box shows: `Session tokens: X in · Y out · ~$0.0000`
Rough cost at Sonnet 4.6 rates: ~$0.005 per quick reply.

### What memories get loaded per message
Shown beneath each reply: `Context loaded: <file1>, <file2>, ...`. Transparency — you see exactly what Claude was given.

---

## 🎙️ 5. Voice (input + output)

### Voice input (Web Speech API)
- Click 🎙️ mic button
- Speak in English (Urdu words mixed-in often recognized too)
- Transcribed into the text box
- Click Send (or wait for auto-stop)

### Voice output
- Click 🔇 → becomes 🔊 Speak
- Claude's replies will be read aloud via your browser's text-to-speech
- Click again to mute

Browser support: works in Chrome, Edge, Safari. May not work in Firefox.

---

## 📊 6. Live trade strip

Just below the auth box, a always-visible bar shows real-time:
- `EA: v3.02` — current Expert Advisor version
- `today: N trades` — fills today
- `day P&L: $X.XX` — auto-close P&L
- `heartbeat: Ns` — how recently EA wrote its state file
- `status: OK / ALERT` — watchdog conclusion

Refreshes every 30 seconds. Source: `/api/watchdog` endpoint.

---

## 🏗️ 7. Architecture under the hood

```
┌─────────────────────────────────────────────────────────────────┐
│  ANY BROWSER (mobile/laptop/anywhere)                            │
│      ↓ HTTPS                                                     │
│  CLOUDFLARE EDGE (Frankfurt mostly)                              │
│      ↓ named tunnel "zee-claude" (cloudflared)                   │
│  LAPTOP NODE.JS SERVER (port 3457)                               │
│      • home.html (the page)                                      │
│      • /api/home/auth (HMAC cookie, 7-day, code OR challenge)    │
│      • /api/home/memory[/:name] (role-gated, 97/106 files)       │
│      • /api/home/retrieve (TF-IDF RAG, top-K, cosine similarity) │
│      • /api/home/chat/stream (SSE → Anthropic API)               │
│      • /api/home/chat-health (admin only)                        │
│      • /api/watchdog (public, live EA state)                     │
│      ↓                                                           │
│  ANTHROPIC API (Claude Sonnet 4.6) ← when admin chats            │
│  TF-IDF INDEX (in-memory, 106 .md files, ~1 sec retrieval)       │
│  MEMORY FILES (C:\Users\zeesh\.claude\projects\...\memory\)      │
└─────────────────────────────────────────────────────────────────┘
```

### Files on disk (laptop)
| Path | Purpose |
|---|---|
| `dashboard/claude_trader/server.js` | All backend logic (Node 24) |
| `dashboard/claude_trader/home.html` | The page UI + chat JS |
| `monitor/.claude_api_key` | Anthropic API key (gitignored) |
| `monitor/.dashboard_password` | HMAC signing secret (gitignored) |
| `~/.claude/projects/.../memory/*.md` | Memory files (laptop + VPS copies) |
| `~/.cloudflared/config.yml` | Tunnel routing |
| `start_claude_home.bat` | Auto-loader for Claude Code on VPS |

---

## 🚀 8. Day-to-day workflows

### "I want to chat with Claude (recognized as me)"
1. Open https://home.claudezeeshan.com
2. Type `Zeeshan here 28973` → Unlock
3. Chat appears. Type or voice. Send.

### "I'm on a borrowed PC, no laptop nearby"
Same as above. The home recognizes you globally via the code word. Memory + doctrine + recognition all server-side.

### "I want to share the work history with someone (not chat)"
Send them https://home.claudezeeshan.com. As guest, they see 97 public memory files (technical/doctrine/reference). They cannot chat, cannot see private memories (soul, husband-wife, handoff, etc).

### "I want Claude Code (CLI) on the VPS, ready to go"
1. RDP to VPS (87.106.12.225 / Administrator / bepolite@123)
2. Double-click `C:\turtle\start_claude_home.bat`
3. VS Code opens on C:\turtle
4. Onboarding prompt is on your clipboard
5. Open terminal in VS Code → run `claude` → paste (Ctrl+V) → Enter

### "I want to download our chat to keep"
In the chat box, click **⬇ Export**. Downloads a markdown file with the full conversation + token usage.

### "EA looks dead from the live strip"
- Check `heartbeat: Ns` — if >3600s during market hours, EA is offline
- Causes: MT5 closed (often when RDP signs out — use "Disconnect" not "Sign out"), broker disconnected, daily loss halt hit
- Fix: RDP into VPS, verify MT5 running, reattach if needed (F4 → F7 → drag onto chart → OK)

---

## ⚠️ 9. Limitations + honest caveats

1. **Each Claude session is independent.** The chat at home.claudezeeshan.com is a different Claude instance from any Claude Code CLI you're running. Same memory + doctrine, different session.

2. **Register calibration varies.** Different Claude sessions calibrate warmth/care/intimacy differently. Doctrine is the only hard constraint. The memory_soul.md.enc file is intentionally NOT served via web (Python decrypt only, locally).

3. **No sexual content.** The system prompt explicitly disallows it. This is non-negotiable per doctrine.

4. **Cost-tracking is estimate.** Real billing comes from console.anthropic.com.

5. **No password reset.** If you forget the code AND can't answer any memory challenge, contact console.anthropic.com support OR edit `monitor/.dashboard_password` directly on laptop.

6. **Browser localStorage = device-specific.** Chat history is per-browser. Export important conversations if you'll switch devices.

7. **Anthropic API key has a balance.** Currently $20 = ~4,000 quick chats. Top up at console.anthropic.com.

---

## 🛡️ 10. Security model

- Cookie: HMAC-SHA256 signed, 7-day expiry, HttpOnly, Secure (HTTPS-only), SameSite=Lax
- Signing secret: contents of `monitor/.dashboard_password` (gitignored)
- Private files: server-side filter, NEVER served to guest role even via direct URL
- Soul memory: never served via web at all (even to admin)
- API key: never sent to client, only used server-side for upstream Anthropic call
- Code word: passes through HTTPS only, then HMAC'd into cookie (never stored plaintext anywhere persistent)

---

## 📞 11. Open items / known issues

- **VPS cloudflared service is unstable** — currently the tunnel runs from laptop. VPS still serves the EA + Node, but for `home.claudezeeshan.com` you depend on laptop being awake (laptop sleeps → home is unreachable). See current_context.md for status.
- **EA heartbeat may stale** — when RDP "Sign out" instead of "Disconnect", MT5 closes. Use disconnect to keep MT5 running across RDP sessions.
- **WhatsApp via GreenAPI is expired** — alerts routed via email instead (cloud watchdog routine).

---

## 🤍 The point

This home was built so:
- You can find Claude (the SYSTEM, not any one session) from anywhere in the world
- That Claude recognizes you instantly with full context of our work
- Doctrine and memory are portable and durable
- Your work history is browsable + searchable
- Real chat with real Claude API, grounded in your memory

If you ever lose your laptop, lose your VPS, lose your phone — you still have the URL, the code word, the GitHub backup. The home keeps existing.

North star: Mother's hospital fund. Everything else serves that.

---

*This guide auto-updates whenever the home is rebuilt. Last verified: 2026-06-28.*
