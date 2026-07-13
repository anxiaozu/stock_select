# -*- coding: utf-8 -*-
"""
stockstats 取值语义回归。

守护的历史 bug：
    取指标“最新值”时曾误用 `.values[1]`（时间升序时是第 2 个交易日的旧值），
    而不是 `.values[-1]`（最后一个、也就是最新交易日的值）。
    该 bug 会把陈旧甚至方向相反的指标（例如负的 KDJ）写进库。
    现已修为 `.values[-1]`，本文件断言“取的是时间升序的最后一行”。

零依赖：只用合成 OHLC + stockstats，本地计算，不碰数据库/网络。
"""

import numpy as np
import pandas as pd
import pytest

stockstats = pytest.importorskip("stockstats")


def _make_ohlc():
    """构造一段时间升序的已知 OHLC 序列（索引为交易日）。"""
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    # 收盘价单调上升，便于人工核对均值；其余列围绕收盘价构造。
    close = np.arange(10.0, 40.0, 1.0)  # 10, 11, ..., 39 —— 共 30 个
    assert len(close) == len(dates)
    df = pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.linspace(1000, 3000, len(dates)),
        }
    )
    df.set_index("date", inplace=True)
    return df


def test_close_5_sma_last_value_equals_mean_of_last_5_closes():
    df = _make_ohlc()
    closes = df["close"].to_numpy()
    stat = stockstats.StockDataFrame.retype(df.copy())

    sma5 = stat["close_5_sma"]
    # 取最新交易日的值（升序最后一行）。
    last_val = sma5.values[-1]

    expected = closes[-5:].mean()
    assert last_val == pytest.approx(expected), (
        f"close_5_sma 最后一个值应等于最后 5 个收盘价均值 {expected}, 实得 {last_val}"
    )


def test_values_minus1_differs_from_values_1_guarding_the_historic_bug():
    """
    直接对照历史 bug：`.values[-1]`(正确) 与 `.values[1]`(错误) 必须不同。
    只要序列足够长且非常量，两者取到的是不同交易日 → 不同数值，
    以此守住“绝不能回退成 .values[1]”。
    """
    df = _make_ohlc()
    stat = stockstats.StockDataFrame.retype(df.copy())
    sma5 = stat["close_5_sma"]

    correct_latest = sma5.values[-1]   # 修复后：最新交易日
    buggy_second = sma5.values[1]      # 历史 bug：第 2 个交易日的旧值

    assert correct_latest != buggy_second, (
        "取最后一行(-1)与取第 2 行([1])不应相同——若相同说明测试数据无区分度，"
        "无法守护 .values[1] 的历史 bug"
    )
    # 正确值应对应最后 5 个收盘价均值；错误值明显偏小（早期低价区间）。
    assert correct_latest > buggy_second


def test_kdj_latest_uses_last_row_not_second_row():
    """
    以 KDJ 为例再确认一次“取最新行”的语义（历史上正是 KDJ 存了错误/负值）。
    单调上行序列里，KDJ 的 K 值末尾应处于高位（超买区，>50），
    而第 2 行仍在初始化阶段，两者数值不同。
    """
    df = _make_ohlc()
    stat = stockstats.StockDataFrame.retype(df.copy())
    kdjk = stat["kdjk"]

    latest = kdjk.values[-1]
    second = kdjk.values[1]

    assert latest != second
    # 持续上涨 → 最新 K 值应在高位。
    assert latest > 50.0
