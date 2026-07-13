# -*- coding: utf-8 -*-
"""
买入三策略掩码 —— 规格/回归测试。

在测试内 **独立复现** 买入策略布尔条件（等价于 guess_indicators_daily_buy_job 里的逻辑），
避免 import 业务模块触发数据库连接。构造合成的 guess_indicators_daily 样式 DataFrame，
断言各行命中的策略集合与 `strategy` 逗号拼接字符串正确。

策略定义（作用于一行）：
- KDJ强势 : kdjk>80 & kdjd>70 & kdjj>90 & macd>macds & last_price>boll & vr>vr_6_sma
- 均线多头 : close_5_sma>close_10_sma>close_20_sma>close_60_sma & last_price>close_5_sma & macd>macds
- 放量突破 : high_20_max>0 & last_price>=high_20_max & vr>vr_6_sma
命中任一入选，strategy 用逗号拼接命中的中文名（顺序：KDJ强势, 均线多头, 放量突破）。
"""

import pandas as pd


# 参与条件的数值列（缺失填 0，与业务 _NUM_COLS 语义一致）。
BUY_NUM_COLS = [
    "last_price", "kdjk", "kdjd", "kdjj", "macd", "macds", "boll",
    "vr", "vr_6_sma", "close_5_sma", "close_10_sma", "close_20_sma",
    "close_60_sma", "high_20_max",
]


def compute_buy_strategy(data: pd.DataFrame) -> pd.DataFrame:
    """独立实现买入三策略并集，返回带 s1/s2/s3 掩码与 strategy 列的副本。"""
    data = data.copy()
    for c in BUY_NUM_COLS:
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors="coerce").fillna(0)

    s1 = ((data.kdjk > 80) & (data.kdjd > 70) & (data.kdjj > 90)
          & (data.macd > data.macds) & (data.last_price > data.boll)
          & (data.vr > data.vr_6_sma))
    s2 = ((data.close_5_sma > data.close_10_sma) & (data.close_10_sma > data.close_20_sma)
          & (data.close_20_sma > data.close_60_sma) & (data.last_price > data.close_5_sma)
          & (data.macd > data.macds))
    s3 = ((data.high_20_max > 0) & (data.last_price >= data.high_20_max)
          & (data.vr > data.vr_6_sma))

    data["s1"], data["s2"], data["s3"] = s1, s2, s3
    data["strategy"] = ""
    data.loc[s1, "strategy"] += "KDJ强势,"
    data.loc[s2, "strategy"] += "均线多头,"
    data.loc[s3, "strategy"] += "放量突破,"
    data["strategy"] = data["strategy"].str.rstrip(",")
    return data


def _base_row(**overrides):
    """一行“均不命中”的中性基线，测试用例只覆盖需要触发的字段。"""
    row = {
        "code": "sh600000", "name": "测试",
        "last_price": 10.0,
        "kdjk": 50.0, "kdjd": 50.0, "kdjj": 50.0,
        "macd": 0.0, "macds": 0.0,
        "boll": 10.0,
        "vr": 100.0, "vr_6_sma": 100.0,
        "close_5_sma": 10.0, "close_10_sma": 10.0,
        "close_20_sma": 10.0, "close_60_sma": 10.0,
        "high_20_max": 999.0,  # 远高于价 → 不会误触放量突破
    }
    row.update(overrides)
    return row


def _build(rows):
    return pd.DataFrame([_base_row(**r) for r in rows])


def test_only_kdj_strong():
    df = _build([dict(
        kdjk=85, kdjd=75, kdjj=95, macd=1.0, macds=0.5,
        last_price=12.0, boll=10.0, vr=150.0, vr_6_sma=100.0,
        high_20_max=999.0,  # 明确不触发放量突破
    )])
    out = compute_buy_strategy(df)
    assert out.loc[0, "s1"] and not out.loc[0, "s2"] and not out.loc[0, "s3"]
    assert out.loc[0, "strategy"] == "KDJ强势"


def test_only_ma_bull():
    df = _build([dict(
        close_5_sma=13.0, close_10_sma=12.0, close_20_sma=11.0, close_60_sma=10.0,
        last_price=14.0, macd=1.0, macds=0.5,
        vr=100.0, vr_6_sma=100.0,  # vr 不 > vr_6_sma，避免放量突破
        high_20_max=999.0,
    )])
    out = compute_buy_strategy(df)
    assert not out.loc[0, "s1"] and out.loc[0, "s2"] and not out.loc[0, "s3"]
    assert out.loc[0, "strategy"] == "均线多头"


def test_only_volume_breakout():
    df = _build([dict(
        last_price=20.0, high_20_max=18.0, vr=200.0, vr_6_sma=100.0,
        # 保持 kdj/均线不满足
        kdjk=50, close_5_sma=10.0,
    )])
    out = compute_buy_strategy(df)
    assert not out.loc[0, "s1"] and not out.loc[0, "s2"] and out.loc[0, "s3"]
    assert out.loc[0, "strategy"] == "放量突破"


def test_multi_hit_kdj_and_breakout():
    # KDJ强势 与 放量突破 同时命中（都需要放量，天然容易共存）。
    df = _build([dict(
        kdjk=85, kdjd=75, kdjj=95, macd=1.0, macds=0.5,
        last_price=20.0, boll=10.0, vr=200.0, vr_6_sma=100.0,
        high_20_max=18.0,
    )])
    out = compute_buy_strategy(df)
    assert out.loc[0, "s1"] and out.loc[0, "s3"] and not out.loc[0, "s2"]
    # 拼接顺序：KDJ强势 在 放量突破 之前。
    assert out.loc[0, "strategy"] == "KDJ强势,放量突破"


def test_all_three_hit():
    df = _build([dict(
        kdjk=85, kdjd=75, kdjj=95, macd=1.0, macds=0.5,
        boll=10.0, vr=200.0, vr_6_sma=100.0,
        close_5_sma=13.0, close_10_sma=12.0, close_20_sma=11.0, close_60_sma=10.0,
        last_price=20.0, high_20_max=18.0,
    )])
    out = compute_buy_strategy(df)
    assert out.loc[0, "s1"] and out.loc[0, "s2"] and out.loc[0, "s3"]
    assert out.loc[0, "strategy"] == "KDJ强势,均线多头,放量突破"


def test_none_hit():
    df = _build([dict()])  # 纯基线
    out = compute_buy_strategy(df)
    assert not out.loc[0, "s1"] and not out.loc[0, "s2"] and not out.loc[0, "s3"]
    assert out.loc[0, "strategy"] == ""


def test_breakout_requires_positive_high_20_max():
    # high_20_max<=0 时即便 last_price>=high_20_max 也不应命中放量突破（守护 >0 条件）。
    df = _build([dict(last_price=5.0, high_20_max=0.0, vr=200.0, vr_6_sma=100.0)])
    out = compute_buy_strategy(df)
    assert not out.loc[0, "s3"]
    assert out.loc[0, "strategy"] == ""


def test_multiple_rows_mixed():
    df = _build([
        dict(),  # none
        dict(kdjk=85, kdjd=75, kdjj=95, macd=1.0, macds=0.5,
             last_price=12.0, boll=10.0, vr=150.0, vr_6_sma=100.0, high_20_max=999.0),  # KDJ强势
        dict(close_5_sma=13.0, close_10_sma=12.0, close_20_sma=11.0, close_60_sma=10.0,
             last_price=14.0, macd=1.0, macds=0.5, high_20_max=999.0),  # 均线多头
    ])
    out = compute_buy_strategy(df)
    assert list(out["strategy"]) == ["", "KDJ强势", "均线多头"]
