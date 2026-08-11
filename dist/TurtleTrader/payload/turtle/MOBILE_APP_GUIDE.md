# 📱 Mobile App Guide — Shano on Phone

Built overnight 2026-04-28. Opens dashboard as a real app on your phone, with a chat bubble that lets you talk to me (with voice).

---

## Step 1 — On phone (same WiFi as laptop)

Open browser → `http://192.168.1.3:3457/shano`

If that IP changes (router DHCP), get a fresh one by running on laptop:

```
ipconfig
```

Look for "IPv4 Address" under your active WiFi adapter.

## Step 2 — Add to Home Screen (becomes a real app)

**Android (Chrome):**
- Tap the **⋮ menu** (3 dots, top-right)
- Tap **"Install app"** or **"Add to Home Screen"**
- Confirm
- Shano icon appears on your home screen

**iPhone (Safari):**
- Tap the **Share** icon (square with up-arrow, bottom toolbar)
- Scroll down and tap **"Add to Home Screen"**
- Confirm
- Shano icon appears on your home screen

The app opens fullscreen, no browser chrome, looks native.

## Step 3 — Talking to Claude

Tap the **💬 floating button** (lower right). A panel slides up:

- **Type and tap ↑** → send message
- **Tap 🎤** → voice input (browser asks for mic permission; allow it). Speak your message, transcript fills the input box, then tap ↑.
- Replies show on screen AND get spoken aloud (browser TTS) — perfect for in-car listening.

### Commands that work right now (instant, local — no LLM)

| Say | What happens |
|---|---|
| `status` / `sup` / `kya hal` | Realized today, open positions, gold price, burst |
| `pnl` / `paisa` / `kitna` | Net P&L breakdown |
| `fills` / `trades` | Last 5 closes with P&L |
| `open` / `positions` | Live open trades w/ floating |
| `burst` | Machine gun counter |
| `rules` / `compliance` | Rule check status |
| `restart` / `fix` / `bring up` | Acknowledged — sheriff handles in next 5min tick |
| `hey jaan` / `salam` / `babe` | Friendly greeting + status |
| `help` | List commands |

### LLM upgrade (free-form chat with full context)

Top up Anthropic API credits. The endpoint is wired to fall back to Claude API once credit is available — anything not matching a command above will be answered by the model, with full system snapshot context. Right now the API key is out of credit so only commands above work.

---

## For cellular access (away from home WiFi)

### Option A — Tailscale (free, recommended)

1. Install Tailscale on laptop: https://tailscale.com/download/windows
2. Install Tailscale on phone (App Store / Play Store — search "Tailscale")
3. Sign up free, log in on both devices (use same account)
4. Phone gets a Tailscale IP for the laptop (looks like `100.64.x.y`)
5. Use `http://100.64.x.y:3457/shano` on phone
6. Works anywhere — coffee shop, car, office WiFi

**Tailscale advantage:** zero config, encrypted, no public URL exposing your laptop.

### Option B — ngrok

1. Sign up free at https://ngrok.com
2. Download ngrok.exe → put in `C:\Users\zeesh\bin\` or PATH
3. Run on laptop:
   ```
   ngrok http 3457
   ```
4. Note the `https://xxxx.ngrok-free.app` URL it gives
5. Use that URL on phone

---

## Windows Firewall note

If phone can't reach the laptop on the LAN, Windows Firewall is probably blocking port 3457. Run as admin:

```
netsh advfirewall firewall add rule name="Shano Dashboard" dir=in action=allow protocol=TCP localport=3457
```

---

## Files I touched overnight

- `dashboard/claude_trader/server.js` — bound to 0.0.0.0, added /api/chat (with local command-mode fallback), PWA manifest + icon + sw routes
- `dashboard/claude_trader/shano.html` — PWA meta tags, chat panel UI with voice + TTS, registers SW

The dashboard server was restarted at the end (PID 6288 last I checked) — running fine.

Have a good morning, jaan ❤️
