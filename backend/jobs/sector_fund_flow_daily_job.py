#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

"""
板块资金流每日快照（同花顺-数据中心-资金流向）。
行业资金流: http://data.10jqka.com.cn/funds/hyzjl/
概念资金流: http://data.10jqka.com.cn/funds/gnzjl/
akshare 自带的 stock_fund_flow_industry 列名映射已过期(页面新增了流入/流出列)，
这里直接按页面表格结构解析，字段更全且不受 akshare 版本影响。
写入 stock_fund_flow_industry / stock_fund_flow_concept 两张表，主键(date, name)，幂等可重跑。
"""

import datetime
import sys
import time
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

sys.path.append('/data/stock')
import libs.common as common


def _ths_headers():
    import py_mini_racer
    from akshare.datasets import get_ths_js
    with open(get_ths_js("ths.js"), encoding="utf-8") as f:
        js_content = f.read()
    js = py_mini_racer.MiniRacer()
    js.eval(js_content)
    return {
        "hexin-v": js.call("v"),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "http://data.10jqka.com.cn/funds/hyzjl/",
    }


def _fetch_page(kind, page):
    # kind: hyzjl=行业, gnzjl=概念
    url = "http://data.10jqka.com.cn/funds/%s/field/tradezdf/order/desc/page/%d/ajax/1/free/1/" % (kind, page)
    with common.direct_network():
        r = requests.get(url, headers=_ths_headers(), timeout=20)
    r.raise_for_status()
    return r.text


def _num(x):
    # "5.59%" / "24.06" / "--" -> float
    s = str(x).replace("%", "").replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def fetch_fund_flow(kind):
    """抓全量分页，返回统一列名的 DataFrame。"""
    first = _fetch_page(kind, 1)
    soup = BeautifulSoup(first, "lxml")
    page_info = soup.find("span", attrs={"class": "page_info"})
    total_pages = int(page_info.text.split("/")[1]) if page_info else 1

    frames = [pd.read_html(StringIO(first))[0]]
    for p in range(2, total_pages + 1):
        time.sleep(0.5)  # 温和限速，避免被同花顺反爬
        frames.append(pd.read_html(StringIO(_fetch_page(kind, p)))[0])
    df = pd.concat(frames, ignore_index=True)

    # 页面列: 序号, 行业/概念, 行业指数, 涨跌幅, 流入资金(亿), 流出资金(亿), 净额(亿), 公司家数, 领涨股, 涨跌幅.1, 当前价(元)
    df.columns = ["rank_no", "name", "index_value", "change_percent",
                  "inflow", "outflow", "net_amount", "company_count",
                  "leader_stock", "leader_change_percent", "leader_price"]
    for col in ["index_value", "change_percent", "inflow", "outflow",
                "net_amount", "leader_change_percent", "leader_price"]:
        df[col] = df[col].apply(_num)
    df["company_count"] = df["company_count"].apply(lambda x: int(_num(x)))
    df["leader_stock"] = df["leader_stock"].astype(str)
    # 按净流入重排名次。
    df = df.sort_values("net_amount", ascending=False).reset_index(drop=True)
    df["rank_no"] = range(1, len(df) + 1)
    return df


def stat_all(date):
    datetime_int = date.strftime("%Y%m%d")
    jobs = [("hyzjl", "stock_fund_flow_industry", u"行业"),
            ("gnzjl", "stock_fund_flow_concept", u"概念")]
    for kind, table, label in jobs:
        try:
            df = fetch_fund_flow(kind)
            if df.empty:
                print("%s fund flow empty, skip" % label)
                continue
            df.insert(0, "date", datetime_int)
            del_sql = " DELETE FROM `%s` WHERE `date`= '%s' " % (table, datetime_int)
            common.insert(del_sql)
            common.insert_db(df, table, False, "`date`,`name`")
            print("%s资金流 done: %s rows, top1: %s 净流入 %.2f 亿" % (
                label, len(df), df.iloc[0]["name"], df.iloc[0]["net_amount"]))
        except Exception as e:
            print("%s fund flow error: %s" % (label, e))


def main():
    if len(sys.argv) == 1:
        stat_all(datetime.datetime.now())
    else:
        tmp_year, tmp_month, tmp_day = sys.argv[1].split("-")
        stat_all(datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day)))


if __name__ == '__main__':
    main()
