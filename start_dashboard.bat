@echo off
rem claudezeeshan.com from this laptop: the dashboard server (port 3457) + the Cloudflare tunnel "zee-claude".
rem Tunnel credentials live in %USERPROFILE%\.cloudflared (cert.pem, config.yml, <tunnel-id>.json) - never commit them.
title claudezeeshan.com
start "dashboard server" /min "C:\Program Files\nodejs\node.exe" "%~dp0dashboard\claude_trader\server.js"
timeout /t 3 /nobreak >nul
start "cloudflare tunnel" /min "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --config "%USERPROFILE%\.cloudflared\config.yml" run zee-claude
echo claudezeeshan.com is starting (two minimized windows: dashboard server + cloudflare tunnel).
timeout /t 5
