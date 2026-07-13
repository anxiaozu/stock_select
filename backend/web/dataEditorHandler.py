#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


from tornado import gen
# import sys
# import os
# sys.path.append(os.path.abspath('/data/stock/libs'))
import libs.stock_web_dic as stock_web_dic
import web.base as webBase
import libs.common as common
import logging
import re

# 获得页面数据。
class GetEditorHtmlHandler(webBase.BaseHandler):
    @gen.coroutine
    def get(self):
        name = self.get_argument("table_name", default=None, strip=False)
        stockWeb = stock_web_dic.STOCK_WEB_DATA_MAP[name]
        # self.uri_ = ("self.request.url:", self.request.uri)
        # print self.uri_
        self.render("data_editor.html", stockWeb=stockWeb,
                    pythonStockVersion=common.__version__,
                    leftMenu=webBase.GetLeftMenu(self.request.uri))


# 拼接sql，将value的key 和 value 放到一起。
# 列名来自表定义(stockWeb.columns / primary_key，白名单)，值用占位符 %s 绑定，返回(片段, 参数列表)。
def genSql(primary_key, param_map, join_string):
    tmp_sql = ""
    params = []
    idx = 0
    for tmp_key in primary_key:
        tmp_val = param_map[tmp_key]
        clause = " `%s` = %%s " % tmp_key
        if idx == 0:
            tmp_sql = clause
        else:
            tmp_sql += join_string + clause
        params.append(tmp_val)
        idx += 1
    return tmp_sql, params


# 获得页面数据。
class SaveEditorHandler(webBase.BaseHandler):
    @gen.coroutine
    def post(self):
        action = self.get_argument("action", default=None, strip=False)
        logging.info(action)
        table_name = self.get_argument("table_name", default=None, strip=False)
        stockWeb = stock_web_dic.STOCK_WEB_DATA_MAP[table_name]
        # 临时map数组。
        param_map = {}
        # 支持多排序。使用shift+鼠标左键。
        for item, val in self.request.arguments.items():
            # 正则查找  data[1112][code] 里面的code字段
            item_key = re.search(r"\]\[(.*?)\]", item)
            if item_key:
                tmp_1 = item_key.group()
                if tmp_1:
                    tmp_1 = tmp_1.replace("][", "").replace("]", "")
                    param_map[tmp_1] = val[0].decode("utf-8")
        #logging.info(param_map)
        if action == "create":
            logging.info("###########################create")
            # 拼接where 和 update 语句。列名来自白名单，值用占位符绑定。
            tmp_columns = "`, `".join(stockWeb.columns)
            tmp_values = []
            for tmp_key in stockWeb.columns:
                tmp_values.append(param_map[tmp_key])
            # 更新sql。
            placeholders = ", ".join(["%s"] * len(tmp_values))
            insert_sql = " INSERT INTO `%s` (`%s`) VALUES(%s); " % (stockWeb.table_name, tmp_columns, placeholders)
            logging.info(insert_sql)
            try:
                self.db.execute(insert_sql, *tmp_values)
            except Exception as e:
                err = {"error": str(e)}
                logging.info(err)
                self.write(err)
                return

        elif action == "edit":
            logging.info("###########################edit")
            # 拼接where 和 update 语句。
            tmp_update, update_params = genSql(stockWeb.columns, param_map, ",")
            tmp_where, where_params = genSql(stockWeb.primary_key, param_map, "and")
            # 更新sql。
            update_sql = " UPDATE `%s` SET %s WHERE %s " % (stockWeb.table_name, tmp_update, tmp_where)
            logging.info(update_sql)
            try:
                self.db.execute(update_sql, *(update_params + where_params))
            except Exception as e:
                err = {"error": str(e)}
                logging.info(err)
                self.write(err)
                return
        elif action == "remove":
            logging.info("###########################remove")
            # 拼接where 语句。
            tmp_where, where_params = genSql(stockWeb.primary_key, param_map, "and")
            # 更新sql。
            delete_sql = " DELETE FROM `%s` WHERE %s " % (stockWeb.table_name, tmp_where)
            logging.info(delete_sql)
            try:
                self.db.execute(delete_sql, *where_params)
            except Exception as e:
                err = {"error": str(e)}
                logging.info(err)
                self.write(err)
                return
        self.write("{\"data\":[{}]}")
