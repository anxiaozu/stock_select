#!/usr/local/bin/python
# -*- coding: utf-8 -*-

# apk add py-mysqldb or

import platform
import datetime
import time
import sys
import os
import re
import threading
from contextlib import contextmanager
import MySQLdb
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.types import NVARCHAR
from sqlalchemy import inspect
import pandas as pd
import traceback
import akshare as ak

# 使用环境变量获得数据库。兼容开发模式可docker模式。
MYSQL_HOST = os.environ.get('MYSQL_HOST') if (os.environ.get('MYSQL_HOST') != None) else "mysqldb"
MYSQL_USER = os.environ.get('MYSQL_USER') if (os.environ.get('MYSQL_USER') != None) else "root"
MYSQL_PWD = os.environ.get('MYSQL_PWD') if (os.environ.get('MYSQL_PWD') != None) else "mysqldb"
MYSQL_DB = os.environ.get('MYSQL_DB') if (os.environ.get('MYSQL_DB') != None) else "stock_data"
MYSQL_PORT = os.environ.get('MYSQL_PORT') if (os.environ.get('MYSQL_PORT') != None) else "3306"

MYSQL_PWD_ENCODED = quote_plus(MYSQL_PWD)
print("MYSQL_HOST :", MYSQL_HOST, ",MYSQL_USER :", MYSQL_USER, ",MYSQL_DB :", MYSQL_DB)
MYSQL_CONN_URL = "mysql+mysqldb://" + MYSQL_USER + ":" + MYSQL_PWD_ENCODED + "@" + MYSQL_HOST + ":" + MYSQL_PORT + "/" + MYSQL_DB + "?charset=utf8mb4"
print("MYSQL_CONN_URL :", MYSQL_CONN_URL)

__version__ = "2.0.0"
# 每次发布时候更新。

# https://docs.sqlalchemy.org/en/20/errors.html#error-e3q8
# 
def engine():
    engine = create_engine(MYSQL_CONN_URL, pool_size=10, max_overflow=20)
        #encoding='utf8', convert_unicode=True)
    return engine

def engine_to_db(to_db):
    MYSQL_CONN_URL_NEW = "mysql+mysqldb://" + MYSQL_USER + ":" + MYSQL_PWD_ENCODED + "@" + MYSQL_HOST + ":" + MYSQL_PORT + "/" + to_db + "?charset=utf8mb4"
    engine = create_engine(MYSQL_CONN_URL_NEW, pool_size=10, max_overflow=20)
        #encoding='utf8', convert_unicode=True)
    return engine

# 通过数据库链接 engine。
def conn():
    try:
        db = MySQLdb.connect(MYSQL_HOST, MYSQL_USER, MYSQL_PWD, MYSQL_DB, charset="utf8")
        # db.autocommit = True
    except Exception as e:
        print("conn error :", e)
    db.autocommit(on=True)
    return db.cursor()


# 定义通用方法函数，插入数据库表，并创建数据库主键，保证重跑数据的时候索引唯一。
def insert_db(data, table_name, write_index, primary_keys):
    # 插入默认的数据库。
    insert_other_db(MYSQL_DB, data, table_name, write_index, primary_keys)


# 增加一个插入到其他数据库的方法。
def insert_other_db(to_db, data, table_name, write_index, primary_keys):
    # 定义engine
    engine_mysql = engine_to_db(to_db)
    # 使用 http://docs.sqlalchemy.org/en/latest/core/reflection.html
    # 使用检查检查数据库表是否有主键。
    insp = inspect(engine_mysql)
    col_name_list = data.columns.tolist()
    # 如果有索引，把索引增加到varchar上面。
    if write_index:
        # 插入到第一个位置：
        col_name_list.insert(0, data.index.name)
    print(col_name_list)
    data.to_sql(name=table_name, con=engine_mysql, schema=to_db, if_exists='append',
                dtype={col_name: NVARCHAR(length=255) for col_name in col_name_list}, index=write_index)

    # print(insp.get_pk_constraint(table_name))
    # print()
    # print(type(insp))
    # 判断是否存在主键
    if insp.get_pk_constraint(table_name)['constrained_columns'] == []:
        with engine_mysql.connect() as con:
            # 执行数据库插入数据。
            try:
                con.execute('ALTER TABLE `%s` ADD PRIMARY KEY (%s);' % (table_name, primary_keys))
            except  Exception as e:
                print("################## ADD PRIMARY KEY ERROR :", e)




# 插入数据。
def insert(sql, params=()):
    with conn() as db:
        print("insert sql:" + sql)
        try:
            db.execute(sql, params)
        except  Exception as e:
            print("error :", e)


# 查询数据
def select(sql, params=()):
    with conn() as db:
        print("select sql:" + sql)
        try:
            db.execute(sql, params)
        except  Exception as e:
            print("error :", e)
        result = db.fetchall()
        return result


# 计算数量
def select_count(sql, params=()):
    with conn() as db:
        print("select sql:" + sql)
        try:
            db.execute(sql, params)
        except  Exception as e:
            print("error :", e)
        result = db.fetchall()
        # 只有一个数组中的第一个数据
        if len(result) == 1:
            return int(result[0][0])
        else:
            return 0


# 通用函数。获得日期参数。
def run_with_args(run_fun):
    tmp_datetime_show = datetime.datetime.now()  # 修改成默认是当日执行 + datetime.timedelta()
    tmp_hour_int = int(tmp_datetime_show.strftime("%H"))
    if tmp_hour_int < 12 :
        # 判断如果是每天 中午 12 点之前运行，跑昨天的数据。
        tmp_datetime_show = (tmp_datetime_show + datetime.timedelta(days=-1))
    tmp_datetime_str = tmp_datetime_show.strftime("%Y-%m-%d %H:%M:%S.%f")
    print("\n######################### hour_int %d " % tmp_hour_int)
    str_db = "MYSQL_HOST :" + MYSQL_HOST + ", MYSQL_USER :" + MYSQL_USER + ", MYSQL_DB :" + MYSQL_DB
    print("\n######################### " + str_db + "  ######################### ")
    print("\n######################### begin run %s %s  #########################" % (run_fun, tmp_datetime_str))
    start = time.time()
    # 要支持数据重跑机制，将日期传入。循环次数
    if len(sys.argv) == 3:
        # python xxx.py 2017-07-01 10
        tmp_year, tmp_month, tmp_day = sys.argv[1].split("-")
        loop = int(sys.argv[2])
        tmp_datetime = datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day))
        for i in range(0, loop):
            # 循环插入多次数据，重复跑历史数据使用。
            # time.sleep(5)
            tmp_datetime_new = tmp_datetime + datetime.timedelta(days=i)
            try:
                run_fun(tmp_datetime_new)
            except Exception as e:
                print("error :", e)
                traceback.print_exc()
    elif len(sys.argv) == 2:
        # python xxx.py 2017-07-01
        tmp_year, tmp_month, tmp_day = sys.argv[1].split("-")
        tmp_datetime = datetime.datetime(int(tmp_year), int(tmp_month), int(tmp_day))
        try:
            run_fun(tmp_datetime)
        except Exception as e:
            print("error :", e)
            traceback.print_exc()
    else:
        # tmp_datetime = datetime.datetime.now() + datetime.timedelta(days=-1)
        try:
            run_fun(tmp_datetime_show)  # 使用当前时间
        except Exception as e:
            print("error :", e)
            traceback.print_exc()
    print("######################### finish %s , use time: %s #########################" % (
        tmp_datetime_str, time.time() - start))


# 设置基础目录，每次加载使用。
# 增量缓存目录：每只股票一个文件，永久复用
bash_stock_tmp = "/data/cache/hist_data_cache/"
if not os.path.exists(bash_stock_tmp):
    os.makedirs(bash_stock_tmp)  # 创建多个文件夹结构。
    print("######################### init tmp dir #########################")


# 历史缓存日志开关：默认关闭逐只刷屏，只在排障时置 True。
HIST_CACHE_VERBOSE = False

# 历史回看天数（可配置）。默认 400 自然日 ≈ 270 个交易日，足够支撑 MA120/MA250。
# 说明：这是“默认回看窗口”，各 job 目前仍显式传入自己的 date_start/date_end，
# 因此调大此值不会改变既有每日增量行为，也不会触发全市场重新联网拉取。
# 仅在调用方选择使用 HIST_DAYS（或调用 backfill_hist_cache）时生效。
HIST_DAYS = 400

# ak.stock_zh_a_daily 网络调用的默认重试次数与退避基数（秒）。
HIST_FETCH_RETRIES = 3
HIST_FETCH_BACKOFF = 1.5


def _hist_log(*args):
    if HIST_CACHE_VERBOSE:
        print(*args)


# 抓取行情时跳过 HTTP/系统代理，直连国内数据源（新浪/东财等）。
_PROXY_ENV_KEYS = (
    'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
    'ALL_PROXY', 'all_proxy',
)
_direct_net_lock = threading.Lock()
_direct_net_depth = 0
_saved_proxy_env = None
_orig_requests_get = None
_orig_session_request = None
_NO_PROXY_DICT = {'http': None, 'https': None}

# 本机网络下多数 N.push2.eastmoney.com 会 RemoteDisconnected，
# 但 push2delay.eastmoney.com 可通。akshare 写死了 82/17/79 等节点，
# 在直连抓数时把这些主机改写到可用节点（数据可能略有延迟，日更场景足够）。
_EM_PUSH2_HOST_RE = re.compile(
    r"^https?://(?:\d+\.)?push2\.eastmoney\.com(?=/|$)", re.IGNORECASE)
_EM_PUSH2_FALLBACK = "https://push2delay.eastmoney.com"


def _rewrite_eastmoney_push2_url(url):
    if not url or not isinstance(url, str):
        return url
    if "push2delay.eastmoney.com" in url.lower():
        return url
    return _EM_PUSH2_HOST_RE.sub(_EM_PUSH2_FALLBACK, url)


_ipv4_forced = False


def _force_ipv4():
    """让 urllib3 只用 IPv4 建连。

    东财等站点的 IPv6 线路在部分网络下会直接断开连接(RemoteDisconnected)，
    而 IPv4 直连正常，故抓数时强制 IPv4。进程级一次性生效，可幂等调用。
    """
    global _ipv4_forced
    if _ipv4_forced:
        return
    try:
        import socket
        from urllib3.util import connection as _u3conn
        _u3conn.allowed_gai_family = lambda: socket.AF_INET
        _ipv4_forced = True
    except Exception as e:
        print("force ipv4 skip:", e)


@contextmanager
def direct_network():
    """抓取 A 股行情时强制不走代理，用本机网络(IPv4)直连。

    - 清空 HTTP_PROXY / ALL_PROXY 等环境变量；
    - 对 requests 注入 proxies=None 且 trust_env=False，绕过 Windows 注册表代理；
    - 强制 IPv4（东财的 IPv6 线路在本机网络下不通）；
    - 指标计算、MySQL、缓存读写等本地操作不需要包在此 context 内。
    """
    global _direct_net_depth, _saved_proxy_env
    global _orig_requests_get, _orig_session_request
    import requests

    _force_ipv4()

    with _direct_net_lock:
        _direct_net_depth += 1
        if _direct_net_depth == 1:
            _saved_proxy_env = {k: os.environ.pop(k, None) for k in _PROXY_ENV_KEYS}
            os.environ['NO_PROXY'] = '*'
            os.environ['no_proxy'] = '*'

            if _orig_requests_get is None:
                _orig_requests_get = requests.get
            if _orig_session_request is None:
                _orig_session_request = requests.Session.request

            def _patched_get(url, **kwargs):
                url = _rewrite_eastmoney_push2_url(url)
                kwargs.setdefault('proxies', _NO_PROXY_DICT)
                return _orig_requests_get(url, **kwargs)

            def _patched_request(self, method, url, **kwargs):
                url = _rewrite_eastmoney_push2_url(url)
                kwargs.setdefault('proxies', _NO_PROXY_DICT)
                old_trust = self.trust_env
                self.trust_env = False
                try:
                    return _orig_session_request(self, method, url, **kwargs)
                finally:
                    self.trust_env = old_trust

            requests.get = _patched_get
            requests.Session.request = _patched_request

    try:
        yield
    finally:
        with _direct_net_lock:
            _direct_net_depth -= 1
            if _direct_net_depth == 0:
                import requests
                requests.get = _orig_requests_get
                requests.Session.request = _orig_session_request
                if _saved_proxy_env is not None:
                    for k, v in _saved_proxy_env.items():
                        if v is not None:
                            os.environ[k] = v
                        elif k in os.environ:
                            del os.environ[k]
                    for k in ('NO_PROXY', 'no_proxy'):
                        if k not in _saved_proxy_env:
                            os.environ.pop(k, None)


def ak_call(func, *args, **kwargs):
    """在 direct_network 下调用任意 akshare 接口。"""
    with direct_network():
        return func(*args, **kwargs)


def _ak_stock_daily_with_retry(symbol, start_date, end_date, adjust="",
                               retries=HIST_FETCH_RETRIES, backoff=HIST_FETCH_BACKOFF):
    """给 ak.stock_zh_a_daily 包一层重试 + 递增退避。

    - 成功返回 DataFrame；
    - 全部重试失败时返回 None（不抛异常），避免打断整批处理。
    - 退避间隔递增：backoff * 1, backoff * 2, ...（含轻微 IO 抖动容忍）。
    """
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            with direct_network():
                df = ak.stock_zh_a_daily(symbol=symbol, start_date=start_date,
                                         end_date=end_date, adjust=adjust)
            return df
        except Exception as e:
            last_err = e
            wait = backoff * attempt
            _hist_log("######### ak.stock_zh_a_daily retry #########",
                      symbol, "attempt", attempt, "err", str(e)[:80],
                      "-> sleep", round(wait, 2), "s")
            if attempt < max(1, retries):
                time.sleep(wait)
    print("ak.stock_zh_a_daily failed after %d retries: %s (%s)" % (
        max(1, retries), symbol, str(last_err)[:120]))
    return None


def _cache_file_for(code):
    symbol = code
    if not (code.startswith('sh') or code.startswith('sz') or code.startswith('bj')):
        prefix = gp_type_szsh(code)
        if prefix:
            symbol = prefix + code
    return bash_stock_tmp + "%s.gzip.pickle" % symbol


# 并发预热历史缓存：网络 IO 型，用线程池并发拉取，冷启动/补历史可大幅提速。
# 每只股票各自读写独立缓存文件，互不干扰；失败的股票跳过不影响整体。
# only_missing=True 时只拉“无缓存”的股票（冷启动/新股）；已有缓存的交给
# append_today_bar_to_cache 走零网络的当日追加，避免每日更新时白白联网。
def prefetch_hist_cache(codes, date_start, date_end, workers=16, only_missing=True):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    codes = list(dict.fromkeys([c for c in codes if c]))
    if only_missing:
        codes = [c for c in codes if not os.path.isfile(_cache_file_for(c))]
    total = len(codes)
    if total == 0:
        print("######### prefetch: nothing to fetch (cache warm) #########")
        return 0
    done = 0
    ok = 0

    def _one(c):
        try:
            return get_hist_data_cache(c, date_start, date_end) is not None
        except Exception as e:
            print("prefetch error:", c, str(e)[:60])
            return False

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_one, c): c for c in codes}
        for fut in as_completed(futures):
            done += 1
            if fut.result():
                ok += 1
            if done % 200 == 0 or done == total:
                print("######### prefetch progress #########: %d/%d (ok=%d)" % (done, total, ok))
    return ok


# 增加读取股票缓存方法。支持增量更新。
def get_hist_data_cache(code, date_start, date_end):
    """获取历史数据（支持增量缓存）。
    首次拉取 100 天全量数据存入缓存文件。
    后续每天只拉取新增的天数，追加到缓存。
    缓存按股票代码存储：hist_data_cache/{code}.gzip.pickle
    """
    # 处理代码格式：如果已有前缀就用，没有则加上
    symbol = code
    if not (code.startswith('sh') or code.startswith('sz') or code.startswith('bj')):
        prefix = gp_type_szsh(code)
        if prefix:
            symbol = prefix + code

    cache_file = bash_stock_tmp + "%s.gzip.pickle" % symbol

    # 读取已有缓存
    cached_df = None
    if os.path.isfile(cache_file):
        cached_df = pd.read_pickle(cache_file, compression="gzip")
        # 规范化索引为 Timestamp，避免 datetime.date 与字符串切片比较报错。
        cached_df.index = pd.to_datetime(cached_df.index)
        _hist_log("######### cache loaded #########", symbol, len(cached_df), "rows")

    if cached_df is not None and len(cached_df) > 0:
        # 缓存中最后一天
        last_cached_date = cached_df.index.max()
        last_cached_str = last_cached_date.strftime("%Y-%m-%d") if hasattr(last_cached_date, 'strftime') else str(last_cached_date)[:10]

        # 需要拉取的结束日期
        date_end_dt = datetime.datetime.strptime(date_end, "%Y-%m-%d")
        date_end_str = date_end_dt.strftime("%Y-%m-%d")

        # 如果缓存已经覆盖到目标日期，直接返回需要的范围
        if str(last_cached_date)[:10] >= date_end_str:
            _hist_log("######### cache hit (up to date) #########", symbol)
            return cached_df.loc[date_start:date_end].copy()

        # 增量拉取：从缓存最后一天的下一天开始
        fetch_start = (last_cached_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        _hist_log("######### incremental fetch #########", symbol, fetch_start, "->", date_end_str)

        new_data = _ak_stock_daily_with_retry(symbol,
            fetch_start.replace("-", ""), date_end_str.replace("-", ""), adjust="")

        # 网络增量拉取失败（返回 None）：不抛异常、不清空缓存，直接返回已有缓存范围，
        # 保证整批处理不被单只股票的网络问题打断。
        if new_data is None:
            _hist_log("######### incremental fetch failed, serve cache #########", symbol)
            return cached_df.loc[date_start:date_end].copy()

        if not new_data.empty and len(new_data) > 0:
            new_data.columns = ['date', 'open', 'high', 'close', 'low', 'volume', 'amount', 'outstanding_share', 'turnover']
            # 保留 turnover(换手率,小数)、outstanding_share(流通股本)，用于自算换手率/流通市值。
            new_data = new_data[['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'turnover', 'outstanding_share']]
            new_data.set_index('date', inplace=True)
            new_data.index = pd.to_datetime(new_data.index)

            # 合并到缓存
            cached_df = pd.concat([cached_df, new_data])
            cached_df = cached_df[~cached_df.index.duplicated(keep='last')]
            cached_df = cached_df.sort_index()
            cached_df.to_pickle(cache_file, compression="gzip")
            _hist_log("######### cache updated #########", symbol, len(cached_df), "total rows")

        return cached_df.loc[date_start:date_end].copy() if cached_df is not None else None

    else:
        # 首次拉取：全量 100 天
        _hist_log("######### first fetch #########", symbol, date_start, date_end)

        stock = _ak_stock_daily_with_retry(symbol,
            date_start.replace("-", ""), date_end.replace("-", ""), adjust="")

        if stock is None or stock.empty:
            return None

        stock.columns = ['date', 'open', 'high', 'close', 'low', 'volume', 'amount', 'outstanding_share', 'turnover']
        # 保留 turnover(换手率,小数)、outstanding_share(流通股本)，用于自算换手率/流通市值。
        stock = stock[['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'turnover', 'outstanding_share']]
        stock.set_index('date', inplace=True)
        stock.index = pd.to_datetime(stock.index)

        stock.to_pickle(cache_file, compression="gzip")
        _hist_log("######### cache saved #########", symbol, len(stock), "rows")
        return stock


# 用当日已抓取的 OHLCV 直接写入该股票历史缓存，避免每日更新时逐只再走网络增量拉取。
# 仅当缓存文件已存在时追加（存在=已有历史）；不存在则跳过，交给首次全量拉取。
# 这样每日指标计算可命中缓存、零网络调用，大幅缩短耗时。
def append_today_bar_to_cache(code, date_str, open_price, close_price, high_price, low_price, volume, amount=0):
    symbol = code
    if not (code.startswith('sh') or code.startswith('sz') or code.startswith('bj')):
        prefix = gp_type_szsh(code)
        if prefix:
            symbol = prefix + code

    cache_file = bash_stock_tmp + "%s.gzip.pickle" % symbol
    if not os.path.isfile(cache_file):
        return False
    try:
        cached_df = pd.read_pickle(cache_file, compression="gzip")
        cached_df.index = pd.to_datetime(cached_df.index)
        ts = pd.to_datetime(str(date_str).replace("-", ""), format="%Y%m%d")
        row = pd.DataFrame({
            "open": [float(open_price)], "close": [float(close_price)],
            "high": [float(high_price)], "low": [float(low_price)],
            "volume": [float(volume)], "amount": [float(amount)],
        }, index=[ts])
        cached_df = pd.concat([cached_df, row])
        cached_df = cached_df[~cached_df.index.duplicated(keep="last")]
        cached_df = cached_df.sort_index()
        cached_df.to_pickle(cache_file, compression="gzip")
        return True
    except Exception as e:
        print("append_today_bar_to_cache error:", code, e)
        return False


# 按需历史回填：把“已有缓存”向更早方向补齐到指定天数。
# 用途：将来支撑 MA120 / MA250 与回测，需要比每日窗口更长的历史。
# 设计要点（避免误伤每日流程）：
#   - 仅处理“已存在缓存文件”的股票；无缓存的不在这里冷启动（交给 prefetch/首次拉取）。
#   - 只在缓存的最早日期仍晚于目标起始日时才联网补齐，已够深的直接跳过（零网络）。
#   - 只向“更早”方向补，不动缓存里已有的较新数据；合并后按索引去重、排序。
#   - 该函数只在被显式调用时执行，不会被任何每日 job 自动触发。
def backfill_hist_cache(codes, days=None, workers=16):
    """把已有缓存回填到 `days` 天深度。

    参数:
        codes:   股票代码列表（同 get_hist_data_cache 接受的格式）。
        days:    目标回看自然日数，默认使用模块级 HIST_DAYS。
        workers: 并发线程数（网络 IO 型）。
    返回:
        实际发生补齐（有新数据写入）的股票数量。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if days is None:
        days = HIST_DAYS
    codes = list(dict.fromkeys([c for c in codes if c]))
    target_start_dt = datetime.datetime.now() - datetime.timedelta(days=days)
    target_start_str = target_start_dt.strftime("%Y-%m-%d")

    # 只处理已有缓存文件的股票。
    codes = [c for c in codes if os.path.isfile(_cache_file_for(c))]
    total = len(codes)
    if total == 0:
        print("######### backfill: no existing cache to extend #########")
        return 0

    def _one(code):
        symbol = code
        if not (code.startswith('sh') or code.startswith('sz') or code.startswith('bj')):
            prefix = gp_type_szsh(code)
            if prefix:
                symbol = prefix + code
        cache_file = bash_stock_tmp + "%s.gzip.pickle" % symbol
        try:
            cached_df = pd.read_pickle(cache_file, compression="gzip")
            cached_df.index = pd.to_datetime(cached_df.index)
            if len(cached_df) == 0:
                return False
            earliest = cached_df.index.min()
            # 已经够深，无需联网。
            if str(earliest)[:10] <= target_start_str:
                return False
            # 补齐区间：目标起始 -> 最早缓存日的前一天。
            fetch_end = (earliest - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            old_data = _ak_stock_daily_with_retry(symbol,
                target_start_str.replace("-", ""), fetch_end.replace("-", ""), adjust="")
            if old_data is None or old_data.empty or len(old_data) == 0:
                return False
            old_data.columns = ['date', 'open', 'high', 'close', 'low', 'volume',
                                'amount', 'outstanding_share', 'turnover']
            old_data = old_data[['date', 'open', 'close', 'high', 'low', 'volume', 'amount']]
            old_data.set_index('date', inplace=True)
            old_data.index = pd.to_datetime(old_data.index)
            merged = pd.concat([old_data, cached_df])
            merged = merged[~merged.index.duplicated(keep='last')]
            merged = merged.sort_index()
            merged.to_pickle(cache_file, compression="gzip")
            _hist_log("######### backfill done #########", symbol,
                      "earliest", str(earliest)[:10], "->", target_start_str,
                      "total", len(merged), "rows")
            return True
        except Exception as e:
            print("backfill error:", code, str(e)[:80])
            return False

    done = 0
    filled = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_one, c): c for c in codes}
        for fut in as_completed(futures):
            done += 1
            if fut.result():
                filled += 1
            if done % 200 == 0 or done == total:
                print("######### backfill progress #########: %d/%d (filled=%d) target>=%s" % (
                    done, total, filled, target_start_str))
    return filled


# 沪市股票包含上证主板和科创板和B股：沪市主板股票代码是60开头、科创板股票代码是688开头、B股代码900开头。
# 深市股票包含主板、中小板、创业板和B股：深市主板股票代码是000开头、中小板股票代码002开头、创业板300开头、B股代码200开头
# print(gp_type_szsh('002340'))
# 
def gp_type_szsh(gp):
    if gp.find('60',0,3)==0:
        gp_type='sh'
    elif gp.find('688',0,4)==0:
        gp_type='sh'
    elif gp.find('900',0,4)==0:
        gp_type='sh'
    elif gp.find('00',0,3)==0:
        gp_type='sz'
    elif gp.find('300',0,4)==0:
        gp_type='sz'
    elif gp.find('200',0,4)==0:
        gp_type='sz'
    return gp_type
