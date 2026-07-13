#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""龙虎榜：每日明细 + 买卖席位（营业部名称）。

数据源：东财 datacenter（stock_lhb_detail_em + 席位明细接口）。
写入：
  stock_lhb_detail_daily  每日上榜个股摘要
  stock_lhb_seat_detail   每只股票的买入/卖出营业部明细
"""
import datetime
import sys
import time

import pandas as pd
import requests

sys.path.append("/data/stock")
import libs.common as common


def _num(x, default=0.0):
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return default
        return float(x)
    except Exception:
        return default


def fetch_daily_list(date_int):
    import akshare as ak
    df = common.ak_call(ak.stock_lhb_detail_em, start_date=date_int, end_date=date_int)
    if df is None or df.empty:
        return pd.DataFrame()
    # 按列位置映射，避免控制台编码干扰中文列名。
    # 已知顺序: 序号,代码,名称,上榜日,解读,收盘价,涨跌幅,净买额,买入额,卖出额,成交额,
    #           市场总成交额,净买占比,成交占比,换手率,流通市值,上榜原因,...
    cols = list(df.columns)
    out = pd.DataFrame({
        "date": date_int,
        "code": df[cols[1]].astype(str),
        "name": df[cols[2]].astype(str),
        "interpret": df[cols[4]].astype(str),
        "close_price": df[cols[5]].apply(_num),
        "change_percent": df[cols[6]].apply(_num),
        "net_amount": df[cols[7]].apply(_num),
        "buy_amount": df[cols[8]].apply(_num),
        "sell_amount": df[cols[9]].apply(_num),
        "lhb_amount": df[cols[10]].apply(_num),
        "market_amount": df[cols[11]].apply(_num),
        "net_ratio": df[cols[12]].apply(_num),
        "amount_ratio": df[cols[13]].apply(_num),
        "turnover_rate": df[cols[14]].apply(_num),
        "circulating_market_cap": df[cols[15]].apply(_num),
        "reason": df[cols[16]].astype(str),
    })
    # 过滤 ST / 退市整理
    out = out[~out["name"].str.contains("ST|退", regex=True)].copy()
    # 同一股票可能因多个上榜原因重复出现，按净买额保留一条，原因合并。
    if not out.empty:
        out["reason"] = out.groupby("code")["reason"].transform(
            lambda s: " | ".join(dict.fromkeys([str(x) for x in s if str(x) and str(x) != "nan"])))
        out = out.sort_values("buy_amount", ascending=False).drop_duplicates(
            subset=["code"], keep="first").reset_index(drop=True)
    return out


def fetch_seats(symbol, date_int, side):
    """side: BUY / SELL -> DataFrame of seats."""
    report = "RPT_BILLBOARD_DAILYDETAILSBUY" if side == "BUY" else "RPT_BILLBOARD_DAILYDETAILSSELL"
    sortcol = "BUY" if side == "BUY" else "SELL"
    d = "%s-%s-%s" % (date_int[:4], date_int[4:6], date_int[6:])
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": report,
        "columns": "ALL",
        "filter": "(TRADE_DATE='%s')(SECURITY_CODE=\"%s\")" % (d, symbol),
        "pageNumber": "1",
        "pageSize": "50",
        "sortTypes": "-1",
        "sortColumns": sortcol,
        "source": "WEB",
        "client": "WEB",
    }
    with common.direct_network():
        r = requests.get(
            url, params=params, timeout=20,
            headers={"User-Agent": "Mozilla/5.0",
                     "Referer": "https://data.eastmoney.com/stock/lhb.html"})
    data = ((r.json().get("result") or {}) or {}).get("data") or []
    return pd.DataFrame(data)


def ensure_tables():
    common.insert("""
    CREATE TABLE IF NOT EXISTS `stock_lhb_detail_daily` (
      `date` varchar(255) NOT NULL,
      `code` varchar(255) NOT NULL,
      `name` varchar(255) DEFAULT NULL,
      `interpret` varchar(255) DEFAULT NULL,
      `close_price` double(20,2) DEFAULT NULL,
      `change_percent` double(20,2) DEFAULT NULL,
      `net_amount` double(20,2) DEFAULT NULL,
      `buy_amount` double(20,2) DEFAULT NULL,
      `sell_amount` double(20,2) DEFAULT NULL,
      `lhb_amount` double(20,2) DEFAULT NULL,
      `market_amount` double(20,2) DEFAULT NULL,
      `net_ratio` double(20,4) DEFAULT NULL,
      `amount_ratio` double(20,4) DEFAULT NULL,
      `turnover_rate` double(20,2) DEFAULT NULL,
      `circulating_market_cap` double(20,2) DEFAULT NULL,
      `reason` varchar(512) DEFAULT NULL,
      PRIMARY KEY (`date`,`code`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    common.insert("""
    CREATE TABLE IF NOT EXISTS `stock_lhb_seat_detail` (
      `date` varchar(255) NOT NULL,
      `code` varchar(255) NOT NULL,
      `name` varchar(255) DEFAULT NULL,
      `side` varchar(16) NOT NULL,
      `rank_no` int(11) DEFAULT NULL,
      `dept_name` varchar(255) DEFAULT NULL,
      `buy_amount` double(20,2) DEFAULT NULL,
      `sell_amount` double(20,2) DEFAULT NULL,
      `net_amount` double(20,2) DEFAULT NULL,
      `reason` varchar(512) DEFAULT NULL,
      PRIMARY KEY (`date`,`code`,`side`,`rank_no`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)


def stat_all(tmp_datetime):
    date_int = tmp_datetime.strftime("%Y%m%d")
    print("lhb detail date:", date_int)
    ensure_tables()

    daily = fetch_daily_list(date_int)
    print("daily list rows:", len(daily))
    if daily.empty:
        print("no lhb data"); return

    common.insert("DELETE FROM `stock_lhb_detail_daily` WHERE `date`='%s'" % date_int)
    common.insert_db(daily, "stock_lhb_detail_daily", False, "`date`,`code`")

    # 席位明细
    common.insert("DELETE FROM `stock_lhb_seat_detail` WHERE `date`='%s'" % date_int)
    seat_rows = []
    for i, r in daily.iterrows():
        code = str(r["code"])
        name = str(r["name"])
        for side, side_cn in (("BUY", "买入"), ("SELL", "卖出")):
            try:
                sdf = fetch_seats(code, date_int, side)
            except Exception as e:
                print("seat fail", code, side, e)
                continue
            if sdf is None or sdf.empty:
                continue
            # 过滤汇总型“自然人/机构/中小投资者”可保留，便于看结构；营业部名称照常展示。
            for idx, s in sdf.iterrows():
                seat_rows.append({
                    "date": date_int,
                    "code": code,
                    "name": name,
                    "side": side_cn,
                    "rank_no": int(idx) + 1,
                    "dept_name": str(s.get("OPERATEDEPT_NAME") or ""),
                    "buy_amount": _num(s.get("BUY")),
                    "sell_amount": _num(s.get("SELL")),
                    "net_amount": _num(s.get("NET")),
                    "reason": str(s.get("EXPLANATION") or r.get("reason") or ""),
                })
        if (i + 1) % 10 == 0:
            print("seats progress", i + 1, "/", len(daily))
        time.sleep(0.15)

    if seat_rows:
        seat_df = pd.DataFrame(seat_rows)
        common.insert_db(seat_df, "stock_lhb_seat_detail", False, "`date`,`code`,`side`,`rank_no`")
        print("seat rows:", len(seat_df))
    else:
        print("no seat rows")


def main():
    if len(sys.argv) == 1:
        stat_all(datetime.datetime.now())
    else:
        y, m, d = sys.argv[1].split("-")
        stat_all(datetime.datetime(int(y), int(m), int(d)))


if __name__ == "__main__":
    main()
