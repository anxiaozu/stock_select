# -*- coding: utf-8 -*-
"""
历史缓存索引规范化 —— 回归测试。

守护的历史 bug：
    历史 DataFrame 的索引曾是原生 `datetime.date` 对象（object 索引）。
    用字符串日期做标签切片 `df.loc["2026-04-01":"2026-07-10"]` 时，
    pandas 需要把字符串与 date 比较，会抛 TypeError。
    修复：统一 `df.index = pd.to_datetime(df.index)` 规范为 Timestamp（DatetimeIndex），
    这样字符串切片正常工作。

本文件独立复现该行为：
- 未规范化的 date 索引 → 字符串切片报错（说明修复必要性）。
- 规范化后的（原 date）索引 → 字符串切片正常。
- 本就是 Timestamp 的索引 → 字符串切片正常。
"""

import datetime

import pandas as pd
import pytest


def _make_frame(index):
    return pd.DataFrame(
        {"open": range(len(index)), "close": range(len(index))},
        index=index,
    )


def _date_index():
    """索引为原生 datetime.date（升序，跨 4 月~7 月）。"""
    base = datetime.date(2026, 4, 1)
    dates = [base + datetime.timedelta(days=i) for i in range(100)]  # 到 7 月中旬
    return dates


SLICE_START = "2026-04-01"
SLICE_END = "2026-07-10"


def test_unnormalized_date_index_string_slice_raises():
    """未规范化的 date-object 索引，用字符串切片应触发异常（正是历史 bug）。"""
    df = _make_frame(pd.Index(_date_index(), dtype=object))
    # object 索引里放的是 datetime.date；字符串标签切片无法与 date 比较。
    with pytest.raises(TypeError):
        _ = df.loc[SLICE_START:SLICE_END]


def test_normalized_from_date_index_string_slice_works():
    """经 pd.to_datetime 规范化后，原 date 索引可用字符串日期切片。"""
    df = _make_frame(pd.Index(_date_index(), dtype=object))
    df.index = pd.to_datetime(df.index)  # 修复动作
    assert isinstance(df.index, pd.DatetimeIndex)

    sub = df.loc[SLICE_START:SLICE_END]
    # 4/1 ~ 7/10 含首尾，应有 101 天中被截取的部分；这里数据到 7/9 (第100天=4/1+99)。
    assert len(sub) > 0
    assert sub.index.min() >= pd.Timestamp(SLICE_START)
    assert sub.index.max() <= pd.Timestamp(SLICE_END)
    # 首行应为 2026-04-01。
    assert sub.index[0] == pd.Timestamp("2026-04-01")


def test_timestamp_index_string_slice_works():
    """索引本就是 Timestamp（DatetimeIndex）时，字符串切片同样正常。"""
    idx = pd.date_range("2026-04-01", periods=100, freq="D")
    df = _make_frame(idx)
    assert isinstance(df.index, pd.DatetimeIndex)

    sub = df.loc[SLICE_START:SLICE_END]
    assert len(sub) > 0
    assert sub.index.min() >= pd.Timestamp(SLICE_START)
    assert sub.index.max() <= pd.Timestamp(SLICE_END)


def test_to_datetime_is_idempotent_on_timestamp_index():
    """对已是 Timestamp 的索引再次 pd.to_datetime 应保持不变（规范化是幂等的）。"""
    idx = pd.date_range("2026-04-01", periods=10, freq="D")
    df = _make_frame(idx)
    normalized = pd.to_datetime(df.index)
    assert normalized.equals(df.index)
    assert isinstance(normalized, pd.DatetimeIndex)


def test_both_index_kinds_agree_after_normalization():
    """
    规范化后：由 date 转来的索引 与 原生 Timestamp 索引，
    对同一字符串切片应产出等价结果（相同长度与相同起止）。
    """
    df_from_date = _make_frame(pd.Index(_date_index(), dtype=object))
    df_from_date.index = pd.to_datetime(df_from_date.index)

    df_ts = _make_frame(pd.date_range("2026-04-01", periods=100, freq="D"))

    a = df_from_date.loc[SLICE_START:SLICE_END]
    b = df_ts.loc[SLICE_START:SLICE_END]
    assert len(a) == len(b)
    assert a.index[0] == b.index[0]
    assert a.index[-1] == b.index[-1]
