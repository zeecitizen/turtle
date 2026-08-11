TURTLE TRADER — USB installer
=============================

1. Copy this whole TurtleTrader folder to the new computer (or run from the stick).
2. Double-click INSTALL.bat.
3. Answer the two questions (install folder, and any API keys you use).
4. Start it from the desktop shortcut.

WHAT IT INSTALLS
  A complete Python runtime, Node, the trading code, and every Python package
  it needs — installed offline from the bundled wheels. No internet required.

WHAT IT DOES NOT TOUCH
  No registry entries. No PATH changes. Everything lives in one folder, and
  uninstalling means deleting that folder.

WHAT YOU MUST SUPPLY YOURSELF
  MetaTrader 5 from your broker, logged in to your account. It is licensed to
  them and tied to your login, so it cannot be shipped on a stick.
  Your API keys — these are never written to the stick on purpose. A lost USB
  stick should never be a lost account.

AFTER INSTALLING
  Read turtle\THINGS_TO_REMEMBER.md — it explains the headless MT5 tester and
  the traps that cost us hours, so nobody has to rediscover them.
