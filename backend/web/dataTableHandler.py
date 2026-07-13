#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import json
from tornado import gen
import libs.common as common
import libs.stock_web_dic as stock_web_dic
import web.base as webBase
import logging
import datetime

# info 蓝色 云财经
# success 绿色
#  danger 红色 东方财富
#  warning 黄色
WEB_EASTMONEY_URL = u"""
    <a class='btn btn-danger btn-xs tooltip-danger' data-rel="tooltip" data-placement="right" data-original-title="东方财富，股票详细地址，新窗口跳转。"
    href='http://quote.eastmoney.com/%s.html' target='_blank'>东财</a>
    
    <a class='btn btn-success btn-xs tooltip-success' data-rel="tooltip" data-placement="right" data-original-title="本地MACD，KDJ等指标，本地弹窗窗口，数据加载中，请稍候。"
    onclick="showIndicatorsWindow('%s');">指标</a>
    
    <a class='btn btn-warning btn-xs tooltip-warning' data-rel="tooltip" data-placement="right" data-original-title="东方财富，研报地址，本地弹窗窗口。"
    onclick="showDFCFWindow('%s');">东研</a>
    
    
    """
# 和在dic中的字符串一致。字符串前面都不特别声明是u""
eastmoney_name = "查看股票"


# 获得页面数据，进入页面中。
class GetStockHtmlHandler(webBase.BaseHandler):
    @gen.coroutine
    def get(self):
        name = self.get_argument("table_name", default=None, strip=False)
        tableInfo = stock_web_dic.STOCK_WEB_DATA_MAP[name]
        # self.uri_ = ("self.request.url:", self.request.uri)
        # print self.uri_
        date_now = datetime.datetime.now()
        date_now_str = date_now.strftime("%Y%m%d")
        # 每天的 16 点前显示昨天数据。
        if date_now.hour < 16:
            date_now_str = (date_now + datetime.timedelta(days=-1)).strftime("%Y%m%d")

        # try:
        #     # 增加columns 字段中的【查看股票 东方财富】
        #     logging.info(eastmoney_name in tableInfo.column_names)
        #     if eastmoney_name in tableInfo.column_names:
        #         tmp_idx = tableInfo.column_names.index(eastmoney_name)
        #         logging.info(tmp_idx)
        #         try:
        #             # 防止重复插入数据。可能会报错。
        #             tableInfo.columns.remove("eastmoney_url")
        #         except Exception as e:
        #             print("error :", e)
        #         tableInfo.columns.insert(tmp_idx, "eastmoney_url")
        # except Exception as e:
        #     print("error :", e)
        logging.info("####################GetStockHtmlHandlerEnd")
        self.render("tableInfo.html", tableInfo=tableInfo, date_now=date_now_str,
                    pythonStockVersion=common.__version__,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


# 获得股票数据内容。
class GetStockDataHandler(webBase.BaseHandler):
    def get(self):

        self.set_header('Content-Type', 'application/json;charset=UTF-8')

        logging.info("######################## GetStockDataHandler ########################")
        # 获得分页参数。
        page_param = self.get_argument("page", default=0, strip=False)
        limit_param = self.get_argument("limit", default=10, strip=False)

        name_param = self.get_argument("name", default="stock_zh_ah_name", strip=False)
        type_param = self.get_argument("type", default=None, strip=False)
        date_param = self.get_argument("date", default=None, strip=False)
        code_param = self.get_argument("code", default=None, strip=False)
        # 股票名称模糊搜索(参数名避开 name=表名)。
        stock_name_param = self.get_argument("stock_name", default=None, strip=False)

        logging.info(f"page param: {page_param}, {limit_param}, {type_param}, {date_param}, {code_param}")


        if name_param == ":tableName":
            obj = {
            "code": 20000,
            "message": "success",
            "draw": 0,
            "data": []
            }
            # logging.info("####################")
            # logging.info(obj)
            self.write(json.dumps(obj))
            return


        tableInfo = stock_web_dic.STOCK_WEB_DATA_MAP[name_param]

        
        order_by_column = []
        order_by_dir = []
        # 支持多排序。使用shift+鼠标左键。
        for item, val in self.request.arguments.items():
            # logging.info("item: %s, val: %s" % (item, val) )
            if str(item).startswith("order["):
                print("order:", item, ",val:", val[0])
            if str(item).startswith("order[") and str(item).endswith("[column]"):
                order_by_column.append(int(val[0]))
            if str(item).startswith("order[") and str(item).endswith("[dir]"):
                order_by_dir.append(val[0].decode("utf-8"))  # bytes转换字符串

        search_by_column = []
        search_by_data = []

        # 返回search字段。
        for item, val in self.request.arguments.items():
            # logging.info("item: %s, val: %s" % (item, val))
            if str(item).startswith("columns[") and str(item).endswith("[search][value]"):
                logging.info("item: %s, val: %s" % (item, val))
                str_idx = item.replace("columns[", "").replace("][search][value]", "")
                try:
                    int_idx = int(str_idx)
                except (ValueError, TypeError):
                    continue
                # 列索引越界直接跳过，列名只能来自表定义(白名单)。
                if int_idx < 0 or int_idx >= len(tableInfo.columns):
                    continue
                # 找到字符串
                str_val = val[0].decode("utf-8")
                if str_val != "":  # 字符串。
                    search_by_column.append(tableInfo.columns[int_idx])
                    search_by_data.append(val[0].decode("utf-8"))  # bytes转换字符串

        # 打印日志。
        # 使用参数化查询，值全部通过占位符 %s 绑定，列名只来自表定义(白名单)。
        search_sql = ""
        search_params = []
        search_idx = 0

        logging.info("################# search_by_column #################")

        logging.info(search_by_column)
        logging.info(search_by_data)
        for item in search_by_column:
            val = search_by_data[search_idx]
            logging.info("idx: %s, column: %s, value: %s " % (search_idx, item, val))
            # 查询sql：列名来自 tableInfo.columns 白名单，值用占位符绑定。
            clause = " `%s` = %%s " % item
            if search_idx == 0:
                search_sql = " WHERE " + clause
            else:
                search_sql = search_sql + " AND " + clause
            search_params.append(val)
            search_idx = search_idx + 1

        # 买入/卖出推荐表：未传 date 时默认最新交易日，避免历史全表刷出几十页。
        _LATEST_DATE_TABLES = (
            "guess_indicators_lite_buy_daily",
            "guess_indicators_lite_sell_daily",
        )
        if not date_param and name_param in _LATEST_DATE_TABLES:
            try:
                latest_rows = self.db.query(
                    " SELECT max(`date`) AS d FROM `%s` " % tableInfo.table_name)
                if latest_rows and latest_rows[0].get("d") is not None:
                    date_param = str(latest_rows[0]["d"])
                    logging.info("default latest date for %s: %s", name_param, date_param)
            except Exception as e:
                logging.warning("resolve latest date failed for %s: %s", name_param, e)

        if date_param:
            if "WHERE" not in search_sql:
                search_sql += " WHERE `date` = %s "
            else:
                search_sql += " AND `date` = %s "
            search_params.append(date_param)

        if code_param:
            # 代码模糊匹配：输 600519 不必带 sh/sz 前缀。
            if "WHERE" not in search_sql:
                search_sql += " WHERE `code` LIKE %s "
            else:
                search_sql += " AND `code` LIKE %s "
            search_params.append("%" + code_param + "%")

        if stock_name_param and "name" in tableInfo.columns:
            # 名称模糊匹配：输"茅台"可搜到"贵州茅台"。
            if "WHERE" not in search_sql:
                search_sql += " WHERE `name` LIKE %s "
            else:
                search_sql += " AND `name` LIKE %s "
            search_params.append("%" + stock_name_param + "%")

        # print("tableInfo :", stock_web)
        order_by_sql = ""
        # 增加排序。
        if len(order_by_column) != 0 and len(order_by_dir) != 0:
            order_clauses = []
            idx = 0
            for key in order_by_column:
                # 排序字段索引必须落在表定义范围内(白名单)，否则跳过。
                if not isinstance(key, int) or key < 0 or key >= len(tableInfo.columns):
                    idx += 1
                    continue
                col_tmp = tableInfo.columns[key]
                # 排序方向白名单校验，只允许 ASC/DESC，非法回退 ASC。
                dir_raw = order_by_dir[idx] if idx < len(order_by_dir) else "asc"
                dir_tmp = "DESC" if str(dir_raw).strip().lower() == "desc" else "ASC"
                order_clauses.append(" `%s` %s " % (col_tmp, dir_tmp))
                idx += 1
            if order_clauses:
                order_by_sql = "  ORDER BY " + " , ".join(order_clauses)
        # 未指定排序时，使用表定义里的默认排序(代码内白名单，非用户输入)。
        if not order_by_sql and getattr(tableInfo, "order_by", None):
            order_by_sql = " ORDER BY " + tableInfo.order_by
        # 查询数据库。limit/offset 强制转 int，防止注入。
        limit_sql = ""
        try:
            limit_int = int(limit_param)
        except (ValueError, TypeError):
            limit_int = 0
        try:
            page_int = int(page_param)
        except (ValueError, TypeError):
            page_int = 0
        if limit_int > 0:
            start = (page_int - 1) * limit_int
            if start < 0:
                start = 0
            limit_sql = " LIMIT %d , %d " % (start, limit_int)
        sql = " SELECT * FROM `%s` %s %s %s " % (
            tableInfo.table_name, search_sql, order_by_sql, limit_sql)
        count_sql = " SELECT count(1) as num FROM `%s` %s " % (tableInfo.table_name, search_sql)

        logging.info("select sql : " + sql)
        logging.info("count sql : " + count_sql)
        stock_web_list = self.db.query(sql, *search_params)

        stock_web_size = self.db.query(count_sql, *search_params)
        logging.info("tableInfoList size : %s " % stock_web_size)

        # 动态表格展示：
        table_columns = []
        try:
            tmp_len = len(tableInfo.columns)
            logging.info("ableInfo.columns tmp_len : %s " % tmp_len)
            # 循环数据，转换成对象，放入到数组中，方便前端 vue table 循环使用。
            for tmp_idx in range(0, tmp_len):
                logging.info(tmp_idx)

                column = tableInfo.columns[tmp_idx]
                column_name = tableInfo.column_names[tmp_idx]

                tpm_column_obj = {
                    "column": column,
                    "columnName" : column_name
                }
                table_columns.append(tpm_column_obj)
               
        except Exception as e:
            print("error :", e)

        obj = {
            "code": 20000,
            "message": "success",
            "draw": 0,
            "tableName" : tableInfo.name,
            "tableColumns":  table_columns,
            "total": stock_web_size[0]["num"],
            "recordsTotal": stock_web_size[0]["num"],
            "recordsFiltered": stock_web_size[0]["num"],
            "date": date_param,
            "data": stock_web_list
        }
        # logging.info("####################")
        # logging.info(obj)
        self.write(json.dumps(obj))
