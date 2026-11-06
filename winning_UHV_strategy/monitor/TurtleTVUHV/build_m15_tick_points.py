"""Build disk-backed quote ticks and per-second paths for Turtle TV's four-year M15 dataset."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SIMDATA = HERE / "simdata"
DEFAULT_SOURCE = HERE.parents[1] / "data_15min_2015_onwards_xauusd" / "XAUUSD_202201030100_202610232021.csv"


def emit_seconds(rows, files):
    if rows is None or rows.empty:
        return 0
    grouped = rows.groupby("s", sort=True)
    index = grouped["b"].first().index.to_numpy(dtype=np.int64)
    bo, bc = grouped["b"].first().to_numpy(), grouped["b"].last().to_numpy()
    bh, bl = grouped["b"].max().to_numpy(), grouped["b"].min().to_numpy()
    ao, ac = grouped["a"].first().to_numpy(), grouped["a"].last().to_numpy()
    ah, al = grouped["a"].max().to_numpy(), grouped["a"].min().to_numpy()
    bh_ms = rows.loc[rows["b"].eq(rows["s"].map(grouped["b"].max())), ["s", "ms"]].groupby("s", sort=True)["ms"].first().reindex(index).to_numpy()
    bl_ms = rows.loc[rows["b"].eq(rows["s"].map(grouped["b"].min())), ["s", "ms"]].groupby("s", sort=True)["ms"].first().reindex(index).to_numpy()
    high_first = bh_ms <= bl_ms
    bid = np.column_stack((bo, np.where(high_first, bh, bl), np.where(high_first, bl, bh), bc)).ravel()
    ask = np.column_stack((ao, np.where(high_first, ah, al), np.where(high_first, al, ah), ac)).ravel()
    index4 = np.repeat(index, 4)
    index.tofile(files["sec"])
    bid.tofile(files["bid4"])
    ask.tofile(files["ask4"])
    index4.tofile(files["time4"])
    return len(index)


def main(source):
    if not source.is_file():
        raise FileNotFoundError(f"tick CSV not found: {source}")

    with np.load(SIMDATA / "m15.npz") as bars:
        first = int(bars["t1"][0])
        last = int(bars["t1"][-1])
    start_date = datetime.fromtimestamp(first, timezone.utc).strftime("%Y.%m.%d")
    end_date = datetime.fromtimestamp(last, timezone.utc).strftime("%Y.%m.%d")

    SIMDATA.mkdir(exist_ok=True)
    names = ("bid4", "ask4", "time4", "sec", "raw_t", "raw_bid", "raw_ask")
    temp_paths = {name: SIMDATA / f"m15_tick_{name}.bin.tmp" for name in names}
    manifest = SIMDATA / "m15_tick_points.json"
    carry = None
    last_bid = last_ask = None
    seconds = ticks = rows_seen = 0
    handles = {name: path.open("wb") for name, path in temp_paths.items()}
    try:
        for chunk_no, chunk in enumerate(pd.read_csv(
            source, sep="\t", usecols=["<DATE>", "<TIME>", "<BID>", "<ASK>"],
            chunksize=250_000, dtype={"<DATE>": str, "<TIME>": str},
        ), start=1):
            dates = chunk["<DATE>"]
            if dates.iloc[0] > end_date:
                seconds += emit_seconds(carry, handles)
                carry = None
                break

            bid = pd.to_numeric(chunk["<BID>"], errors="coerce").ffill()
            ask = pd.to_numeric(chunk["<ASK>"], errors="coerce").ffill()
            if last_bid is not None:
                bid = bid.fillna(last_bid)
            if last_ask is not None:
                ask = ask.fillna(last_ask)
            if bid.notna().any():
                last_bid = float(bid.dropna().iloc[-1])
            if ask.notna().any():
                last_ask = float(ask.dropna().iloc[-1])

            keep = (dates >= start_date) & (dates <= end_date)
            if not keep.any():
                continue
            selected = chunk.loc[keep, ["<DATE>", "<TIME>"]].copy()
            times = pd.to_datetime(selected["<DATE>"] + " " + selected["<TIME>"], format="%Y.%m.%d %H:%M:%S.%f")
            ns = times.to_numpy(dtype="datetime64[ns]").astype(np.int64)
            selected["t"] = ns.astype(np.float64) / 1_000_000_000
            selected["s"] = ns // 1_000_000_000
            selected["ms"] = (ns % 1_000_000_000 // 1_000_000).astype(np.int32)
            selected["b"] = bid.loc[keep].to_numpy()
            selected["a"] = ask.loc[keep].to_numpy()
            selected = selected.loc[selected["b"].notna() & selected["a"].notna()]
            selected["t"].to_numpy(dtype=np.float64).tofile(handles["raw_t"])
            selected["b"].to_numpy(dtype=np.float64).tofile(handles["raw_bid"])
            selected["a"].to_numpy(dtype=np.float64).tofile(handles["raw_ask"])
            ticks += len(selected)
            selected = selected[["s", "ms", "b", "a"]]
            if carry is not None:
                selected = pd.concat((carry, selected), ignore_index=True)
            if selected.empty:
                carry = None
                continue

            final_second = selected["s"].iloc[-1]
            done = selected.loc[selected["s"] < final_second]
            carry = selected.loc[selected["s"] == final_second]
            seconds += emit_seconds(done, handles)
            rows_seen += len(chunk)
            if chunk_no % 100 == 0:
                print(f"chunks={chunk_no} rows={rows_seen:,} seconds={seconds:,}", flush=True)

        if carry is not None:
            seconds += emit_seconds(carry, handles)
        if not seconds:
            raise RuntimeError("no tick seconds matched the four-year M15 dataset")
        for handle in handles.values():
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        for handle in handles.values():
            handle.close()

    for name, temp_path in temp_paths.items():
        os.replace(temp_path, SIMDATA / f"m15_tick_{name}.bin")
    metadata = {
        "source": str(source),
        "start": start_date,
        "end": end_date,
        "seconds": seconds,
        "ticks": ticks,
        "minutes_start": first,
        "minutes_end": last,
    }
    temp_manifest = manifest.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_manifest, manifest)
    print(f"done: {ticks:,} ticks, {seconds:,} seconds / {seconds * 4:,} points ({start_date}–{end_date})", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE)
