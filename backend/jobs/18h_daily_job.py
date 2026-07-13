#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import libs.common as common
import sys
import os
import time
import pandas as pd
import numpy as np
from sqlalchemy.types import NVARCHAR
from sqlalchemy import inspect
import datetime
import akshare as ak
import traceback
import MySQLdb


def _spot_source_log_dir():
    """与 monitor 一致：Linux 生产优先 /data/logs；Windows 本地用 backend/logs。

    Windows 上 `/data/logs` 会落到当前盘符根目录（如 E:\\data\\logs），不可用作生产路径。
    """
    fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
    fallback = os.path.abspath(fallback)
    os.makedirs(fallback, exist_ok=True)
    if sys.platform.startswith("win"):
        return fallback
    prod_dir = "/data/logs"
    try:
        os.makedirs(prod_dir, exist_ok=True)
        if os.path.isdir(prod_dir) and os.access(prod_dir, os.W_OK):
            return prod_dir
    except Exception:
        pass
    return fallback


def write_spot_source(datetime_int, source):
    """写入当日 spot 数据源状态文件，供 run_daily / monitor 读取。"""
    path = os.path.join(_spot_source_log_dir(), "spot_source.%s.txt" % datetime_int)
    content = "source=%s\n" % source
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("spot_source file written: %s (%s)" % (path, content.strip()))
    return path

# 600开头的股票是上证A股，属于大盘股
# 600开头的股票是上证A股，属于大盘股，其中6006开头的股票是最早上市的股票，
# 6016开头的股票为大盘蓝筹股；900开头的股票是上证B股；
# 000开头的股票是深证A股，001、002开头的股票也都属于深证A股，
# 其中002开头的股票是深证A股中小企业股票；
# 200开头的股票是深证B股；
# 300开头的股票是创业板股票；400开头的股票是三板市场股票。
def stock_a(code):
    # 兼容裸代码(600519)和带市场前缀(sh600519 / sz000001)。
    c = str(code).lower()
    if c.startswith(("sh", "sz", "bj")):
        c = c[2:]
    # 沪深主板(含603/605/003) + 中小板；与上周五东财~3000只口径对齐。
    # 创业板/科创板暂不纳入（全量预热易把进程打崩，后续可单独加）。
    if c.startswith(("600", "601", "603", "605",
                     "000", "001", "002", "003")):
        return True
    return False


def normalize_spot_code(code):
    """统一成 sh/sz/bj + 6 位，方便与历史缓存/已有库一致。"""
    c = str(code).strip().lower()
    if c.startswith(("sh", "sz", "bj")):
        return c
    prefix = common.gp_type_szsh(c)
    return (prefix + c) if prefix else c
# 过滤掉 st 股票。
def stock_a_filter_st(name):
    # print(code)
    # print(type(code))
    # 上证A股  # 深证A股
    if name.find("ST") == -1:
        return True
    else:
        return False

# 过滤价格，如果没有基本上是退市了。
def stock_a_filter_price(latest_price):
    # float 在 pandas 里面判断 空。
    if np.isnan(latest_price):
        return False
    else:
        return True


# stock_zh_a_spot_em 的目标列（顺序即东财快照的既有位置映射）。
SPOT_EM_COLUMNS = ['index', 'code', 'name', 'last_price', 'change_percent', 'change_amount',
    'volume', 'turnover', 'amplitude', 'high', 'low', 'open', 'closed', 'volume_ratio',
    'turnover_rate', 'pe_ratio', 'pb_ratio', 'market_cap', 'circulating_market_cap', 'rise_speed',
    'change_5min', 'change_ercent_60day', 'ytd_change_percent']

# 东财中文列名 -> 目标英文列名。akshare 若微调列顺序，只要列名不变即可稳健映射。
SPOT_EM_CN_MAP = {
    '序号': 'index', '代码': 'code', '名称': 'name', '最新价': 'last_price',
    '涨跌幅': 'change_percent', '涨跌额': 'change_amount', '成交量': 'volume',
    '成交额': 'turnover', '振幅': 'amplitude', '最高': 'high', '最低': 'low',
    '今开': 'open', '昨收': 'closed', '量比': 'volume_ratio', '换手率': 'turnover_rate',
    '市盈率-动态': 'pe_ratio', '市净率': 'pb_ratio', '总市值': 'market_cap',
    '流通市值': 'circulating_market_cap', '涨速': 'rise_speed', '5分钟涨跌': 'change_5min',
    '60日涨跌幅': 'change_ercent_60day', '年初至今涨跌幅': 'ytd_change_percent',
}

# 计算指标依赖的关键字段，整列为 0/空时给出数据质量告警。
SPOT_EM_QUALITY_KEYS = ['turnover_rate', 'volume_ratio', 'market_cap', 'circulating_market_cap']


def map_spot_em_columns(data):
    """稳健地把 stock_zh_a_spot_em 的返回列映射为目标列。

    策略（从稳到糙）:
      1) 若返回列是东财中文列名，按“列名”映射（对 akshare 调整列顺序免疫）。
      2) 否则若列数与既有映射一致，退回“按位置”映射（兼容旧行为）。
      3) 两者都不满足则抛出清晰的 schema 变化错误，避免把错位数据静默写库。
    返回按 SPOT_EM_COLUMNS 排列的 DataFrame。
    """
    cols = list(data.columns)
    cn_hit = sum(1 for c in cols if c in SPOT_EM_CN_MAP)

    # 1) 按中文列名映射（大多数列命中即认为是命名式返回）。
    if cn_hit >= max(10, int(len(SPOT_EM_CN_MAP) * 0.6)):
        renamed = data.rename(columns=SPOT_EM_CN_MAP)
        missing = [t for t in SPOT_EM_COLUMNS if t not in renamed.columns]
        if missing:
            raise ValueError(
                "stock_zh_a_spot_em schema changed: 按列名映射后仍缺少字段 %s；实际返回列=%s"
                % (missing, cols))
        return renamed[SPOT_EM_COLUMNS].copy()

    # 2) 按位置映射（列名不认识，但列数一致）。
    if len(cols) == len(SPOT_EM_COLUMNS):
        print("WARNING: stock_zh_a_spot_em 返回列名不可识别，按位置映射兜底。实际列=%s" % cols)
        out = data.copy()
        out.columns = SPOT_EM_COLUMNS
        return out

    # 3) 无法安全映射，抛清晰错误。
    raise ValueError(
        "stock_zh_a_spot_em schema changed: 期望 %d 列，实际 %d 列；实际返回列=%s"
        % (len(SPOT_EM_COLUMNS), len(cols), cols))


def check_spot_em_quality(data):
    """检测关键字段是否整列为 0/空，打印数据质量 WARNING（不阻断流程）。"""
    n = len(data)
    if n == 0:
        print("WARNING: stock_zh_a_spot_em 过滤后为空，无法做数据质量检查。")
        return
    for key in SPOT_EM_QUALITY_KEYS:
        if key not in data.columns:
            continue
        col = pd.to_numeric(data[key], errors="coerce")
        zero_or_nan = int((col.isna() | (col == 0)).sum())
        if zero_or_nan == n:
            print("WARNING: 数据质量 —— 关键字段 `%s` 整列为 0/空 (%d/%d)，"
                  "可能是数据源被限流/封锁或字段错位，请核查。" % (key, zero_or_nan, n))
        elif zero_or_nan >= n * 0.9:
            print("WARNING: 数据质量 —— 关键字段 `%s` 约 %d/%d 为 0/空，占比偏高，请留意。"
                  % (key, zero_or_nan, n))

def fetch_spot_from_sina():
    """东财快照不可用时，用新浪实时行情兜底写入同一张表。

    新浪字段比东财少（无量比/换手率/市盈率/市值等），缺失列填 0，
    后续可由 backfill_fundamentals.py 用日线数据补齐。
    """
    raw = common.ak_call(ak.stock_zh_a_spot)
    if raw is None or len(raw) == 0:
        raise ValueError("stock_zh_a_spot(新浪) 返回空数据。")

    # 兼容中英文列名。
    rename = {
        "代码": "code", "名称": "name", "最新价": "last_price",
        "涨跌额": "change_amount", "涨跌幅": "change_percent",
        "昨收": "closed", "今开": "open", "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "turnover",
        "code": "code", "name": "name", "trade": "last_price",
        "pricechange": "change_amount", "changepercent": "change_percent",
        "settlement": "closed", "open": "open", "high": "high", "low": "low",
        "volume": "volume", "amount": "turnover",
    }
    df = raw.rename(columns={c: rename[c] for c in raw.columns if c in rename}).copy()
    need = ["code", "name", "last_price", "change_percent", "change_amount",
            "volume", "turnover", "high", "low", "open", "closed"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError("sina spot 缺字段 %s；实际列=%s" % (missing, list(raw.columns)))

    for c in need:
        if c not in ("code", "name"):
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # 振幅(%) = (高-低)/昨收 * 100
    closed = df["closed"].replace(0, pd.NA)
    df["amplitude"] = ((df["high"] - df["low"]) / closed * 100).fillna(0).round(2)

    out = pd.DataFrame({
        "index": range(1, len(df) + 1),
        "code": df["code"].astype(str),
        "name": df["name"].astype(str),
        "last_price": df["last_price"],
        "change_percent": df["change_percent"],
        "change_amount": df["change_amount"],
        "volume": df["volume"],
        "turnover": df["turnover"],
        "amplitude": df["amplitude"],
        "high": df["high"],
        "low": df["low"],
        "open": df["open"],
        "closed": df["closed"],
        "volume_ratio": 0.0,
        "turnover_rate": 0.0,
        "pe_ratio": 0.0,
        "pb_ratio": 0.0,
        "market_cap": 0.0,
        "circulating_market_cap": 0.0,
        "rise_speed": 0.0,
        "change_5min": 0.0,
        "change_ercent_60day": 0.0,
        "ytd_change_percent": 0.0,
    })
    print("sina spot mapped: %s rows" % len(out))
    return out


####### 3.pdf 方法。宏观经济数据
# 接口全部有错误。只专注股票数据。
def stat_all(tmp_datetime):

    datetime_str = (tmp_datetime).strftime("%Y-%m-%d")
    datetime_int = (tmp_datetime).strftime("%Y%m%d")
    print("datetime_str:", datetime_str)
    print("datetime_int:", datetime_int)

    # 股票列表（强制直连，不走梯子代理）；东财失败时自动切新浪兜底。
    try:
        data = None
        source = "eastmoney"
        try:
            data = common.ak_call(ak.stock_zh_a_spot_em)
            if data is None or len(data) == 0:
                raise ValueError("stock_zh_a_spot_em 返回空数据（可能被限流/封锁或接口变更）。")
            data = map_spot_em_columns(data)
        except Exception as em_err:
            print("eastmoney spot failed, fallback to sina:", em_err)
            source = "sina"
            data = fetch_spot_from_sina()

        check_spot_em_quality(data)
        data = data.loc[data["code"].apply(stock_a)].loc[data["name"].apply(stock_a_filter_st)].loc[
            data["last_price"].apply(stock_a_filter_price)].copy()
        data["code"] = data["code"].apply(normalize_spot_code)
        print("spot source=%s rows=%s" % (source, len(data)))
        print(data.head())
        data['date'] = datetime_int

        del_sql = " DELETE FROM `stock_zh_a_spot_em` where `date` = '%s' " % datetime_int
        common.insert(del_sql)

        data.set_index('code', inplace=True)
        data.drop('index', axis=1, inplace=True)
        common.insert_db(data, "stock_zh_a_spot_em", True, "`date`,`code`")
        print("spot insert done: source=%s date=%s rows=%s" % (source, datetime_int, len(data)))
        try:
            write_spot_source(datetime_int, source)
        except Exception as src_err:
            print("WARNING: write spot_source failed:", src_err)
    except Exception as e:
        print("error :", e)
        traceback.print_exc()



    # 龙虎榜-个股上榜统计
    # 接口: stock_lhb_ggtj_sina
    #
    # 目标地址: http://vip.stock.finance.sina.com.cn/q/go.php/vLHBData/kind/ggtj/index.phtml
    #
    # 描述: 获取新浪财经-龙虎榜-个股上榜统计
    #

    try:
        stock_lhb_ggtj_sina = common.ak_call(ak.stock_lhb_ggtj_sina, symbol="5")
        print(stock_lhb_ggtj_sina)

        stock_lhb_ggtj_sina.columns = ['code', 'name', 'ranking_times', 'sum_buy', 'sum_sell', 'net_amount', 'buy_seat',
                                       'sell_seat']

        stock_lhb_ggtj_sina = stock_lhb_ggtj_sina.loc[stock_lhb_ggtj_sina["code"].apply(stock_a)].loc[
            stock_lhb_ggtj_sina["name"].apply(stock_a_filter_st)]

        stock_lhb_ggtj_sina.set_index('code', inplace=True)
        # data_sina_lhb.drop('index', axis=1, inplace=True)
        # 删除老数据。
        stock_lhb_ggtj_sina['date'] = datetime_int  # 修改时间成为int类型。

        # 删除老数据。
        del_sql = " DELETE FROM `stock_lhb_ggtj_sina` where `date` = '%s' " % datetime_int
        common.insert(del_sql)

        common.insert_db(stock_lhb_ggtj_sina, "stock_lhb_ggtj_sina", True, "`date`,`code`")

    except Exception as e:
        print("error :", e)
        traceback.print_exc()
        


    # 每日统计
    # 接口: stock_dzjy_mrtj
    #
    # 目标地址: http://data.eastmoney.com/dzjy/dzjy_mrtj.aspx
    #
    # 描述: 获取东方财富网-数据中心-大宗交易-每日统计
    # https://akshare.akfamily.xyz/data/stock/stock.html#id318
    # import akshare as ak
    # stock_dzjy_mrtj_df = ak.stock_dzjy_mrtj(start_date='20220105', end_date='20220105')
    # print(stock_dzjy_mrtj_df)

    try:

        print("################ tmp_datetime : " + datetime_int)
        # 格式要 int类型日期
        stock_dzjy_mrtj = common.ak_call(ak.stock_dzjy_mrtj, start_date=datetime_int, end_date=datetime_int)
        print(stock_dzjy_mrtj)

        stock_dzjy_mrtj.columns = ['index', 'trade_date', 'code', 'name', 'quote_change', 'close_price', 'average_price',
                                   'overflow_rate', 'trade_number', 'sum_volume', 'sum_turnover',
                                   'turnover_market_rate']

        stock_dzjy_mrtj.set_index('code', inplace=True)
        # data_sina_lhb.drop('index', axis=1, inplace=True)
        # 删除老数据。
        stock_dzjy_mrtj['date'] = datetime_int  # 修改时间成为int类型。
        stock_dzjy_mrtj.drop('trade_date', axis=1, inplace=True)
        stock_dzjy_mrtj.drop('index', axis=1, inplace=True)

        # 数据保留2位小数
        try:
            stock_dzjy_mrtj = stock_dzjy_mrtj.loc[stock_dzjy_mrtj["code"].apply(stock_a)].loc[
                stock_dzjy_mrtj["name"].apply(stock_a_filter_st)]

            stock_dzjy_mrtj["average_price"] = stock_dzjy_mrtj["average_price"].round(2)
            stock_dzjy_mrtj["overflow_rate"] = stock_dzjy_mrtj["overflow_rate"].round(4)
            stock_dzjy_mrtj["turnover_market_rate"] = stock_dzjy_mrtj["turnover_market_rate"].round(6)
        except Exception as e:
            print("round error :", e)
            traceback.print_exc()

        # 删除老数据。
        del_sql = " DELETE FROM `stock_dzjy_mrtj` where `date` = '%s' " % datetime_int
        common.insert(del_sql)

        print(stock_dzjy_mrtj)

        common.insert_db(stock_dzjy_mrtj, "stock_dzjy_mrtj", True, "`date`,`code`")

    except Exception as e:
        print("error :", e)
        traceback.print_exc()

# main函数入口
if __name__ == '__main__':
    # 执行数据初始化。
    # 使用方法传递。
    tmp_datetime = common.run_with_args(stat_all)
