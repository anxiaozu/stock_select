#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""Dashboard 扩展：市场情绪、消息、资金流、市场风格、大盘星图、个股风向标。"""

import json
import time
import logging

import akshare as ak

import libs.common as common
import web.base as webBase

# 快讯内存缓存：避免每次刷新页面都联网拉新浪。
_NEWS_CACHE = {"ts": 0.0, "data": []}
_NEWS_TTL_SECONDS = 300

# 同花顺行业汇总缓存（大盘星图用）。
_STAR_CACHE = {"ts": 0.0, "tree": None, "date": None, "source": None}
_STAR_TTL_SECONDS = 300


def _fetch_news():
    now = time.time()
    if now - _NEWS_CACHE["ts"] < _NEWS_TTL_SECONDS and _NEWS_CACHE["data"]:
        return _NEWS_CACHE["data"]
    try:
        df = common.ak_call(ak.stock_info_global_sina)
        items = []
        for _, r in df.head(30).iterrows():
            items.append({"time": str(r["时间"]), "content": str(r["内容"])})
        _NEWS_CACHE["ts"] = now
        _NEWS_CACHE["data"] = items
    except Exception as e:
        logging.warning("fetch news error: %s", str(e)[:120])
    return _NEWS_CACHE["data"]


def _fetch_fund_flow(db, table, limit=8, order="DESC"):
    """取最新一天的板块资金流 Top N。order=DESC 净流入，ASC 净流出。"""
    try:
        rows = db.query("SELECT max(`date`) AS d FROM `%s`" % table)
        latest = rows[0]["d"] if rows else None
        if not latest:
            return []
        direction = "DESC" if str(order).upper() != "ASC" else "ASC"
        data = db.query(
            "SELECT `name`, `change_percent`, `net_amount`, `leader_stock`, `leader_change_percent`,"
            " `company_count`, `inflow`, `outflow`"
            " FROM `%s` WHERE `date` = %%s ORDER BY `net_amount` %s LIMIT %d"
            % (table, direction, int(limit)),
            latest)
        return [{
            "name": r["name"],
            "changePercent": float(r["change_percent"] or 0),
            "netAmount": float(r["net_amount"] or 0),
            "leader": r["leader_stock"],
            "leaderChange": float(r["leader_change_percent"] or 0),
            "companyCount": int(r["company_count"] or 0),
            "inflow": float(r["inflow"] or 0),
            "outflow": float(r["outflow"] or 0),
        } for r in data]
    except Exception as e:
        logging.warning("fund flow error: %s", str(e)[:120])
        return []


def _money_effect(up, down, avg_change, limit_up):
    """赚钱效应：综合涨跌比、平均涨跌、涨停家数。"""
    total = up + down
    up_ratio = (up * 1.0 / total) if total else 0.5
    score = up_ratio * 60.0 + max(min(avg_change, 3.0), -3.0) * 8.0 + min(limit_up, 80) * 0.15
    if score >= 55:
        return "强", score
    if score >= 40:
        return "中", score
    return "弱", score


def _suggested_position(temperature, money_score):
    """建议仓位：市场温度为主，赚钱效应微调，限制在 10%~90%。"""
    raw = temperature * 0.75 + money_score * 0.25
    return int(max(10, min(90, round(raw))))


def _build_market_style(sentiment, industry_flow, industry_outflow):
    up = int(sentiment.get("up") or 0)
    down = int(sentiment.get("down") or 0)
    flat = int(sentiment.get("flat") or 0)
    avg_change = float(sentiment.get("avgChange") or 0)
    limit_up = int(sentiment.get("limitUp") or 0)
    temperature = float(sentiment.get("temperature") or 50)
    effect, money_score = _money_effect(up, down, avg_change, limit_up)
    position = _suggested_position(temperature, money_score)
    # 板块瓷砖：净流入前 8 + 净流出前 4（若有），去重。
    tiles = []
    seen = set()
    for row in (industry_flow or []) + (industry_outflow or []):
        name = row.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        tiles.append(row)
        if len(tiles) >= 12:
            break
    return {
        "suggestedPosition": position,
        "moneyEffect": effect,
        "moneyScore": round(money_score, 1),
        "up": up,
        "down": down,
        "flat": flat,
        "temperature": temperature,
        "avgChange": avg_change,
        "sectorTiles": tiles,
        "hint": "根据市场涨跌与赚钱效应估算，仅供参考",
    }


def _fetch_industry_star_tree():
    """同花顺行业汇总 → 行业级树图（面积=成交额，颜色=涨跌幅）。"""
    now = time.time()
    if now - _STAR_CACHE["ts"] < _STAR_TTL_SECONDS and _STAR_CACHE["tree"]:
        return _STAR_CACHE["tree"], _STAR_CACHE["date"], _STAR_CACHE["source"]
    try:
        df = common.ak_call(ak.stock_board_industry_summary_ths)
        children = []
        for _, r in df.iterrows():
            name = str(r.get("板块") or "").strip()
            if not name:
                continue
            change = float(r.get("涨跌幅") or 0)
            amount = float(r.get("总成交额") or 0)
            # 成交额单位多为亿元；过小则用上涨+下跌家数兜底，保证块可见。
            value = amount if amount > 0 else float(
                (r.get("上涨家数") or 0) + (r.get("下跌家数") or 0) or 1)
            up_n = int(r.get("上涨家数") or 0)
            down_n = int(r.get("下跌家数") or 0)
            leader = str(r.get("领涨股") or "")
            children.append({
                "name": name,
                "value": round(value, 2),
                "changePercent": round(change, 2),
                "up": up_n,
                "down": down_n,
                "leader": leader,
            })
        tree = {"name": "A股行业", "children": children}
        _STAR_CACHE["ts"] = now
        _STAR_CACHE["tree"] = tree
        _STAR_CACHE["date"] = time.strftime("%Y%m%d")
        _STAR_CACHE["source"] = "ths_industry_summary"
        return tree, _STAR_CACHE["date"], _STAR_CACHE["source"]
    except Exception as e:
        logging.warning("star map ths error: %s", str(e)[:160])
        return None, None, None


def _star_tree_from_db(db):
    """THS 不可用时，用库内行业资金流拼行业树图。"""
    try:
        rows = db.query("SELECT max(`date`) AS d FROM stock_fund_flow_industry")
        latest = rows[0]["d"] if rows else None
        if not latest:
            return None, None, None
        data = db.query(
            "SELECT `name`, `change_percent`, `net_amount`, `company_count`, `inflow`, `outflow`, `leader_stock`"
            " FROM stock_fund_flow_industry WHERE `date` = %s", latest)
        children = []
        for r in data:
            name = r["name"]
            # 用流入+流出近似活跃度，没有则用公司家数。
            value = float(r["inflow"] or 0) + float(r["outflow"] or 0)
            if value <= 0:
                value = float(r["company_count"] or 1)
            children.append({
                "name": name,
                "value": round(value, 2),
                "changePercent": round(float(r["change_percent"] or 0), 2),
                "up": 0,
                "down": 0,
                "leader": r["leader_stock"] or "",
            })
        return {"name": "A股行业", "children": children}, str(latest), "db_fund_flow_industry"
    except Exception as e:
        logging.warning("star map db fallback error: %s", str(e)[:120])
        return None, None, None


def _stock_cap_star_tree(db, limit=180):
    """个股市值热力：按流通市值取 TopN，作扁平树图（无行业分组时的补充视图）。"""
    try:
        rows = db.query("SELECT max(`date`) AS d FROM stock_zh_a_spot_em")
        latest = rows[0]["d"] if rows else None
        if not latest:
            return None, None
        sql = (
            "SELECT `code`, `name`, `change_percent`, `circulating_market_cap`"
            " FROM stock_zh_a_spot_em"
            " WHERE `date` = %%s AND `open` > 0 AND `volume` > 0"
            "   AND `circulating_market_cap` > 0"
            " ORDER BY `circulating_market_cap` DESC LIMIT %d"
        ) % int(limit)
        data = db.query(sql, latest)
        children = []
        for r in data:
            cmc = float(r["circulating_market_cap"] or 0)
            children.append({
                "name": r["name"] or r["code"],
                "code": r["code"],
                "value": round(cmc / 1e8, 2),  # 亿元
                "changePercent": round(float(r["change_percent"] or 0), 2),
            })
        return {"name": "A股个股(流通市值Top)", "children": children}, str(latest)
    except Exception as e:
        logging.warning("stock cap star error: %s", str(e)[:120])
        return None, None


def _stock_vane(db, n=10):
    """个股风向标：涨幅/跌幅前列。"""
    try:
        rows = db.query("SELECT max(`date`) AS d FROM stock_zh_a_spot_em")
        latest = rows[0]["d"] if rows else None
        if not latest:
            return {"date": None, "gainers": [], "losers": []}
        g_sql = (
            "SELECT `code`, `name`, `last_price`, `change_percent`, `turnover_rate`"
            " FROM stock_zh_a_spot_em"
            " WHERE `date` = %%s AND `open` > 0 AND `volume` > 0"
            "   AND locate('ST', `name`) = 0"
            " ORDER BY `change_percent` DESC LIMIT %d"
        ) % int(n)
        l_sql = (
            "SELECT `code`, `name`, `last_price`, `change_percent`, `turnover_rate`"
            " FROM stock_zh_a_spot_em"
            " WHERE `date` = %%s AND `open` > 0 AND `volume` > 0"
            "   AND locate('ST', `name`) = 0"
            " ORDER BY `change_percent` ASC LIMIT %d"
        ) % int(n)
        gainers = db.query(g_sql, latest)
        losers = db.query(l_sql, latest)

        def _pack(rs):
            return [{
                "code": r["code"],
                "name": r["name"],
                "lastPrice": float(r["last_price"] or 0),
                "changePercent": float(r["change_percent"] or 0),
                "turnoverRate": float(r["turnover_rate"] or 0),
            } for r in rs]

        return {
            "date": str(latest),
            "gainers": _pack(gainers),
            "losers": _pack(losers),
        }
    except Exception as e:
        logging.warning("stock vane error: %s", str(e)[:120])
        return {"date": None, "gainers": [], "losers": []}


class DashboardExtraHandler(webBase.BaseHandler):
    def get(self):
        self.set_header('Content-Type', 'application/json;charset=UTF-8')

        sentiment = {}
        try:
            rows = self.db.query(
                "SELECT max(`date`) AS d FROM stock_zh_a_spot_em")
            latest_date = rows[0]["d"] if rows else None
            if latest_date:
                stat = self.db.query(
                    " SELECT count(1) AS total, "
                    "  sum(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END) AS up_count, "
                    "  sum(CASE WHEN change_percent < 0 THEN 1 ELSE 0 END) AS down_count, "
                    "  sum(CASE WHEN change_percent = 0 THEN 1 ELSE 0 END) AS flat_count, "
                    "  sum(CASE WHEN change_percent >= 9.5 THEN 1 ELSE 0 END) AS limit_up, "
                    "  sum(CASE WHEN change_percent <= -9.5 THEN 1 ELSE 0 END) AS limit_down, "
                    "  round(avg(change_percent), 2) AS avg_change, "
                    "  round(sum(turnover) / 1e8, 0) AS total_turnover_yi "
                    " FROM stock_zh_a_spot_em "
                    " WHERE `date` = %s AND `open` > 0 AND `volume` > 0 ", latest_date)[0]
                up = int(stat["up_count"] or 0)
                down = int(stat["down_count"] or 0)
                sentiment = {
                    "date": str(latest_date),
                    "total": int(stat["total"] or 0),
                    "up": up,
                    "down": down,
                    "flat": int(stat["flat_count"] or 0),
                    "limitUp": int(stat["limit_up"] or 0),
                    "limitDown": int(stat["limit_down"] or 0),
                    "avgChange": float(stat["avg_change"] or 0),
                    "totalTurnoverYi": float(stat["total_turnover_yi"] or 0),
                    "temperature": round(up * 100.0 / (up + down), 1) if (up + down) > 0 else 50.0,
                }
        except Exception as e:
            logging.warning("sentiment error: %s", str(e)[:120])

        industry_flow = _fetch_fund_flow(self.db, "stock_fund_flow_industry", limit=8, order="DESC")
        industry_outflow = _fetch_fund_flow(self.db, "stock_fund_flow_industry", limit=6, order="ASC")
        concept_flow = _fetch_fund_flow(self.db, "stock_fund_flow_concept", limit=8, order="DESC")

        market_style = _build_market_style(sentiment, industry_flow, industry_outflow)

        industry_tree, industry_date, industry_source = _fetch_industry_star_tree()
        if not industry_tree:
            industry_tree, industry_date, industry_source = _star_tree_from_db(self.db)
        stock_tree, stock_date = _stock_cap_star_tree(self.db)

        obj = {
            "code": 20000,
            "message": "success",
            "sentiment": sentiment,
            "news": _fetch_news(),
            "industryFlow": industry_flow,
            "conceptFlow": concept_flow,
            "marketStyle": market_style,
            "starMap": {
                "industry": {
                    "date": industry_date,
                    "source": industry_source,
                    "tree": industry_tree,
                    "note": "行业级星图：面积≈成交活跃度，颜色=涨跌幅（东财个股成分暂不可用）",
                },
                "stockCap": {
                    "date": stock_date,
                    "tree": stock_tree,
                    "note": "个股市值热力：流通市值 Top，颜色=涨跌幅",
                },
            },
            "stockVane": _stock_vane(self.db, 10),
        }
        self.write(json.dumps(obj, ensure_ascii=False))
