#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""分批跑指标计算，避免 API 限流"""

import libs.common as common
import pandas as pd
import numpy as np
import datetime
import stockstats
import time
import traceback
import signal

BATCH_SIZE = 50
PAUSE_SECONDS = 3
API_TIMEOUT = 15  # Sina API 超时秒数

datetime_int = '20260710'
date_end = '2026-07-10'
date_start = '2026-03-31'

stock_column = ['date','code', 'boll', 'boll_lb', 'boll_ub',
                'kdjd', 'kdjj', 'kdjk', 'macd', 'macdh', 'macds', 'pdi',
                'trix', 'trix_9_sma', 'vr', 'vr_6_sma', 'wr_10', 'wr_6',
                'close_5_sma', 'close_10_sma', 'close_20_sma', 'close_60_sma',
                'volume_5_sma', 'high_20_max', 'rsi_6']

def calc_one_stock(row):
    """计算单只股票的指标"""
    code = row['code']
    date = datetime_int
    try:
        stock = common.get_hist_data_cache(code, date_start, date_end)
        if stock is None:
            return None

        stock["date"] = stock.index.values
        stockStat = stockstats.StockDataFrame.retype(stock)

        result = {}
        for col in stock_column:
            if col == 'date':
                result[col] = date
            elif col == 'code':
                result[col] = code
            else:
                try:
                    tmp_val = stockStat[col].values[-1]
                    if np.isinf(tmp_val):
                        tmp_val = 0
                    if np.isnan(tmp_val):
                        tmp_val = 0
                    result[col] = tmp_val
                except:
                    result[col] = 0
        return result
    except Exception as e:
        print(f"  SKIP {code}: {str(e)[:80]}")
        return None

def run_batch(offset, batch_size):
    """跑一批"""
    sql = f"""
        SELECT `date`,`code`,`name`,`last_price`,`change_percent`,`change_amount`,`volume`,`turnover`,
               `amplitude`,`high`,`low`,`open`,`closed`,`volume_ratio`,`turnover_rate`,
               `pe_ratio`,`pb_ratio`,`market_cap`,`circulating_market_cap`,`rise_speed`,
               `change_5min`,`change_ercent_60day`,`ytd_change_percent`
        FROM stock_zh_a_spot_em WHERE `date` = {datetime_int} and `open` > 0
        ORDER BY code LIMIT {offset}, {batch_size}
    """
    data = pd.read_sql(sql=sql, con=common.engine())
    data = data.drop_duplicates(subset="code", keep="last")
    if len(data) == 0:
        return []

    results = []
    for _, row in data.iterrows():
        r = calc_one_stock(row)
        if r:
            results.append(r)
    return results

def main():
    # 获取总数和已完成数
    total_sql = f"SELECT count(1) FROM stock_zh_a_spot_em WHERE `date` = {datetime_int} and `open` > 0"
    total = common.select_count(total_sql)

    # 检查已完成
    done_sql = f"SELECT count(1) FROM guess_indicators_daily WHERE `date` = {datetime_int}"
    done = common.select_count(done_sql)

    # 获取已完成code列表
    done_codes_sql = f"SELECT code FROM guess_indicators_daily WHERE `date` = {datetime_int}"
    done_codes = set()
    try:
        done_data = pd.read_sql(sql=done_codes_sql, con=common.engine())
        done_codes = set(done_data['code'].tolist())
    except:
        pass

    # 获取所有待处理code
    all_sql = f"SELECT code FROM stock_zh_a_spot_em WHERE `date` = {datetime_int} and `open` > 0 ORDER BY code"
    all_data = pd.read_sql(sql=all_sql, con=common.engine())
    pending_codes = [c for c in all_data['code'].tolist() if c not in done_codes]

    print(f"总数: {len(all_data)}, 已完成: {len(done_codes)}, 待处理: {len(pending_codes)}")

    if len(pending_codes) == 0:
        print("全部完成！")
        return

    # 分批处理
    for i in range(0, len(pending_codes), BATCH_SIZE):
        batch_codes = pending_codes[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(pending_codes) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n批次 {batch_num}/{total_batches}: 处理 {batch_codes[0]} ~ {batch_codes[-1]} ({len(batch_codes)} 只)")

        batch_results = []
        for code in batch_codes:
            row = all_data[all_data['code'] == code].iloc[0]
            r = calc_one_stock(row)
            if r:
                batch_results.append(r)

        if batch_results:
            df_batch = pd.DataFrame(batch_results)
            # 合并原始数据
            batch_codes_set = set(df_batch['code'].tolist())
            original_data = all_data[all_data['code'].isin(batch_codes_set)].copy()
            original_data = original_data.drop_duplicates(subset="code", keep="last")

            data_new = pd.merge(original_data, df_batch, on=['code'], how='left')
            data_new = data_new.round(2)
            data_new.drop('date_y', axis=1, inplace=True, errors='ignore')
            data_new.rename(columns={'date_x': 'date'}, inplace=True)

            try:
                common.insert_db(data_new, "guess_indicators_daily", False, "`date`,`code`")
                print(f"  入库 {len(batch_results)} 条, 总进度: {done + len(batch_results) + i}/{total}")
            except Exception as e:
                print(f"  入库失败: {e}")

        # 批次间休息
        if i + BATCH_SIZE < len(pending_codes):
            print(f"  休息 {PAUSE_SECONDS}s...")
            time.sleep(PAUSE_SECONDS)

    # 最终统计
    final_done = common.select_count(f"SELECT count(1) FROM guess_indicators_daily WHERE `date` = {datetime_int}")
    print(f"\n完成! 指标表: {final_done}/{total}")

if __name__ == '__main__':
    main()
