#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""轻量回测：评估买入策略的历史前瞻收益与胜率。

对抽样股票拉取较长日线历史，按“时间点 t”逐日复现三条买入策略的信号，
统计信号触发后持有 FORWARD_DAYS 天的收益率，并与“任意日买入”的基线对比。

用法：
    python jobs/backtest_strategy.py            # 默认抽样 100 只，前瞻 5 日
    python jobs/backtest_strategy.py 200 10     # 抽样 200 只，前瞻 10 日
"""

import sys
import random
import datetime
import numpy as np
import pandas as pd
import stockstats
import akshare as ak
import libs.common as common

FORWARD_DAYS = 5      # 前瞻持有天数
SAMPLE = 100          # 抽样股票数
HISTORY_DAYS = 400    # 每只回看天数（保证 MA60 等指标有足够样本）
SPOT_DATE = "20260710"


def load_long_history(code):
    symbol = code
    if not (code.startswith("sh") or code.startswith("sz") or code.startswith("bj")):
        prefix = common.gp_type_szsh(code)
        symbol = (prefix or "") + code
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=HISTORY_DAYS)
    df = common.ak_call(ak.stock_zh_a_daily, symbol=symbol, start_date=start.strftime("%Y%m%d"),
                        end_date=end.strftime("%Y%m%d"), adjust="")
    if df is None or df.empty:
        return None
    df.columns = ["date", "open", "high", "close", "low", "volume", "amount",
                  "outstanding_share", "turnover"]
    df = df[["date", "open", "close", "high", "low", "volume"]]
    df.set_index("date", inplace=True)
    df.index = pd.to_datetime(df.index)
    return df


def eval_stock(df, results):
    if df is None or len(df) < 80:
        return
    ss = stockstats.StockDataFrame.retype(df.copy())
    kdjk, kdjd, kdjj = ss["kdjk"], ss["kdjd"], ss["kdjj"]
    macd, macds, boll = ss["macd"], ss["macds"], ss["boll"]
    vr, vr6 = ss["vr"], ss["vr_6_sma"]
    ma5, ma10, ma20, ma60 = ss["close_5_sma"], ss["close_10_sma"], ss["close_20_sma"], ss["close_60_sma"]
    high20, close = ss["high_20_max"], ss["close"]
    n = len(df)
    for t in range(60, n - FORWARD_DAYS):
        price = close.iloc[t]
        if price <= 0:
            continue
        fwd = close.iloc[t + FORWARD_DAYS] / price - 1.0
        if np.isnan(fwd) or np.isinf(fwd):
            continue
        signals = {
            "KDJ强势": (kdjk.iloc[t] > 80 and kdjd.iloc[t] > 70 and kdjj.iloc[t] > 90
                        and macd.iloc[t] > macds.iloc[t] and price > boll.iloc[t]
                        and vr.iloc[t] > vr6.iloc[t]),
            "均线多头": (ma5.iloc[t] > ma10.iloc[t] > ma20.iloc[t] > ma60.iloc[t]
                        and price > ma5.iloc[t] and macd.iloc[t] > macds.iloc[t]),
            "放量突破": (high20.iloc[t] > 0 and price >= high20.iloc[t]
                        and vr.iloc[t] > vr6.iloc[t]),
        }
        for name, hit in signals.items():
            if hit:
                results[name].append(fwd)
        results["_ALL_"].append(fwd)


def main():
    global SAMPLE, FORWARD_DAYS
    if len(sys.argv) >= 2:
        SAMPLE = int(sys.argv[1])
    if len(sys.argv) >= 3:
        FORWARD_DAYS = int(sys.argv[2])

    codes = pd.read_sql(
        f"SELECT code FROM stock_zh_a_spot_em WHERE `date`={SPOT_DATE} AND `open`>0 ORDER BY code",
        common.engine())["code"].tolist()
    random.seed(42)
    random.shuffle(codes)
    codes = codes[:SAMPLE]

    results = {"KDJ强势": [], "均线多头": [], "放量突破": [], "_ALL_": []}
    for i, code in enumerate(codes):
        try:
            eval_stock(load_long_history(code), results)
        except Exception as e:
            print("skip", code, str(e)[:50])
        if (i + 1) % 20 == 0:
            print(f"...processed {i + 1}/{len(codes)}")

    print(f"\n=== 回测结果 (前瞻 {FORWARD_DAYS} 日, 抽样 {len(codes)} 只, 每只 ~{HISTORY_DAYS} 天) ===")
    base = np.array(results["_ALL_"]) if results["_ALL_"] else np.array([0.0])
    print(f"基线(任意日买入持有{FORWARD_DAYS}日): 样本 {len(base)}, "
          f"平均 {base.mean() * 100:.2f}%, 胜率 {(base > 0).mean() * 100:.1f}%")
    for name in ["KDJ强势", "均线多头", "放量突破"]:
        a = np.array(results[name])
        if len(a) == 0:
            print(f"{name}: 无信号")
            continue
        edge = (a.mean() - base.mean()) * 100
        print(f"{name}: 信号 {len(a)} 次, 平均 {a.mean() * 100:.2f}%, "
              f"胜率 {(a > 0).mean() * 100:.1f}%, 中位 {np.median(a) * 100:.2f}%, "
              f"超额(vs基线) {edge:+.2f}%")


if __name__ == "__main__":
    main()
