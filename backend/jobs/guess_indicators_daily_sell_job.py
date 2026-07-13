#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import libs.common as common
import pandas as pd
import numpy as np
import math
import datetime
import stockstats
from sqlalchemy import text

# 需要数值化后参与条件判断的列。
_NUM_COLS = ["last_price", "change_percent", "kdjj", "macd", "macds", "boll", "boll_lb",
             "close_5_sma", "close_10_sma", "close_20_sma", "close_60_sma"]

SELL_TOP_N = 20
# 单策略「均线空头」过宽，分数过低的剔除，避免刷屏。
WEAK_MA_ONLY_MIN_SCORE = 48.0


# 设置卖出数据。采用“多策略并集”找见顶/走坏信号，并在 strategy 列标注原因。
# 说明：旧逻辑用“KDJ 超卖(<20)”当卖出信号，语义其实相反（超卖常预示反弹）。
#       现改为见顶回落 / 均线空头 / 跌破布林下轨等走坏信号；并对空头/下轨加确认，控制数量。
def stat_all_lite_sell(tmp_datetime):
    datetime_str = (tmp_datetime).strftime("%Y-%m-%d")
    datetime_int = (tmp_datetime).strftime("%Y%m%d")
    print("datetime_str:", datetime_str)
    print("datetime_int:", datetime_int)

    try:
        # 删除老数据。
        del_sql = " DELETE FROM `stock_data`.`guess_indicators_lite_sell_daily` WHERE `date`= '%s' " % datetime_int
        common.insert(del_sql)
    except Exception as e:
        print("error :", e)

    # 基础过滤：非 ST、价>2，避免垃圾股噪音。
    sql_1 = text("""
        SELECT * FROM stock_data.guess_indicators_daily
        WHERE `date` = :datetime
          AND locate('ST', `name`) = 0
          AND last_price > :min_price
    """)
    data = pd.read_sql(sql=sql_1, con=common.engine(),
                       params={"datetime": datetime_int, "min_price": 2})
    data = data.drop_duplicates(subset="code", keep="last")
    print("######## base rows ########:", len(data))
    if len(data) == 0:
        return

    for c in _NUM_COLS:
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors="coerce").fillna(0)

    # 策略1：见顶回落 —— 曾强势(J>80) 但 MACD 转空且跌破 5 日线。
    d1 = (data.kdjj > 80) & (data.macd < data.macds) & (data.last_price < data.close_5_sma)
    # 策略2：均线空头 —— 空头排列 + MACD 空头 + 跌破 MA5（单独空头排列过宽，已收紧）。
    d2 = ((data.close_5_sma < data.close_10_sma) & (data.close_10_sma < data.close_20_sma)
          & (data.close_20_sma < data.close_60_sma) & (data.close_60_sma > 0)
          & (data.macd < data.macds) & (data.last_price < data.close_5_sma))
    # 策略3：跌破布林下轨 —— 破位且当日收跌，避免假破。
    d3 = ((data.boll_lb > 0) & (data.last_price < data.boll_lb)
          & (data.change_percent < 0))

    data["strategy"] = ""
    data.loc[d1, "strategy"] += "见顶回落,"
    data.loc[d2, "strategy"] += "均线空头,"
    data.loc[d3, "strategy"] += "跌破下轨,"
    data["strategy"] = data["strategy"].str.rstrip(",")

    # 卖出强度分：命中策略数为主，叠加破位幅度/J 值/跌破均线程度，便于 Top-N。
    eps = 1e-6
    hit = d1.astype(int) + d2.astype(int) + d3.astype(int)
    score_hit = hit / 3.0 * 50.0
    # 跌破下轨越深分越高。
    below_lb = np.clip((data.boll_lb - data.last_price) / (data.boll_lb.abs() + eps), 0, 1) * 20.0
    # J 仍处高位却转弱，见顶意味更强。
    j_high = np.clip((data.kdjj - 80.0) / 40.0, 0, 1) * 15.0
    # 跌破 MA5 的幅度。
    below_ma5 = np.clip((data.close_5_sma - data.last_price) / (data.close_5_sma.abs() + eps), 0, 1) * 15.0
    data["score"] = (score_hit + below_lb + j_high + below_ma5).clip(0, 100).round(2)
    # 多策略同时命中优先：命中 >=2 额外 +15。
    multi = hit >= 2
    data.loc[multi, "score"] = (data.loc[multi, "score"] + 15.0).clip(0, 100).round(2)
    print("卖出多策略加分(+15): 命中>=2 共 %d 只" % int(multi.sum()))

    picked = data[d1 | d2 | d3].copy()
    print("######## strategy union ########:", len(picked))

    # 剔除弱「仅均线空头」：单策略且分数偏低，历史上最容易刷屏。
    if len(picked) > 0:
        weak = ((picked["strategy"] == "均线空头")
                & (picked["score"] < WEAK_MA_ONLY_MIN_SCORE))
        before = len(picked)
        picked = picked[~weak].copy()
        print("弱均线空头过滤(score<%.1f): %d -> %d"
              % (WEAK_MA_ONLY_MIN_SCORE, before, len(picked)))

    picked = picked.sort_values("score", ascending=False).head(SELL_TOP_N)
    print("######## stat_all_lite_sell len data ########:", len(picked), "(Top-%d)" % SELL_TOP_N)
    try:
        print("命中策略分布:", picked["strategy"].value_counts().to_dict())
        print("score 分布:", picked["score"].describe().round(2).to_dict())
    except Exception as e:
        print("count error:", e)

    if len(picked) == 0:
        return
    try:
        common.insert(" ALTER TABLE `stock_data`.`guess_indicators_lite_sell_daily` "
                      " ADD COLUMN `score` double(20,2) DEFAULT NULL ")
    except Exception as e:
        print("add score column skip:", e)
    try:
        common.insert_db(picked, "guess_indicators_lite_sell_daily", False, "`date`,`code`")
    except Exception as e:
        print("error :", e)



# main函数入口
if __name__ == '__main__':
    # 使用方法传递。
    # 二次筛选数据。直接计算买卖股票数据。
    tmp_datetime = common.run_with_args(stat_all_lite_sell)
