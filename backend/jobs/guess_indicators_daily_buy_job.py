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
_NUM_COLS = ["last_price", "change_percent", "kdjk", "kdjd", "kdjj",
             "macd", "macds", "boll", "vr", "vr_6_sma",
             "close_5_sma", "close_10_sma", "close_20_sma", "close_60_sma", "high_20_max",
             "rsi_6"]


def _bare_code(code):
    """统一成 6 位裸代码，兼容 sh600519 / sz000001 / 600519。"""
    c = str(code).strip().lower()
    if c.startswith(("sh", "sz", "bj")):
        c = c[2:]
    return c


def _market_temperature():
    """与 dashboardHandler 一致：最新 stock_zh_a_spot_em 上涨家数占比(0~100)。"""
    try:
        latest = pd.read_sql(
            text("SELECT max(`date`) AS d FROM stock_zh_a_spot_em"),
            common.engine())
        d = latest.iloc[0]["d"] if len(latest) else None
        if d is None or (isinstance(d, float) and np.isnan(d)):
            print("市场温度: 无 spot 数据，默认 50.0")
            return 50.0, None
        stat = pd.read_sql(text("""
            SELECT
              sum(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END) AS up_count,
              sum(CASE WHEN change_percent < 0 THEN 1 ELSE 0 END) AS down_count
            FROM stock_zh_a_spot_em
            WHERE `date` = :d AND `open` > 0 AND `volume` > 0
        """), common.engine(), params={"d": d})
        up = int(stat.iloc[0]["up_count"] or 0)
        down = int(stat.iloc[0]["down_count"] or 0)
        temp = round(up * 100.0 / (up + down), 1) if (up + down) > 0 else 50.0
        print("市场温度: %.1f (date=%s, up=%d, down=%d)" % (temp, d, up, down))
        return temp, d
    except Exception as e:
        print("市场温度计算失败，默认 50.0:", e)
        return 50.0, None


def _lhb_net_buy_codes(datetime_int):
    """当日龙虎榜净买额>0 的裸代码集合；无表/无数据则空集。"""
    try:
        df = pd.read_sql(text("""
            SELECT `code`, `net_amount` FROM stock_lhb_detail_daily
            WHERE `date` = :d
        """), common.engine(), params={"d": datetime_int})
        if df is None or len(df) == 0:
            print("龙虎榜加分: 当日无数据，跳过")
            return set()
        df["net_amount"] = pd.to_numeric(df["net_amount"], errors="coerce").fillna(0)
        codes = set(_bare_code(c) for c in df.loc[df["net_amount"] > 0, "code"])
        print("龙虎榜净买入加分(+8): 当日净买>0 共 %d 只" % len(codes))
        return codes
    except Exception as e:
        print("龙虎榜加分跳过(无表/异常):", e)
        return set()


def _log_fund_flow_top3(datetime_int):
    """板块净流入 Top3 仅写日志，不做个股映射。"""
    for table, label in (("stock_fund_flow_industry", "行业"),
                         ("stock_fund_flow_concept", "概念")):
        try:
            df = pd.read_sql(text("""
                SELECT `name`, `net_amount` FROM `%s`
                WHERE `date` = :d
                ORDER BY `net_amount` DESC LIMIT 3
            """ % table), common.engine(), params={"d": datetime_int})
            if df is None or len(df) == 0:
                print("%s资金流 Top3: 当日无数据" % label)
                continue
            parts = ["%s(%.0f)" % (r["name"], float(r["net_amount"] or 0))
                     for _, r in df.iterrows()]
            print("%s资金流 Top3: %s" % (label, ", ".join(parts)))
        except Exception as e:
            print("%s资金流 Top3 跳过:" % label, e)


### 对每日指标数据做二次筛选，采用“多策略并集”：
### 每条策略独立选股，命中任一即入选，并在 strategy 列标注命中原因。
### 数据源限制：东财实时快照被拦截，仅有日线 OHLC，故量比/换手率/市值字段不可用；
### 量能确认统一改用从历史成交量自算的 VR 指标（vr > vr_6_sma）。
def stat_all_lite_buy(tmp_datetime):
    datetime_str = (tmp_datetime).strftime("%Y-%m-%d")
    datetime_int = (tmp_datetime).strftime("%Y%m%d")
    print("datetime_str:", datetime_str)
    print("datetime_int:", datetime_int)

    try:
        # 删除老数据。
        del_sql = " DELETE FROM `stock_data`.`guess_indicators_lite_buy_daily` WHERE `date`= '%s' " % datetime_int
        common.insert(del_sql)
    except Exception as e:
        print("error :", e)

    # 取当日通过“基础质量过滤”的候选（非ST、价>2、未涨停），含全部指标列。
    sql_1 = text("""
        SELECT * FROM stock_data.guess_indicators_daily
        WHERE `date` = :datetime
          AND locate('ST', `name`) = 0
          AND last_price > :min_price
          AND change_percent < :max_change
    """)
    params_1 = {"datetime": datetime_int, "min_price": 2, "max_change": 9.5}
    data = pd.read_sql(sql=sql_1, con=common.engine(), params=params_1)
    data = data.drop_duplicates(subset="code", keep="last")
    print("######## base candidates ########:", len(data))
    if len(data) == 0:
        return

    for c in _NUM_COLS:
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors="coerce").fillna(0)

    # 策略1：KDJ 强势 —— 超买强势 + MACD 多头 + 站上 BOLL 中轨 + 放量。
    s1 = ((data.kdjk > 80) & (data.kdjd > 70) & (data.kdjj > 90)
          & (data.macd > data.macds) & (data.last_price > data.boll)
          & (data.vr > data.vr_6_sma))
    # 策略2：均线多头排列 —— MA5>MA10>MA20>MA60 且站上 MA5 + MACD 多头。
    s2 = ((data.close_5_sma > data.close_10_sma) & (data.close_10_sma > data.close_20_sma)
          & (data.close_20_sma > data.close_60_sma) & (data.last_price > data.close_5_sma)
          & (data.macd > data.macds))
    # 注：原“策略3 放量突破(创20日新高)”经回测为显著负超额(约 -2.5%~-3.5%)，
    #     且加趋势/MACD 过滤越严越差，属追高被套，已下线。high_20_max 仍保留用于展示。

    data["strategy"] = ""
    data.loc[s1, "strategy"] += "KDJ强势,"
    data.loc[s2, "strategy"] += "均线多头,"
    data["strategy"] = data["strategy"].str.rstrip(",")

    # 综合打分（0~100）：命中策略条数权重最大(占 45)，叠加多个信号强度归一化分量(占 55)。
    # 各分量都做 clip 截断到 [0,1] 后再乘权重，保证可比、不被极端值放大。
    eps = 1e-6
    hit_count = s1.astype(int) + s2.astype(int)
    score_strategy = hit_count / 2.0 * 45.0
    # KDJ 超买强势：kdjk 超过 80 的幅度，高出 20(即达到 100) 记满分。
    kdj_str = np.clip((data.kdjk - 80.0) / 20.0, 0, 1) * 10.0
    # MACD 多头强度：(macd - macds) 相对二者规模的占比，避免绝对值量纲差异。
    macd_str = np.clip((data.macd - data.macds) / (data.macd.abs() + data.macds.abs() + eps), 0, 1) * 10.0
    # 价格站上 MA5 幅度：高出 5% 记满分。
    ma5_str = np.clip((data.last_price - data.close_5_sma) / (data.close_5_sma + eps) / 0.05, 0, 1) * 8.0
    # 价格站上 BOLL 中轨幅度：高出 5% 记满分。
    boll_str = np.clip((data.last_price - data.boll) / (data.boll + eps) / 0.05, 0, 1) * 7.0
    # RSI6 健康区间：以 65 为中心，50~80 视为健康，越居中得分越高(±15 外归零)。
    rsi_str = np.clip(1.0 - (data.rsi_6 - 65.0).abs() / 15.0, 0, 1) * 10.0
    # 量能比：vr 相对 vr_6_sma 的放大程度，放大到 2 倍(即 +100%) 记满分。
    vr_str = np.clip((data.vr / (data.vr_6_sma + eps)) - 1.0, 0, 1) * 10.0

    data["score"] = (score_strategy + kdj_str + macd_str + ma5_str
                     + boll_str + rsi_str + vr_str).clip(0, 100).round(2)

    # 龙虎榜净买入交叉加分（有则 +8；无表/无数据跳过）。
    lhb_buy = _lhb_net_buy_codes(datetime_int)
    if lhb_buy:
        bare = data["code"].map(_bare_code)
        lhb_hit = bare.isin(lhb_buy)
        data.loc[lhb_hit, "score"] = (data.loc[lhb_hit, "score"] + 8.0).clip(0, 100).round(2)
        print("龙虎榜净买入命中候选:", int(lhb_hit.sum()))
    _log_fund_flow_top3(datetime_int)

    # 并集入选。
    picked = data[s1 | s2].copy()
    print("######## strategy union ########:", len(picked))

    # 市场温度过滤：偏冷时收紧候选；极冷时 TopN 降为 10。
    temperature, _ = _market_temperature()
    BUY_TOP_N = 20
    if temperature < 30:
        BUY_TOP_N = 10
        print("温度过滤: temperature=%.1f < 30，买入 TopN 降为 %d" % (temperature, BUY_TOP_N))
    else:
        print("温度过滤: temperature=%.1f，买入 TopN 保持 %d" % (temperature, BUY_TOP_N))

    if temperature < 45 and len(picked) > 0:
        # 偏冷：保留「KDJ强势」或原候选 score 前半（更严）。
        median_score = float(picked["score"].median())
        keep = (picked["strategy"].str.contains("KDJ强势", na=False)
                | (picked["score"] >= median_score))
        before = len(picked)
        picked = picked[keep].copy()
        print("温度过滤: temperature=%.1f < 45，要求命中KDJ强势或 score>=中位数(%.2f)；"
              "%d -> %d" % (temperature, median_score, before, len(picked)))
    else:
        print("温度过滤: temperature=%.1f >= 45，不做额外收紧" % temperature)

    picked = picked.sort_values("score", ascending=False).head(BUY_TOP_N)
    print("######## stat_all_lite_buy len data ########:", len(picked), "(Top-%d)" % BUY_TOP_N)
    try:
        print("命中策略分布:", picked["strategy"].value_counts().to_dict())
        print("score 分布:", picked["score"].describe().round(2).to_dict())
    except Exception as e:
        print("count error:", e)

    if len(picked) == 0:
        return

    # 给线上表补 score 列（已存在则忽略），保证写入不因缺列失败。
    try:
        common.insert(" ALTER TABLE `stock_data`.`guess_indicators_lite_buy_daily` "
                      " ADD COLUMN `score` double(20,2) DEFAULT NULL ")
    except Exception as e:
        print("add score column skip:", e)

    try:
        common.insert_db(picked, "guess_indicators_lite_buy_daily", False, "`date`,`code`")
    except Exception as e:
        print("error :", e)



# main函数入口
if __name__ == '__main__':
    # 使用方法传递。
    # 二次筛选数据。直接计算买卖股票数据。
    tmp_datetime = common.run_with_args(stat_all_lite_buy)
