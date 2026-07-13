# -*- coding: utf-8 -*-
"""
pytest 公共配置。

设计目标（务必保持）：
- 这些测试 **零依赖数据库、零网络**：全部用合成的 pandas DataFrame 构造数据。
- 绝不 `import libs.common` / `import jobs.*`，因为那些模块在导入时就会连接数据库并打印。
  因此本套件把业务规则（买卖策略布尔条件、缓存索引规范化、stockstats 取值语义）
  在测试内 **独立复现**，属于“规格测试 / 回归守卫”。

可运行性：
- 从仓库根 `python -m pytest backend/tests -q` 或
- 从 backend 目录 `python -m pytest tests -q` 都能收集运行。
- 这里把 backend 目录加入 sys.path 只是为了保险（当前测试并不 import 业务代码）。
"""

import os
import sys

# backend 目录（本文件在 backend/tests/ 下）。
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
