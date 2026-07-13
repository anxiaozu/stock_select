<template>
  <div class="dashboard-container">

    <!-- 顶部统计卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-blue">
          <div class="stat-title">数据日期</div>
          <div class="stat-value">{{ dataDate || '—' }}</div>
          <div class="stat-desc">最近一次每日任务</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-red">
          <div class="stat-title">买入推荐</div>
          <div class="stat-value">{{ buyCount }}<span class="stat-unit">只</span></div>
          <div class="stat-desc">多策略并集 + 综合分排序</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-green">
          <div class="stat-title">卖出提示</div>
          <div class="stat-value">{{ sellCount }}<span class="stat-unit">只</span></div>
          <div class="stat-desc">见顶回落 / 均线空头 / 跌破下轨</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-purple">
          <div class="stat-title">指标覆盖</div>
          <div class="stat-value">{{ indicatorCount }}<span class="stat-unit">只</span></div>
          <div class="stat-desc">全市场每日指标计算</div>
        </div>
      </el-col>
    </el-row>

    <!-- 市场情绪面 + 消息面 -->
    <el-row :gutter="20">
      <el-col :sm="12">
        <el-card shadow="never" class="panel-card sentiment-card">
          <div slot="header" class="panel-header">
            <span class="panel-title">市场情绪面</span>
            <span class="rule-muted">{{ sentiment.date || '' }}</span>
          </div>
          <div v-if="sentiment.total">
            <!-- 涨跌分布条 -->
            <div class="updown-bar">
              <div class="bar-up" :style="{width: upPercent + '%'}"></div>
              <div class="bar-down" :style="{width: (100 - upPercent) + '%'}"></div>
            </div>
            <div class="updown-label">
              <span class="text-up">上涨 {{ sentiment.up }} 家</span>
              <span class="rule-muted">平盘 {{ sentiment.flat }}</span>
              <span class="text-down">下跌 {{ sentiment.down }} 家</span>
            </div>
            <el-row class="senti-stats">
              <el-col :span="6">
                <div class="senti-num text-up">{{ sentiment.limitUp }}</div>
                <div class="senti-name">涨停(家)</div>
              </el-col>
              <el-col :span="6">
                <div class="senti-num text-down">{{ sentiment.limitDown }}</div>
                <div class="senti-name">跌停(家)</div>
              </el-col>
              <el-col :span="6">
                <div class="senti-num" :class="sentiment.avgChange >= 0 ? 'text-up' : 'text-down'">
                  {{ sentiment.avgChange >= 0 ? '+' : '' }}{{ sentiment.avgChange }}%</div>
                <div class="senti-name">平均涨跌幅</div>
              </el-col>
              <el-col :span="6">
                <div class="senti-num">{{ sentiment.totalTurnoverYi }}</div>
                <div class="senti-name">总成交(亿元)</div>
              </el-col>
            </el-row>
            <!-- 市场温度 -->
            <div class="temp-line">
              <span class="senti-name">市场温度</span>
              <el-progress :percentage="sentiment.temperature" :stroke-width="16"
                           :color="tempColor" class="temp-progress" />
              <span class="temp-text" :style="{color: tempColor}">{{ tempText }}</span>
            </div>
          </div>
          <div v-else class="empty-tip">暂无情绪数据</div>
        </el-card>
      </el-col>
      <el-col :sm="12">
        <el-card shadow="never" class="panel-card news-card">
          <div slot="header" class="panel-header">
            <span class="panel-title">消息面 · 财经快讯</span>
            <span class="rule-muted">新浪财经 · 5分钟更新</span>
          </div>
          <div v-if="news.length" class="news-list">
            <div v-for="(n, i) in news" :key="i" class="news-item">
              <span class="news-time">{{ n.time }}</span>
              <span class="news-content">{{ n.content }}</span>
            </div>
          </div>
          <div v-else class="empty-tip">快讯加载中或暂不可用</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 市场风格 / 个股风向标 / 大盘星图 -->
    <el-card shadow="never" class="panel-card market-lab-card">
      <div slot="header" class="panel-header">
        <span class="panel-title">市场风格 · 大盘星图</span>
        <span class="rule-muted">{{ marketStyleHint }}</span>
      </div>
      <el-tabs v-model="marketTab" @tab-click="onMarketTabClick">
        <el-tab-pane label="市场风格" name="style">
          <div v-if="marketStyle.suggestedPosition != null" class="style-panel">
            <el-row :gutter="20">
              <el-col :xs="24" :sm="8">
                <div class="gauge-wrap">
                  <div ref="posGauge" class="gauge-chart" />
                  <div class="gauge-caption">{{ marketStyle.hint || '根据市场表现估算建议仓位' }}</div>
                </div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="effect-box">
                  <div class="effect-label">赚钱效应</div>
                  <div class="effect-value" :class="effectClass">{{ marketStyle.moneyEffect || '—' }}</div>
                  <div class="updown-label" style="margin-top:16px">
                    <span class="text-up">涨 {{ marketStyle.up }}</span>
                    <span class="rule-muted">平 {{ marketStyle.flat }}</span>
                    <span class="text-down">跌 {{ marketStyle.down }}</span>
                  </div>
                  <div class="updown-bar" style="margin-top:10px">
                    <div class="bar-up" :style="{width: styleUpPercent + '%'}"></div>
                    <div class="bar-down" :style="{width: (100 - styleUpPercent) + '%'}"></div>
                  </div>
                </div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="effect-box">
                  <div class="effect-label">市场温度</div>
                  <div class="effect-value" :style="{color: tempColor}">{{ marketStyle.temperature || '—' }}°</div>
                  <div class="rule-muted" style="margin-top:8px">均涨跌 {{ formatSigned(marketStyle.avgChange) }}%</div>
                </div>
              </el-col>
            </el-row>
            <div class="tile-title">板块资金风向（红=净流入，绿=净流出）</div>
            <div class="sector-tiles">
              <div
                v-for="t in (marketStyle.sectorTiles || [])"
                :key="t.name"
                class="sector-tile"
                :class="t.netAmount >= 0 ? 'tile-in' : 'tile-out'"
              >
                <div class="tile-name">{{ t.name }}</div>
                <div class="tile-chg">{{ formatSigned(t.changePercent) }}%</div>
                <div class="tile-net">{{ formatSigned(t.netAmount) }} 亿</div>
              </div>
              <div v-if="!(marketStyle.sectorTiles && marketStyle.sectorTiles.length)" class="empty-tip">暂无板块资金数据</div>
            </div>
          </div>
          <div v-else class="empty-tip">市场风格加载中…</div>
        </el-tab-pane>

        <el-tab-pane label="个股风向标" name="vane">
          <el-row :gutter="20">
            <el-col :sm="12">
              <div class="vane-title text-up">涨幅前列</div>
              <el-table :data="stockVane.gainers || []" size="small" stripe>
                <el-table-column type="index" width="45" />
                <el-table-column prop="code" label="代码" width="90" />
                <el-table-column prop="name" label="名称" width="90" />
                <el-table-column label="涨跌幅" width="90">
                  <template slot-scope="{row}">
                    <span class="text-up">{{ formatSigned(row.changePercent) }}%</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template slot-scope="{row}">
                    <el-button type="text" @click="openEastmoney(row.code)">行情</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-col>
            <el-col :sm="12">
              <div class="vane-title text-down">跌幅前列</div>
              <el-table :data="stockVane.losers || []" size="small" stripe>
                <el-table-column type="index" width="45" />
                <el-table-column prop="code" label="代码" width="90" />
                <el-table-column prop="name" label="名称" width="90" />
                <el-table-column label="涨跌幅" width="90">
                  <template slot-scope="{row}">
                    <span class="text-down">{{ formatSigned(row.changePercent) }}%</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template slot-scope="{row}">
                    <el-button type="text" @click="openEastmoney(row.code)">行情</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="大盘星图" name="star">
          <div class="star-toolbar">
            <el-radio-group v-model="starMode" size="small" @change="renderStarMap">
              <el-radio-button label="industry">行业板块</el-radio-button>
              <el-radio-button label="stockCap">个股市值</el-radio-button>
            </el-radio-group>
            <span class="rule-muted star-note">{{ starNote }}</span>
          </div>
          <div ref="starMap" class="star-chart" v-loading="starLoading" />
          <div class="star-legend">
            <span class="leg-down">跌</span>
            <span class="leg-bar" />
            <span class="leg-up">涨</span>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 板块资金流 Top8 -->
    <el-row :gutter="20">
      <el-col :sm="12">
        <el-card shadow="never" class="panel-card flow-card">
          <div slot="header" class="panel-header">
            <span class="panel-title">行业资金流入 Top8</span>
            <el-button type="text" @click="goTable('stock_fund_flow_industry')">查看全部 »</el-button>
          </div>
          <div v-if="industryFlow.length">
            <div v-for="(f, i) in industryFlow" :key="f.name" class="flow-item">
              <span class="flow-rank" :class="{'flow-rank-top': i < 3}">{{ i + 1 }}</span>
              <span class="flow-name">{{ f.name }}</span>
              <span class="flow-change" :class="f.changePercent >= 0 ? 'text-up' : 'text-down'">
                {{ f.changePercent >= 0 ? '+' : '' }}{{ f.changePercent }}%</span>
              <div class="flow-bar-wrap">
                <div class="flow-bar" :style="{width: flowBarWidth(f.netAmount, industryFlow) + '%'}"></div>
              </div>
              <span class="flow-amount" :class="f.netAmount >= 0 ? 'text-up' : 'text-down'">
                {{ f.netAmount >= 0 ? '+' : '' }}{{ f.netAmount }} 亿</span>
              <span class="flow-leader rule-muted">{{ f.leader }}</span>
            </div>
          </div>
          <div v-else class="empty-tip">暂无资金流数据（每日 18:00 更新）</div>
        </el-card>
      </el-col>
      <el-col :sm="12">
        <el-card shadow="never" class="panel-card flow-card">
          <div slot="header" class="panel-header">
            <span class="panel-title">概念资金流入 Top8</span>
            <el-button type="text" @click="goTable('stock_fund_flow_concept')">查看全部 »</el-button>
          </div>
          <div v-if="conceptFlow.length">
            <div v-for="(f, i) in conceptFlow" :key="f.name" class="flow-item">
              <span class="flow-rank" :class="{'flow-rank-top': i < 3}">{{ i + 1 }}</span>
              <span class="flow-name">{{ f.name }}</span>
              <span class="flow-change" :class="f.changePercent >= 0 ? 'text-up' : 'text-down'">
                {{ f.changePercent >= 0 ? '+' : '' }}{{ f.changePercent }}%</span>
              <div class="flow-bar-wrap">
                <div class="flow-bar" :style="{width: flowBarWidth(f.netAmount, conceptFlow) + '%'}"></div>
              </div>
              <span class="flow-amount" :class="f.netAmount >= 0 ? 'text-up' : 'text-down'">
                {{ f.netAmount >= 0 ? '+' : '' }}{{ f.netAmount }} 亿</span>
              <span class="flow-leader rule-muted">{{ f.leader }}</span>
            </div>
          </div>
          <div v-else class="empty-tip">暂无资金流数据（每日 18:00 更新）</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 今日买入 / 卖出 Top -->
    <el-row :gutter="20">
      <el-col :sm="24" :lg="14">
        <el-card shadow="never" class="panel-card">
          <div slot="header" class="panel-header">
            <span class="panel-title">今日买入推荐 Top20（按综合分）</span>
            <el-button type="text" @click="goBuyTable">查看全部 »</el-button>
          </div>
          <el-table :data="buyTop" v-loading="loading" size="medium" stripe style="width: 100%" max-height="420">
            <el-table-column type="index" label="#" width="50" align="center" />
            <el-table-column prop="code" label="代码" width="90" align="center" />
            <el-table-column prop="name" label="名称" width="100" align="center" />
            <el-table-column label="最新价" width="80" align="center">
              <template slot-scope="{row}">{{ row.last_price }}</template>
            </el-table-column>
            <el-table-column label="涨跌幅(%)" width="90" align="center">
              <template slot-scope="{row}">
                <span :class="row.change_percent >= 0 ? 'text-up' : 'text-down'">
                  {{ row.change_percent >= 0 ? '+' : '' }}{{ row.change_percent }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="综合分" min-width="140" align="center">
              <template slot-scope="{row}">
                <el-progress :percentage="Math.min(100, Number(row.score) || 0)"
                             :stroke-width="14" :format="() => row.score" color="#e6a23c" />
              </template>
            </el-table-column>
            <el-table-column label="命中策略" min-width="120" align="center">
              <template slot-scope="{row}">
                <el-tag v-for="s in splitStrategy(row.strategy)" :key="s" size="small"
                        :type="s === 'KDJ强势' ? 'danger' : 'success'" class="strategy-tag">{{ s }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template slot-scope="{row}">
                <el-button type="primary" size="mini" plain @click="openEastmoney(row.code)">行情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!loading && buyTop.length === 0" class="empty-tip">暂无买入推荐（当日无策略命中）</div>
        </el-card>
      </el-col>
      <el-col :sm="24" :lg="10">
        <el-card shadow="never" class="panel-card">
          <div slot="header" class="panel-header">
            <span class="panel-title">今日卖出提示 Top20</span>
            <el-button type="text" @click="goSellTable">查看全部 »</el-button>
          </div>
          <el-table :data="sellTop" v-loading="sellLoading" size="medium" stripe style="width: 100%" max-height="420">
            <el-table-column type="index" label="#" width="45" align="center" />
            <el-table-column prop="code" label="代码" width="90" align="center" />
            <el-table-column prop="name" label="名称" width="90" align="center" />
            <el-table-column label="涨跌幅(%)" width="90" align="center">
              <template slot-scope="{row}">
                <span :class="row.change_percent >= 0 ? 'text-up' : 'text-down'">
                  {{ row.change_percent >= 0 ? '+' : '' }}{{ row.change_percent }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="综合分" width="70" align="center">
              <template slot-scope="{row}">{{ row.score }}</template>
            </el-table-column>
            <el-table-column label="策略" min-width="100" align="center" show-overflow-tooltip>
              <template slot-scope="{row}">{{ row.strategy }}</template>
            </el-table-column>
          </el-table>
          <div v-if="!sellLoading && sellTop.length === 0" class="empty-tip">暂无卖出提示</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 今日龙虎榜净买 Top5 -->
    <el-card shadow="never" class="panel-card">
      <div slot="header" class="panel-header">
        <span class="panel-title">今日龙虎榜净买 Top5</span>
        <el-button type="text" @click="goTable('stock_lhb_detail_daily')">查看全部 »</el-button>
      </div>
      <el-table :data="lhbTop" v-loading="lhbLoading" size="medium" stripe style="width: 100%">
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column prop="code" label="代码" width="100" align="center" />
        <el-table-column prop="name" label="名称" width="120" align="center" />
        <el-table-column label="涨跌幅(%)" width="100" align="center">
          <template slot-scope="{row}">
            <span :class="row.change_percent >= 0 ? 'text-up' : 'text-down'">
              {{ row.change_percent >= 0 ? '+' : '' }}{{ row.change_percent }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="净买额(元)" min-width="120" align="center">
          <template slot-scope="{row}">
            <span :class="row.net_amount >= 0 ? 'text-up' : 'text-down'">
              {{ formatAmount(row.net_amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="上榜原因" min-width="160" align="center" show-overflow-tooltip />
        <el-table-column label="操作" width="160" align="center">
          <template slot-scope="{row}">
            <el-button type="primary" size="mini" plain @click="openEastmoney(row.code)">行情</el-button>
            <el-button type="warning" size="mini" plain @click="goLhbSeat(row.code)">席位</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!lhbLoading && lhbTop.length === 0" class="empty-tip">暂无龙虎榜数据</div>
    </el-card>

    <!-- 选股依据说明 -->
    <el-row :gutter="20">
      <el-col :sm="12">
        <el-card shadow="never" class="panel-card rule-card">
          <div slot="header" class="panel-header"><span class="panel-title">买入依据（命中任一即入选）</span></div>
          <p><el-tag type="danger" size="small">KDJ强势</el-tag> KDJ 高位强势（K&gt;80, D&gt;70, J&gt;90）+ MACD 多头 + 站上布林中轨 + 放量确认<span class="rule-note">（回测 5 日均收益 +3.59%，胜率 66.7%）</span></p>
          <p><el-tag type="success" size="small">均线多头</el-tag> MA5&gt;MA10&gt;MA20&gt;MA60 多头排列 + 站上 MA5 + MACD 多头<span class="rule-note">（回测超额 +0.45%）</span></p>
          <p class="rule-muted">基础过滤：非 ST、价 &gt; 2 元、未涨停；“放量突破(追新高)”经回测为负收益，已下线。</p>
        </el-card>
      </el-col>
      <el-col :sm="12">
        <el-card shadow="never" class="panel-card rule-card">
          <div slot="header" class="panel-header"><span class="panel-title">卖出依据（命中任一即提示）</span></div>
          <p><el-tag type="warning" size="small">见顶回落</el-tag> 曾强势（J&gt;80）但 MACD 转空且跌破 5 日线</p>
          <p><el-tag type="info" size="small">均线空头</el-tag> MA5&lt;MA10&lt;MA20&lt;MA60，趋势整体走坏</p>
          <p><el-tag size="small">跌破下轨</el-tag> 股价跌破布林下轨，破位</p>
          <p class="rule-muted">技术面短线信号（5 日视角），不含基本面，仅供参考，不构成投资建议。</p>
        </el-card>
      </el-col>
    </el-row>

    <!-- 基础库版本 -->
    <el-card shadow="never" class="panel-card version-card">
      <div slot="header" class="panel-header"><span class="panel-title">运行环境</span></div>
      <el-tag v-for="v in versionTags" :key="v.name" size="small" type="info" class="version-tag">
        {{ v.name }} {{ v.version }}
      </el-tag>
      <span class="rule-muted version-links">
        <el-link type="primary" href="https://gitee.com/pythonstock/stock" target="_blank">项目地址</el-link>
        <el-link type="primary" href="https://akshare.akfamily.xyz/data/index/index.html" target="_blank">AkShare 文档</el-link>
      </span>
    </el-card>

  </div>
</template>

<script>
import * as echarts from 'echarts'
import request from '@/utils/request'
import { fetchList } from '@/api/article'
import { fetchPackageVersion } from '@/api/package'

function changeToColor(pct) {
  const p = Number(pct) || 0
  if (p >= 4) return '#b71c1c'
  if (p >= 2) return '#e53935'
  if (p >= 1) return '#ef9a9a'
  if (p > 0) return '#ffcdd2'
  if (p === 0) return '#90a4ae'
  if (p > -1) return '#c8e6c9'
  if (p > -2) return '#81c784'
  if (p > -4) return '#43a047'
  return '#1b5e20'
}

export default {
  name: 'Dashboard',
  data() {
    return {
      loading: true,
      sellLoading: true,
      lhbLoading: true,
      starLoading: false,
      dataDate: '',
      buyCount: 0,
      sellCount: 0,
      indicatorCount: 0,
      buyTop: [],
      sellTop: [],
      lhbTop: [],
      versionTags: [],
      sentiment: {},
      news: [],
      industryFlow: [],
      conceptFlow: [],
      marketStyle: {},
      stockVane: { gainers: [], losers: [] },
      starMap: { industry: {}, stockCap: {} },
      marketTab: 'style',
      starMode: 'industry',
      posGaugeChart: null,
      starChart: null
    }
  },
  computed: {
    upPercent() {
      const t = (this.sentiment.up || 0) + (this.sentiment.down || 0)
      return t > 0 ? Math.round(this.sentiment.up * 100 / t) : 50
    },
    styleUpPercent() {
      const t = (this.marketStyle.up || 0) + (this.marketStyle.down || 0)
      return t > 0 ? Math.round(this.marketStyle.up * 100 / t) : 50
    },
    tempColor() {
      const t = this.sentiment.temperature || this.marketStyle.temperature || 50
      if (t >= 65) return '#f56c6c'
      if (t >= 45) return '#e6a23c'
      return '#67c23a'
    },
    tempText() {
      const t = this.sentiment.temperature || 50
      if (t >= 75) return '过热'
      if (t >= 60) return '偏暖'
      if (t >= 45) return '中性'
      if (t >= 30) return '偏冷'
      return '冰点'
    },
    effectClass() {
      const e = this.marketStyle.moneyEffect
      if (e === '强') return 'text-up'
      if (e === '弱') return 'text-down'
      return ''
    },
    marketStyleHint() {
      const d = (this.sentiment && this.sentiment.date) || ''
      return d ? ('数据日 ' + d) : ''
    },
    starNote() {
      if (this.starMode === 'industry') {
        return (this.starMap.industry && this.starMap.industry.note) || ''
      }
      return (this.starMap.stockCap && this.starMap.stockCap.note) || ''
    }
  },
  created() {
    this.loadDashboard()
    this.loadExtra()
    this.loadVersions()
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.onChartResize)
    if (this.posGaugeChart) this.posGaugeChart.dispose()
    if (this.starChart) this.starChart.dispose()
  },
  methods: {
    formatSigned(v) {
      const n = Number(v)
      if (!isFinite(n)) return '—'
      return (n > 0 ? '+' : '') + n
    },
    onMarketTabClick() {
      this.$nextTick(() => {
        if (this.marketTab === 'style') this.renderPosGauge()
        if (this.marketTab === 'star') this.renderStarMap()
        this.onChartResize()
      })
    },
    onChartResize() {
      if (this.posGaugeChart) this.posGaugeChart.resize()
      if (this.starChart) this.starChart.resize()
    },
    renderPosGauge() {
      if (!this.$refs.posGauge) return
      if (!this.posGaugeChart) {
        this.posGaugeChart = echarts.init(this.$refs.posGauge)
      }
      const pos = Number(this.marketStyle.suggestedPosition) || 0
      this.posGaugeChart.setOption({
        series: [{
          type: 'gauge',
          startAngle: 180,
          endAngle: 0,
          min: 0,
          max: 100,
          radius: '100%',
          center: ['50%', '70%'],
          axisLine: {
            lineStyle: {
              width: 18,
              color: [[0.35, '#67c23a'], [0.65, '#e6a23c'], [1, '#f56c6c']]
            }
          },
          pointer: { length: '55%', width: 5 },
          axisTick: { show: false },
          splitLine: { length: 12, lineStyle: { width: 2, color: '#999' }},
          axisLabel: { distance: 14, fontSize: 11, color: '#666' },
          detail: {
            valueAnimation: true,
            formatter: '{value}%\n建议仓位',
            fontSize: 16,
            offsetCenter: [0, '18%'],
            color: '#303133'
          },
          data: [{ value: pos }]
        }]
      })
    },
    renderStarMap() {
      if (!this.$refs.starMap) return
      this.starLoading = true
      if (!this.starChart) {
        this.starChart = echarts.init(this.$refs.starMap)
      }
      const pack = this.starMode === 'industry' ? this.starMap.industry : this.starMap.stockCap
      const tree = (pack && pack.tree) || null
      const children = (tree && tree.children) || []
      const data = children.map(c => ({
        name: c.name,
        value: c.value,
        changePercent: c.changePercent,
        code: c.code,
        leader: c.leader,
        itemStyle: { color: changeToColor(c.changePercent) }
      }))
      this.starChart.setOption({
        tooltip: {
          formatter: (info) => {
            const d = info.data || {}
            const ch = d.changePercent
            const chStr = (ch == null || !isFinite(Number(ch))) ? '—' : (((Number(ch) > 0 ? '+' : '') + ch) + '%')
            let extra = ''
            if (d.leader) extra += '<br/>领涨: ' + d.leader
            if (d.code) extra += '<br/>代码: ' + d.code
            return (info.name || '') + '<br/>涨跌幅: ' + chStr + '<br/>面积值: ' + (d.value != null ? d.value : '—') + extra
          }
        },
        series: [{
          type: 'treemap',
          width: '96%',
          height: '90%',
          top: 8,
          bottom: 28,
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          label: {
            show: true,
            formatter: (p) => {
              const ch = p.data && p.data.changePercent
              const chStr = (ch == null || !isFinite(Number(ch))) ? '' : ('\n' + (Number(ch) > 0 ? '+' : '') + ch + '%')
              return p.name + chStr
            },
            fontSize: 11,
            color: '#fff',
            textShadowColor: 'rgba(0,0,0,.45)',
            textShadowBlur: 2
          },
          upperLabel: { show: false },
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 1,
            gapWidth: 1
          },
          data
        }]
      }, true)
      this.starLoading = false
    },
    loadDashboard() {
      // 买入表数据量小，直接取全量后本地按分数排序取 Top20。
      fetchList({ name: 'guess_indicators_lite_buy_daily', page: 1, limit: 500 }).then(res => {
        const rows = res.data || []
        if (rows.length > 0) {
          const maxDate = rows.reduce((m, r) => (r.date > m ? r.date : m), rows[0].date)
          const todays = rows.filter(r => r.date === maxDate)
          this.dataDate = String(maxDate)
          this.buyCount = todays.length
          this.buyTop = todays
            .slice()
            .sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0))
            .slice(0, 20)
          this.loadSellTop(maxDate)
          this.loadLhbTop(maxDate)
          fetchList({ name: 'guess_indicators_daily', page: 1, limit: 1, date: maxDate }).then(r3 => {
            this.indicatorCount = r3.total || 0
          }).catch(() => {})
        } else {
          this.sellLoading = false
          this.lhbLoading = false
        }
        this.loading = false
      }).catch(() => {
        this.loading = false
        this.sellLoading = false
        this.lhbLoading = false
      })
    },
    loadSellTop(date) {
      this.sellLoading = true
      fetchList({ name: 'guess_indicators_lite_sell_daily', page: 1, limit: 500, date }).then(res => {
        const rows = res.data || []
        this.sellCount = res.total != null ? res.total : rows.length
        this.sellTop = rows
          .slice()
          .sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0))
          .slice(0, 20)
        this.sellLoading = false
      }).catch(() => {
        this.sellTop = []
        this.sellLoading = false
      })
    },
    loadLhbTop(date) {
      this.lhbLoading = true
      fetchList({ name: 'stock_lhb_detail_daily', page: 1, limit: 50, date }).then(res => {
        const rows = res.data || []
        this.lhbTop = rows
          .slice()
          .sort((a, b) => (Number(b.net_amount) || 0) - (Number(a.net_amount) || 0))
          .slice(0, 5)
        this.lhbLoading = false
      }).catch(() => {
        this.lhbTop = []
        this.lhbLoading = false
      })
    },
    formatAmount(v) {
      const n = Number(v)
      if (!isFinite(n)) return '—'
      if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + ' 亿'
      if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(0) + ' 万'
      return String(n)
    },
    loadExtra() {
      request({ url: '/api/v1/dashboard_extra', method: 'get', timeout: 30000 }).then(res => {
        this.sentiment = res.sentiment || {}
        this.news = res.news || []
        this.industryFlow = res.industryFlow || []
        this.conceptFlow = res.conceptFlow || []
        this.marketStyle = res.marketStyle || {}
        this.stockVane = res.stockVane || { gainers: [], losers: [] }
        this.starMap = res.starMap || { industry: {}, stockCap: {} }
        this.$nextTick(() => {
          this.renderPosGauge()
          window.addEventListener('resize', this.onChartResize)
        })
      }).catch(() => {})
    },
    flowBarWidth(v, list) {
      const max = Math.max.apply(null, list.map(x => Math.abs(x.netAmount)).concat([1]))
      return Math.round(Math.abs(v) * 100 / max)
    },
    goTable(name) {
      this.$router.push('/stock/table/' + name)
    },
    loadVersions() {
      fetchPackageVersion().then(res => {
        this.versionTags = [
          { name: 'pandas', version: res.pandasVersion },
          { name: 'numpy', version: res.numpyVersion },
          { name: 'sqlalchemy', version: res.sqlalchemyVersion },
          { name: 'akshare', version: res.akshareVersion },
          { name: 'bokeh', version: res.bokehVersion },
          { name: 'stockstats', version: res.stockstatsVersion }
        ]
      })
    },
    splitStrategy(s) {
      return (s || '').split(',').filter(x => x)
    },
    openEastmoney(code) {
      window.open('http://quote.eastmoney.com/' + code + '.html', '_blank')
    },
    goBuyTable() {
      const date = (this.buyTop[0] && this.buyTop[0].date) || (this.sentiment && this.sentiment.date)
      this.$router.push({
        path: '/stock/table/guess_indicators_lite_buy_daily',
        query: date ? { date: String(date) } : {}
      })
    },
    goSellTable() {
      const date = (this.sellTop[0] && this.sellTop[0].date) || (this.sentiment && this.sentiment.date)
      this.$router.push({
        path: '/stock/table/guess_indicators_lite_sell_daily',
        query: date ? { date: String(date) } : {}
      })
    },
    goLhbSeat(code) {
      this.$router.push({ path: '/stock/table/stock_lhb_seat_detail', query: { code } })
    }
  }
}
</script>

<style lang="scss" scoped>
.dashboard-container {
  padding: 24px;
  background: #f5f7fa;
  min-height: calc(100vh - 50px);
}

.stat-row {
  margin-bottom: 4px;
}

.stat-card {
  border-radius: 10px;
  padding: 18px 20px;
  color: #fff;
  margin-bottom: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, .08);

  .stat-title { font-size: 13px; opacity: .9; }
  .stat-value { font-size: 30px; font-weight: 700; margin: 6px 0 2px; }
  .stat-unit  { font-size: 14px; font-weight: 400; margin-left: 4px; opacity: .85; }
  .stat-desc  { font-size: 12px; opacity: .75; }
}
.stat-blue   { background: linear-gradient(135deg, #409eff, #2f74d0); }
.stat-red    { background: linear-gradient(135deg, #f56c6c, #d24a4a); }
.stat-green  { background: linear-gradient(135deg, #67c23a, #4c9a2a); }
.stat-purple { background: linear-gradient(135deg, #9254de, #6e3cbc); }

.panel-card {
  margin-bottom: 20px;
  border-radius: 10px;

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .panel-title { font-size: 15px; font-weight: 600; }
}

.strategy-tag { margin: 0 3px; }

.text-up { color: #f56c6c; font-weight: 600; }
.text-down { color: #67c23a; font-weight: 600; }

.empty-tip {
  text-align: center;
  color: #909399;
  padding: 24px 0;
}

.rule-card {
  p { margin: 10px 0; font-size: 13px; line-height: 1.7; color: #303133; }
  .el-tag { margin-right: 8px; }
  .rule-note { color: #909399; font-size: 12px; margin-left: 4px; }
  .rule-muted { color: #909399; font-size: 12px; }
}

.version-card {
  .version-tag { margin-right: 8px; margin-bottom: 6px; }
  .version-links { margin-left: 12px; .el-link { margin-right: 12px; } }
}

/* 情绪面 */
.sentiment-card {
  .updown-bar {
    display: flex;
    height: 14px;
    border-radius: 7px;
    overflow: hidden;
    margin: 6px 0 8px;

    .bar-up   { background: linear-gradient(90deg, #f56c6c, #fa9191); }
    .bar-down { background: linear-gradient(90deg, #95d475, #67c23a); }
  }
  .updown-label {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    margin-bottom: 14px;
  }
  .senti-stats {
    text-align: center;
    margin-bottom: 14px;

    .senti-num  { font-size: 22px; font-weight: 700; }
    .senti-name { font-size: 12px; color: #909399; margin-top: 2px; }
  }
  .temp-line {
    display: flex;
    align-items: center;

    .temp-progress { flex: 1; margin: 0 10px; }
    .temp-text { font-size: 14px; font-weight: 700; }
  }
}

/* 板块资金流 */
.flow-card {
  .flow-item {
    display: flex;
    align-items: center;
    padding: 7px 2px;
    border-bottom: 1px dashed #ebeef5;
    font-size: 13px;

    &:last-child { border-bottom: none; }
  }
  .flow-rank {
    width: 20px; height: 20px; line-height: 20px;
    text-align: center; border-radius: 4px;
    background: #f0f2f5; color: #909399;
    font-size: 12px; font-weight: 700; flex-shrink: 0;
  }
  .flow-rank-top { background: #fdf6ec; color: #e6a23c; }
  .flow-name { width: 88px; margin-left: 8px; font-weight: 600; color: #303133;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0; }
  .flow-change { width: 58px; text-align: right; font-size: 12px; flex-shrink: 0; }
  .flow-bar-wrap { flex: 1; height: 8px; background: #f0f2f5; border-radius: 4px; margin: 0 8px; overflow: hidden; }
  .flow-bar { height: 100%; border-radius: 4px; background: linear-gradient(90deg, #fa9191, #f56c6c); }
  .flow-amount { width: 76px; text-align: right; font-size: 12px; flex-shrink: 0; }
  .flow-leader { width: 64px; text-align: right; font-size: 12px; flex-shrink: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rule-muted { color: #909399; }
}

/* 消息面 */
.news-card {
  .news-list {
    max-height: 300px;
    overflow-y: auto;
  }
  .news-item {
    padding: 8px 4px;
    border-bottom: 1px dashed #ebeef5;
    font-size: 13px;
    line-height: 1.6;

    &:last-child { border-bottom: none; }
    .news-time { color: #409eff; margin-right: 8px; white-space: nowrap; font-size: 12px; }
    .news-content { color: #303133; }
  }
}

/* 市场风格 / 大盘星图 */
.market-lab-card {
  .gauge-wrap { text-align: center; }
  .gauge-chart { width: 100%; height: 200px; }
  .gauge-caption { font-size: 12px; color: #909399; margin-top: -8px; }

  .effect-box {
    background: #fafafa;
    border-radius: 8px;
    padding: 18px 16px;
    min-height: 180px;
  }
  .effect-label { font-size: 13px; color: #909399; }
  .effect-value { font-size: 36px; font-weight: 700; margin-top: 8px; }

  .updown-bar {
    display: flex;
    height: 12px;
    border-radius: 6px;
    overflow: hidden;
    .bar-up   { background: linear-gradient(90deg, #f56c6c, #fa9191); }
    .bar-down { background: linear-gradient(90deg, #95d475, #67c23a); }
  }
  .updown-label {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
  }

  .tile-title {
    margin: 18px 0 10px;
    font-size: 13px;
    font-weight: 600;
    color: #606266;
  }
  .sector-tiles {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .sector-tile {
    width: calc(16.66% - 8px);
    min-width: 110px;
    border-radius: 6px;
    padding: 10px 8px;
    color: #fff;
    box-sizing: border-box;
  }
  .tile-in { background: linear-gradient(135deg, #e74c3c, #c0392b); }
  .tile-out { background: linear-gradient(135deg, #27ae60, #1e8449); }
  .tile-name { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tile-chg { font-size: 16px; font-weight: 700; margin: 4px 0 2px; }
  .tile-net { font-size: 12px; opacity: .9; }

  .vane-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; }

  .star-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }
  .star-note { font-size: 12px; }
  .star-chart {
    width: 100%;
    height: 520px;
    background: #1a1a1a;
    border-radius: 8px;
  }
  .star-legend {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 8px;
    font-size: 12px;
    color: #909399;
  }
  .leg-bar {
    width: 120px;
    height: 10px;
    border-radius: 4px;
    background: linear-gradient(90deg, #1b5e20, #90a4ae, #b71c1c);
  }
}
</style>
