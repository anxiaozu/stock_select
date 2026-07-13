# -*- coding: utf-8 -*-
"""
卖出三策略掩码 —— 规格/回归测试。

独立复现卖出策略布尔条件（等价于 guess_indicators_daily_sell_job 的逻辑），不 import 业务模块。

策略定义（作用于一行）：
- 见顶回落 : kdjj>80 & macd<macds & last_price<close_5_sma
- 均线空头 : close_5_sma<close_10_sma<close_20_sma<close_60_sma （业务上并要求 close_60_sma>0）
- 跌破下轨 : boll_lb>0 & last_price<boll_lb
命中任一入选，strategy 拼接顺序：见顶回落, 均线空头, 跌破下轨。
"""

import pandas as pd


SELL_NUM_COLS = [
    "last_price", "kdjj", "macd", "macds", "boll_lb",
    "close_5_sma", "close_10_sma", "close_20_sma", "close_60_sma",
]


def compute_sell_strategy(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    for c in SELL_NUM_COLS:
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors="coerce").fillna(0)

    d1 = (data.kdjj > 80) & (data.macd < data.macds) & (data.last_price < data.close_5_sma)
    d2 = ((data.close_5_sma < data.close_10_sma) & (data.close_10_sma < data.close_20_sma)
          & (data.close_20_sma < data.close_60_sma) & (data.close_60_sma > 0))
    d3 = (data.boll_lb > 0) & (data.last_price < data.boll_lb)

    data["d1"], data["d2"], data["d3"] = d1, d2, d3
    data["strategy"] = ""
    data.loc[d1, "strategy"] += "见顶回落,"
    data.loc[d2, "strategy"] += "均线空头,"
    data.loc[d3, "strategy"] += "跌破下轨,"
    data["strategy"] = data["strategy"].str.rstrip(",")
    return data


def _base_row(**overrides):
    """中性基线：均不命中卖出信号。"""
    row = {
        "code": "sh600000", "name": "测试",
        "last_price": 10.0,
        "kdjj": 50.0, "macd": 0.0, "macds": 0.0,
        "boll_lb": 5.0,  # >0 但价 10 > 5 → 不破下轨
        # 均线多头排列（升序），保证 d2 不命中
        "close_5_sma": 13.0, "close_10_sma": 12.0,
        "close_20_sma": 11.0, "close_60_sma": 10.0,
    }
    row.update(overrides)
    return row


def _build(rows):
    return pd.DataFrame([_base_row(**r) for r in rows])


def test_only_top_reversal():
    df = _build([dict(
        kdjj=85, macd=-0.5, macds=0.2, last_price=9.0, close_5_sma=13.0,
        boll_lb=5.0,  # 价 9 > 5，不破下轨
    )])
    out = compute_sell_strategy(df)
    assert out.loc[0, "d1"] and not out.loc[0, "d2"] and not out.loc[0, "d3"]
    assert out.loc[0, "strategy"] == "见顶回落"


def test_only_ma_bear():
    df = _build([dict(
        close_5_sma=10.0, close_10_sma=11.0, close_20_sma=12.0, close_60_sma=13.0,
        last_price=10.5,  # > boll_lb(5)，不破下轨; > close_5_sma → 不见顶回落
        kdjj=50,
    )])
    out = compute_sell_strategy(df)
    assert not out.loc[0, "d1"] and out.loc[0, "d2"] and not out.loc[0, "d3"]
    assert out.loc[0, "strategy"] == "均线空头"


def test_only_break_lower_band():
    df = _build([dict(
        last_price=4.0, boll_lb=5.0,
        # 保持均线多头排列(升序)避免 d2；kdjj 低避免 d1
        close_5_sma=13.0, close_10_sma=12.0, close_20_sma=11.0, close_60_sma=10.0,
        kdjj=50,
    )])
    out = compute_sell_strategy(df)
    # 注意：last_price 4 < close_5_sma 13，但 kdjj=50 不 >80，d1 不命中。
    assert not out.loc[0, "d1"] and not out.loc[0, "d2"] and out.loc[0, "d3"]
    assert out.loc[0, "strategy"] == "跌破下轨"


def test_multi_hit_top_and_break():
    df = _build([dict(
        kdjj=85, macd=-0.5, macds=0.2, last_price=4.0,
        close_5_sma=13.0, close_10_sma=12.0, close_20_sma=11.0, close_60_sma=10.0,
        boll_lb=5.0,  # 价 4 < 5 → 破下轨
    )])
    out = compute_sell_strategy(df)
    assert out.loc[0, "d1"] and not out.loc[0, "d2"] and out.loc[0, "d3"]
    assert out.loc[0, "strategy"] == "见顶回落,跌破下轨"


def test_all_three_hit():
    # 均线空头(降序) + 见顶回落 + 跌破下轨 同时成立。
    df = _build([dict(
        kdjj=85, macd=-0.5, macds=0.2,
        close_5_sma=10.0, close_10_sma=11.0, close_20_sma=12.0, close_60_sma=13.0,
        last_price=4.0,  # < close_5_sma(10) 且 < boll_lb(5)
        boll_lb=5.0,
    )])
    out = compute_sell_strategy(df)
    assert out.loc[0, "d1"] and out.loc[0, "d2"] and out.loc[0, "d3"]
    assert out.loc[0, "strategy"] == "见顶回落,均线空头,跌破下轨"


def test_none_hit():
    out = compute_sell_strategy(_build([dict()]))
    assert not out.loc[0, "d1"] and not out.loc[0, "d2"] and not out.loc[0, "d3"]
    assert out.loc[0, "strategy"] == ""


def test_break_lower_band_requires_positive_boll_lb():
    # boll_lb<=0 时不应命中跌破下轨（守护 >0 条件，避免 0 值误判）。
    df = _build([dict(last_price=-1.0, boll_lb=0.0)])
    out = compute_sell_strategy(df)
    assert not out.loc[0, "d3"]


def test_ma_bear_requires_positive_close_60_sma():
    # 全 0 均线时严格降序不成立（均相等），且 close_60_sma>0 守护避免空数据误判。
    df = _build([dict(close_5_sma=0.0, close_10_sma=0.0,
                      close_20_sma=0.0, close_60_sma=0.0, last_price=1.0)])
    out = compute_sell_strategy(df)
    assert not out.loc[0, "d2"]


def test_multiple_rows_mixed():
    df = _build([
        dict(),  # none
        dict(kdjj=85, macd=-0.5, macds=0.2, last_price=9.0, close_5_sma=13.0, boll_lb=5.0),  # 见顶回落
        dict(close_5_sma=10.0, close_10_sma=11.0, close_20_sma=12.0, close_60_sma=13.0,
             last_price=10.5, kdjj=50),  # 均线空头
    ])
    out = compute_sell_strategy(df)
    assert list(out["strategy"]) == ["", "见顶回落", "均线空头"]
