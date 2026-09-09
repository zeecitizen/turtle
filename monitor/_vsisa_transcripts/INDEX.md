# VSISA transcripts — index

Speech from the 22-part course *Volume Spread Imbalance Shift Analysis* (Sajid Ahmed),
the source Zee's `LAWS_VSISA.md` cites. The inferred rules are in
`/LAWS_VSISA_INFER.md`; this folder is the evidence behind them.

`partNN_orig.txt` is **Whisper output in the original Urdu/Hindi** — the speaker
code-switches, so some files are Arabic script and some Devanagari, sometimes inside one
sentence. It is not translated and not timestamped, but it is *accurate*, which is the
part that matters.

## ⚠️ THE NUMBERING WAS WRONG AND IS NOW FIXED

The May 2026 transcription run (`monitor/_vsa_transcripts/`) downloaded **one extra video
at playlist position 2**, so every file from `part03` onward was labelled one ahead of the
video it actually contains. Anyone reading `_vsa_transcripts/part06.txt` expecting Part 6
gets Part 5.

    true Part 1  = _vsa_transcripts/part01.txt
    true Part N  = _vsa_transcripts/part{N+1}.txt      for N >= 2

The files in THIS folder are already renumbered — `partNN_orig.txt` is genuinely Part NN.

Proven by matching audio durations, not assumed:

| true part | seconds | old file |
|---|---|---|
| 1 | 903 | part01 |
| 2 | 848 | part03 |
| 5 | 861 | part06 |
| 9 | 622 | part10 |
| 15 | 496 | part16 |

Coverage is **parts 1–21**. Part 22 has no transcript.

## ⛔ What was tried and thrown away

**YouTube auto-translated English captions are worthless here** and were deleted rather
than kept, so nobody mistakes them for a source. The pipeline is machine ASR of Urdu
speech, then machine translation — and it hallucinates fluent English nonsense.
Part 5 at 0:00 came back as *"after the construction of this road, the Superintendent of
Police said..."* on a passage about volume on a bullish candle. It is not merely rough;
it invents content, which is worse than nothing.

**OpenAI Whisper API is unavailable** — the key in `monitor/.openai_api_key` returns
HTTP 429 "You have no credits remaining", which is why parts 1–21 come from the May run
and part 22 is missing. `monitor/_vsisa_transcribe.py` is written and working and will
transcribe the local videos in `C:\Users\zeesh\Downloads\VSISA` to timestamped English
the moment that account has credit.

## Files

| part | bytes | part | bytes |
|---|---|---|---|
| 01 | 11392 | 12 | 10190 |
| 02 | 10146 | 13 | 10580 |
| 03 | 8988 | 14 | 10707 |
| 04 | 12700 | 15 | 9865 |
| 05 | 16515 | 16 | 9096 |
| 06 | 13648 | 17 | 8117 |
| 07 | 10566 | 18 | 10340 |
| 08 | 14829 | 19 | 10414 |
| 09 | 14349 | 20 | 10414 |
| 10 | 14448 | 21 | 10339 |
| 11 | 10190 | 22 | *missing* |

## Where the load-bearing quotes live

- **Part 1** — big volume is 50/50, the next bar resolves it; ignore VSA bands
- **Part 3–4** — effort vs result; the three-bar setup introduced
- **Part 5** — two-bar setup; the support / fake-break confirmation ladder
- **Part 6** — end of rising market; the wick as proof of aggression
- **Part 7** — the cleanest statement of the ideal sell: cluster, then LOW-volume reaction
- **Part 8** — aggressive buying, lower wick; "without the wick this could be supply"
- **Part 9** — anomaly / bag holding; the no-supply test
- **Part 10** — **SL 3 to 8 pips**; never chase, trade the retracement
- **Part 12** — **SL 2–3 pips beyond the extreme**; breakout on big volume is supply
- **Part 13** — the imbalance-shift narrative end to end
- **Part 15** — "the lower the volume the stronger the signal; if big volume comes, SKIP"
- **Part 16–17** — fib 50/61.8 + Automatic Rally line (a *different* method, not ported)
- **Part 18** — currency strength meter (meaningless on a single instrument)
