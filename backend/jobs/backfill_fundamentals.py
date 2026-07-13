#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""用新浪日线数据回填 换手率/流通市值/量比 到 guess_indicators_daily。

背景：东财实时快照(stock_zh_a_spot_em)在本机网络(TUN 代理)下不可达，导致
turnover_rate/volume_ratio/market_cap/circulating_market_cap 全为 0。新浪日线
(stock_zh_a_daily)可正常访问，且返回 turnover(换手率,小数) 与 outstanding_share
(流通股本)，据此可自算：
  turnover_rate         = turnover * 100           (换手率 %)
  circulating_market_cap= outstanding_share * close (流通市值, 元)
  volume_ratio          = volume / volume_5_sma     (量比近似, 用已有列，免联网)

用法：python jobs/backfill_fundamentals.py 2026-07-10   (缺省用最近交易日)
"""
import sys
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from sqlalchemy import text

import libs.common as common

WORKERS = 16


def _symbol(code):
    if code.startswith(("sh", "sz", "bj")):
        return code
    prefix = common.gp_type_szsh(code)
    return (prefix or "") + code


def _fetch_one(code, date_int):
    """取该股票截至 date 的最近一根日线，返回 (code, turnover_rate, circulating_market_cap)。"""
    end = datetime.datetime.strptime(date_int, "%Y%m%d")
    start = (end + datetime.timedelta(days=-15)).strftime("%Y%m%d")
    try:
        df = common._ak_stock_daily_with_retry(_symbol(code), start, end.strftime("%Y%m%d"), "")
    except Exception:
        df = None
    if df is None or df.empty:
        return code, None, None
    row = df.iloc[-1]
    try:
        turnover = float(row["turnover"])
        shares = float(row["outstanding_share"])
        close = float(row["close"])
    except Exception:
        return code, None, None
    turnover_rate = round(turnover * 100.0, 4)
    cmc = round(shares * close, 2)
    return code, turnover_rate, cmc


def main():
    date_int = sys.argv[1].replace("-", "") if len(sys.argv) >= 2 else None
    if not date_int:
        date_int = common.select_count("SELECT max(`date`) FROM guess_indicators_daily")
        date_int = str(date_int)
    print("backfill date:", date_int)

    base = pd.read_sql(
        text("SELECT code, volume, volume_5_sma FROM guess_indicators_daily WHERE `date`=:d"),
        common.engine(), params={"d": date_int})
    if len(base) == 0:
        print("no rows for date"); return
    codes = base["code"].tolist()
    print("codes:", len(codes))

    # 量比：直接用已有列算，免联网。
    vr_map = {}
    for _, r in base.iterrows():
        v5 = float(r["volume_5_sma"] or 0)
        vr_map[r["code"]] = round(float(r["volume"] or 0) / v5, 4) if v5 > 0 else 0.0

    # 换手率/流通市值：并发拉新浪日线。
    results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(_fetch_one, c, date_int): c for c in codes}
        for fut in as_completed(futs):
            code, tr, cmc = fut.result()
            results[code] = (tr, cmc)
            done += 1
            if done % 300 == 0 or done == len(codes):
                print(f"fetched {done}/{len(codes)}")

    rows = []
    ok = 0
    for c in codes:
        tr, cmc = results.get(c, (None, None))
        if tr is None:
            continue
        ok += 1
        rows.append({"tr": tr, "cmc": cmc, "vr": vr_map.get(c, 0.0), "d": date_int, "c": c})

    print(f"updatable: {ok}/{len(codes)}")
    if rows:
        eng = common.engine()
        with eng.begin() as conn:
            conn.execute(text(
                "UPDATE guess_indicators_daily SET turnover_rate=:tr, "
                "circulating_market_cap=:cmc, volume_ratio=:vr "
                "WHERE `date`=:d AND `code`=:c"), rows)
    print("done. sample:")
    chk = pd.read_sql(text(
        "SELECT code,name,round(turnover_rate,2) turnover_rate, "
        "round(circulating_market_cap/1e8,2) cmc_yi, round(volume_ratio,2) vr "
        "FROM guess_indicators_daily WHERE `date`=:d AND turnover_rate>0 LIMIT 6"),
        common.engine(), params={"d": date_int})
    print(chk.to_string(index=False))


if __name__ == "__main__":
    main()
