Claude's test rounds from 3 Nov 2026, moved out of rounds/ on 4 Nov 2026 (about 1:55 AM CET).

Why: the game counts every round in rounds/<day>/ as the player's own. These test rounds were filling
Zee's tallies board and trophy shelf. They also satisfied the Paper Alley gate (5 wooden rounds incl. an
eject), so the real note was already unlocked before Zee had played a single practice round.

What is here:
  *-sim.json            4 wooden rounds on the SIM server (build agents 06:52 UTC, Claude 22:20-22:23 UTC)
  230003..230027-live   5 wooden Alley rounds Claude played on LIVE quotes (23:00-23:01 UTC = 4:00 AM PKT)
  230158-live           the first REAL 0.01 oz round, played by Claude: buy 3932.82, stop 3931.82, -1.00 cent.
                        PrimeXBT report/orders2 matched to the cent. Position 15460073. Kept here as the receipt.
  discipline.json.bak   the SIM discipline state from the build agents' tests (storm timer, waited_storm award)

To restore any of them: stop the game server, move the file back into rounds/<YYYYMMDD>/, start the server.
