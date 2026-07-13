#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""用腾讯行情接口回填基本面字段（东财快照不可用时）。

补齐: volume_ratio / turnover_rate / pe_ratio / pb_ratio /
      market_cap / circulating_market_cap
同时更新 stock_zh_a_spot_em 与当日的 guess_indicators_* 表。

腾讯接口: https://qt.gtimg.cn/q=sh600519,sz000001
字段: 38换手率 39市盈率 44流通市值(亿) 45总市值(亿) 46市净率 49量比(常见)
"""
import sys
import time
import datetime

import pandas as pd
import requests
from sqlalchemy import text

import libs.common as common

BATCH = 80  # 腾讯单次批量上限较宽松，80 较稳


def _f(parts, idx, default=0.0):
    try:
        v = parts[idx].strip()
        if v in ("", "-", "--"):
            return default
        return float(v)
    except Exception:
        return default


def fetch_tencent_batch(codes):
    """codes: ['sh600519', ...] -> {code: dict}"""
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    with common.direct_network():
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    text_body = r.content.decode("gbk", errors="replace")
    out = {}
    for chunk in text_body.split(";"):
        chunk = chunk.strip()
        if '="' not in chunk:
            continue
        body = chunk.split('="', 1)[1].rstrip('"').rstrip(";")
        parts = body.split("~")
        if len(parts) < 50:
            continue
        raw_code = parts[2].strip()
        # 还原带前缀的 code
        sym = None
        for c in codes:
            if c.endswith(raw_code):
                sym = c
                break
        if not sym:
            # 兜底按数字补前缀
            prefix = common.gp_type_szsh(raw_code) or ""
            sym = prefix + raw_code
        circ_yi = _f(parts, 44)
        total_yi = _f(parts, 45)
        out[sym] = {
            "turnover_rate": _f(parts, 38),
            "pe_ratio": _f(parts, 39),
            "circulating_market_cap": round(circ_yi * 1e8, 2),
            "market_cap": round(total_yi * 1e8, 2),
            "pb_ratio": _f(parts, 46),
            # 不同版本量比落在 47 或 49；优先非零。
            "volume_ratio": _f(parts, 49) or _f(parts, 47),
        }
    return out


def enrich(date_int):
    print("enrich date:", date_int)
    codes = pd.read_sql(
        text("SELECT code FROM stock_zh_a_spot_em WHERE `date`=:d"),
        common.engine(), params={"d": date_int})["code"].astype(str).tolist()
    print("codes:", len(codes))
    if not codes:
        return

    merged = {}
    for i in range(0, len(codes), BATCH):
        batch = codes[i:i + BATCH]
        try:
            part = fetch_tencent_batch(batch)
            merged.update(part)
            print("fetched %d/%d (got %d)" % (min(i + BATCH, len(codes)), len(codes), len(merged)))
        except Exception as e:
            print("batch fail", i, e)
        time.sleep(0.2)

    if not merged:
        print("no tencent data")
        print("enrich field success rate: quotes=0/%d (0.0%%)" % len(codes))
        return

    # 补全字段成功率：相对当日 spot 代码总数，非零视为成功。
    enrich_fields = [
        "volume_ratio", "turnover_rate", "pe_ratio", "pb_ratio",
        "market_cap", "circulating_market_cap",
    ]
    total = len(codes)
    quote_rate = 100.0 * len(merged) / total if total else 0.0
    field_stats = []
    for key in enrich_fields:
        ok = sum(1 for v in merged.values() if float(v.get(key) or 0) != 0.0)
        rate = 100.0 * ok / total if total else 0.0
        field_stats.append((key, ok, rate))
        print("enrich field success: %s = %d/%d (%.1f%%)" % (key, ok, total, rate))
    print("enrich quote fetch: %d/%d (%.1f%%)" % (len(merged), total, quote_rate))

    tables = [
        "stock_zh_a_spot_em",
        "guess_indicators_daily",
        "guess_indicators_lite_buy_daily",
        "guess_indicators_lite_sell_daily",
    ]
    import MySQLdb
    db = MySQLdb.connect(
        host=common.MYSQL_HOST, port=int(common.MYSQL_PORT),
        user=common.MYSQL_USER, passwd=common.MYSQL_PWD,
        db=common.MYSQL_DB, charset="utf8mb4")
    cur = db.cursor()
    updated = 0
    for code, v in merged.items():
        params = (
            v["volume_ratio"], v["turnover_rate"], v["pe_ratio"], v["pb_ratio"],
            v["market_cap"], v["circulating_market_cap"], date_int, code,
        )
        for t in tables:
            try:
                cur.execute(
                    "UPDATE `%s` SET volume_ratio=%%s, turnover_rate=%%s, pe_ratio=%%s, "
                    "pb_ratio=%%s, market_cap=%%s, circulating_market_cap=%%s "
                    "WHERE `date`=%%s AND `code`=%%s" % t,
                    params)
                updated += cur.rowcount
            except Exception:
                pass
    db.commit()
    cur.close()
    db.close()
    avg_rate = (sum(r for _, _, r in field_stats) / len(field_stats)) if field_stats else 0.0
    print("tencent enrich done: quotes=%d/%d (%.1f%%) sql_rows_touched~=%d avg_field_success=%.1f%%"
          % (len(merged), total, quote_rate, updated, avg_rate))


def main():
    if len(sys.argv) >= 2:
        date_int = sys.argv[1].replace("-", "")
    else:
        date_int = datetime.datetime.now().strftime("%Y%m%d")
    enrich(date_int)


if __name__ == "__main__":
    main()
