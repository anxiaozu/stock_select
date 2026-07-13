#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

# 每日任务健康监控 + 告警。
# 只读统计当日各产出表行数，做异常判定，写日志并（可选）推送 webhook 告警。
# 严重异常时以非 0 退出码结束，便于 cron/supervisor 感知。
#
# 用法：
#   python3 jobs/monitor_daily.py 20260710
#   python3 jobs/monitor_daily.py 2026-07-10
#   python3 jobs/monitor_daily.py            # 默认当天
#
# 说明：对数据库只做只读计数（select_count），不做任何写入/删除。

import os
import sys
import json
import datetime
import urllib.request

import libs.common as common


# ------------------------- 阈值配置（可按需调整） -------------------------
# daily 行数相对当日快照股票数的允许偏差比例，超过则告警（非严重）。
DAILY_DEVIATION_WARN = 0.05
# lite_buy / lite_sell 相对全市场（快照）占比上限，超过视为“过多”告警（非严重）。
LITE_MAX_RATIO_WARN = 0.60

LHB_DETAIL_TABLE = "stock_lhb_detail_daily"


def _normalize_date(arg):
    """把 20260710 或 2026-07-10 归一化为 (datetime_int='20260710', datetime_str='2026-07-10')。"""
    s = str(arg).strip().replace("-", "")
    dt = datetime.datetime.strptime(s, "%Y%m%d")
    return dt.strftime("%Y%m%d"), dt.strftime("%Y-%m-%d")


def _backend_logs_dir():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
    path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    return path


def _log_dir():
    """生产(Linux)优先 /data/logs；Windows 本地一律用 backend/logs。

    注意：Windows 上 `/data/logs` 会落到「当前盘符:\\data\\logs」（如 E:\\data\\logs），
    不能当作 Linux 生产路径。
    """
    if sys.platform.startswith("win"):
        return _backend_logs_dir()
    prod_dir = "/data/logs"
    try:
        os.makedirs(prod_dir, exist_ok=True)
        if os.path.isdir(prod_dir) and os.access(prod_dir, os.W_OK):
            return prod_dir
    except Exception:
        pass
    return _backend_logs_dir()


def read_spot_source(datetime_int):
    """读取当日 spot 数据源状态文件，返回如 source=sina；不存在则返回 None。

    兼容：先查当前 log_dir，再查 backend/logs，再查历史误写的 <drive>:\\data\\logs。
    """
    name = "spot_source.%s.txt" % datetime_int
    candidates = [_log_dir(), _backend_logs_dir()]
    # 兼容早期 Windows 误写到当前盘符根下的 /data/logs
    if sys.platform.startswith("win"):
        drive = os.path.splitdrive(os.getcwd())[0] or "C:"
        candidates.append(os.path.join(drive + os.sep, "data", "logs"))
    seen = set()
    first_path = None
    for d in candidates:
        path = os.path.join(d, name)
        if first_path is None:
            first_path = path
        if path in seen:
            continue
        seen.add(path)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read().strip()
            return content or None, path
        except Exception as e:
            print("[monitor_daily] 读取 spot_source 失败：", str(e)[:200])
            return None, path
    return None, first_path


def send_alert(msg):
    """有 STOCK_ALERT_WEBHOOK 则 POST {"text":...}；无则打印 ALERT（不因缺失报错）。"""
    webhook = os.environ.get("STOCK_ALERT_WEBHOOK")
    if not webhook:
        print("ALERT")
        print(msg)
        return False
    try:
        payload = json.dumps({"text": msg}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("[alert] 已推送告警，HTTP", resp.status)
        return True
    except Exception as e:
        # 告警失败不应影响监控本身的退出语义，仅记录。
        print("[alert] 推送失败（忽略）：", str(e)[:200])
        print("ALERT")
        print(msg)
        return False


def _count(sql, params):
    try:
        return common.select_count(sql, params=params)
    except Exception as e:
        print("[count] 查询失败：", str(e)[:200])
        return -1


def _table_exists(table_name):
    """检查当前库是否存在指定表。"""
    try:
        n = common.select_count(
            "SELECT COUNT(1) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            params=[table_name])
        return n > 0
    except Exception as e:
        print("[monitor_daily] 检查表存在失败：", str(e)[:200])
        return False


def monitor(datetime_int, datetime_str):
    """对指定日期做只读统计与异常判定，返回 (摘要文本, 是否严重异常, 是否需告警)。"""
    # spot：当日总行数（与健康门禁一致，0 则严重）
    spot = _count(
        "SELECT count(1) FROM stock_zh_a_spot_em WHERE `date` = %s",
        [datetime_int])
    # 有效快照（用于偏差/占比参考）
    snapshot = _count(
        "SELECT count(1) FROM stock_zh_a_spot_em "
        "WHERE `date` = %s AND `open` > 0 AND `volume` > 0",
        [datetime_int])
    ind = _count(
        "SELECT count(1) FROM guess_indicators_daily WHERE `date` = %s",
        [datetime_int])
    buy = _count(
        "SELECT count(1) FROM guess_indicators_lite_buy_daily WHERE `date` = %s",
        [datetime_int])
    sell = _count(
        "SELECT count(1) FROM guess_indicators_lite_sell_daily WHERE `date` = %s",
        [datetime_int])

    lhb_exists = _table_exists(LHB_DETAIL_TABLE)
    lhb = -1
    if lhb_exists:
        lhb = _count(
            "SELECT count(1) FROM `%s` WHERE `date` = %%s" % LHB_DETAIL_TABLE,
            [datetime_int])

    spot_source, spot_source_path = read_spot_source(datetime_int)

    warnings = []
    criticals = []

    # 门禁：spot / buy / sell 为 0 → 严重（exit non-zero）。
    if spot <= 0:
        criticals.append("stock_zh_a_spot_em 当日行数为 0，数据源可能未落地。")
    if buy <= 0:
        criticals.append("guess_indicators_lite_buy_daily 行数为 0，买入推荐任务可能失败。")
    if sell <= 0:
        criticals.append("guess_indicators_lite_sell_daily 行数为 0，卖出提示任务可能失败。")

    # ind 为 0 也视为严重（指标链路断裂）。
    if ind <= 0:
        criticals.append("guess_indicators_daily 行数为 0，指标计算任务可能失败。")

    # daily 应接近当日快照股票数；偏差过大告警。
    if snapshot > 0 and ind > 0:
        deviation = abs(ind - snapshot) / float(snapshot)
        if deviation > DAILY_DEVIATION_WARN:
            warnings.append(
                "guess_indicators_daily(%d) 与当日有效快照(%d) 偏差 %.1f%% 超过阈值 %.1f%%。"
                % (ind, snapshot, deviation * 100, DAILY_DEVIATION_WARN * 100))

    # lite_buy / lite_sell 不应过多（超过全市场占比上限）。
    if snapshot > 0 and buy > 0:
        buy_ratio = buy / float(snapshot)
        if buy_ratio > LITE_MAX_RATIO_WARN:
            warnings.append(
                "lite_buy(%d) 占全市场 %.1f%% 超过阈值 %.0f%%，推荐可能过多。"
                % (buy, buy_ratio * 100, LITE_MAX_RATIO_WARN * 100))
    if snapshot > 0 and sell > 0:
        sell_ratio = sell / float(snapshot)
        if sell_ratio > LITE_MAX_RATIO_WARN:
            warnings.append(
                "lite_sell(%d) 占全市场 %.1f%% 超过阈值 %.0f%%，提示可能过多。"
                % (sell, sell_ratio * 100, LITE_MAX_RATIO_WARN * 100))

    if lhb_exists and lhb == 0:
        warnings.append("%s 当日行数为 0（非门禁，仅提示）。" % LHB_DETAIL_TABLE)

    if not spot_source:
        warnings.append("未找到 spot_source 文件：%s" % spot_source_path)

    status = "CRITICAL" if criticals else ("WARN" if warnings else "OK")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("=" * 60)
    lines.append("[monitor_daily] %s  date=%s  status=%s" % (now, datetime_str, status))
    if spot_source:
        lines.append("  spot_source                         : %s" % spot_source)
    else:
        lines.append("  spot_source                         : (missing) %s" % spot_source_path)
    lines.append("  stock_zh_a_spot_em (spot)            : %d" % spot)
    lines.append("  stock_zh_a_spot_em (open>0,volume>0) : %d" % snapshot)
    lines.append("  guess_indicators_daily (ind)         : %d" % ind)
    lines.append("  guess_indicators_lite_buy_daily      : %d" % buy)
    lines.append("  guess_indicators_lite_sell_daily     : %d" % sell)
    if lhb_exists:
        lines.append("  %s         : %d" % (LHB_DETAIL_TABLE.ljust(32), lhb))
    else:
        lines.append("  %s         : (table not found, skip)" % LHB_DETAIL_TABLE.ljust(32))
    if criticals:
        lines.append("  -- CRITICAL --")
        for c in criticals:
            lines.append("    * " + c)
    if warnings:
        lines.append("  -- WARN --")
        for w in warnings:
            lines.append("    * " + w)
    if status == "OK":
        lines.append("  所有指标正常。")
    lines.append("=" * 60)

    summary = "\n".join(lines)
    return summary, bool(criticals), (bool(criticals) or bool(warnings))


def main():
    arg = sys.argv[1] if len(sys.argv) >= 2 else datetime.datetime.now().strftime("%Y%m%d")
    try:
        datetime_int, datetime_str = _normalize_date(arg)
    except Exception:
        print("日期参数无效：%r（应为 YYYYMMDD 或 YYYY-MM-DD）" % arg)
        sys.exit(2)

    summary, is_critical, has_alert = monitor(datetime_int, datetime_str)

    # 打印摘要。
    print(summary)

    # 写日志文件。
    try:
        log_path = os.path.join(_log_dir(), "monitor.%s.log" % datetime_str)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(summary + "\n")
        print("[monitor_daily] 日志已写入：", log_path)
    except Exception as e:
        print("[monitor_daily] 日志写入失败（忽略）：", str(e)[:200])

    # 有异常时告警（严重与警告都推送，严重级外加退出码）。
    if has_alert:
        send_alert(summary)

    if is_critical:
        sys.exit(1)


if __name__ == "__main__":
    main()
