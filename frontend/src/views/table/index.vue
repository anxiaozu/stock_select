<template>
  <div class="app-container">

    <div class="filter-container">
      <el-date-picker
        v-model="queryDate" type="date" format="yyyyMMdd"
        value-format="yyyyMMdd"
        placeholder="选择日期"
        class="filter-item"
      />
      <el-input v-model="queryCode" placeholder="代码，如 600519" clearable
        prefix-icon="el-icon-coin"
        style="width: 180px;" class="filter-item" @keyup.enter.native="handleFilter" />
      <el-input v-model="queryName" placeholder="名称，如 茅台" clearable
        prefix-icon="el-icon-user"
        style="width: 180px;" class="filter-item" @keyup.enter.native="handleFilter" />

      <el-button v-waves class="filter-item filter-search-btn" type="primary" icon="el-icon-search" @click="handleFilter">
        搜索
      </el-button>

      <span v-if="isLhbSeatTable" class="filter-item seat-filter">
        <el-switch
          v-model="onlyBrokerSeat"
          active-text="仅营业部"
          inactive-text="全部席位"
          @change="applySeatFilter"
        />
        <span v-if="onlyBrokerSeat && seatFilteredCount > 0" class="seat-filter-tip">
          已隐藏 {{ seatFilteredCount }} 条非营业部
        </span>
      </span>
    </div>

    <el-table :key="tableKey" v-loading="listLoading" :data="list"
      stripe border fit fixed highlight-current-row style="width: 100%;"
    >
      <el-table-column
        v-for="column in tableColumns"
        :key="column.column"
        :label="column.columnName"
        :prop="column.column"
        align="center"
        width="120"
        sortable
      >
        <template slot-scope="{row}">
          <span v-if="isChangeColumn(column.column)" :class="changeClass(row[column.column])">
            {{ formatChange(row[column.column]) }}
          </span>
          <span v-else-if="isNetAmountColumn(column.column)" :class="changeClass(row[column.column])">
            {{ row[column.column] }}
          </span>
          <span v-else>{{ row[column.column] }}</span>
        </template>
      </el-table-column>

      <el-table-column fixed="right" label="操作" align="center" :width="actionColWidth" class-name="small-padding fixed-width">
        <template slot-scope="{row,$index}">
          <el-button type="primary" size="mini" @click="handleView(row,$index)">
            查看
          </el-button>
          <el-button
            v-if="isLhbDetailTable"
            type="warning"
            size="mini"
            plain
            @click="goSeatDetail(row)"
          >
            席位
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total>0" :total="total"
      :page-sizes="[10, 20, 50, 100, 200, 300]"
      :page.sync="listQuery.page" :limit.sync="listQuery.limit"
      @pagination="getList"/>
  </div>
</template>

<script>
import { fetchList } from '@/api/article'
import waves from '@/directive/waves'
import Pagination from '@/components/Pagination'

const SCORE_SORT_TABLES = [
  'guess_indicators_lite_buy_daily',
  'guess_indicators_lite_sell_daily'
]

const NON_BROKER_DEPTS = ['自然人', '其他自然人', '中小投资者', '机构']

const CHANGE_COLUMNS = [
  'change_percent',
  'quote_change',
  'change_amount',
  'ups_downs',
  'rise_speed',
  'change_5min',
  'change_ercent_60day',
  'ytd_change_percent',
  'leader_change_percent'
]

export default {
  name: 'ComplexTable',
  components: { Pagination },
  directives: { waves },
  data() {
    return {
      tableKey: 0,
      list: [],
      rawList: [],
      tableColumns: [],
      total: 0,
      listLoading: true,
      listQuery: {
        page: 1,
        limit: 10,
        importance: undefined,
        date: undefined,
        code: undefined,
        stock_name: undefined,
        name: '',
        sort: '+id'
      },
      dialogFormVisible: false,
      queryDate: '',
      queryCode: '',
      queryName: '',
      onlyBrokerSeat: true,
      seatFilteredCount: 0
    }
  },
  computed: {
    tableName() {
      return (this.$route.path || '').replace('/stock/table/', '')
    },
    isLhbDetailTable() {
      return this.tableName === 'stock_lhb_detail_daily'
    },
    isLhbSeatTable() {
      return this.tableName === 'stock_lhb_seat_detail'
    },
    actionColWidth() {
      return this.isLhbDetailTable ? 200 : 120
    }
  },
  watch: {
    '$route'(to, from) {
      if (!from || to.fullPath !== from.fullPath) {
        this.resetForTable()
        this.applyRouteQuery()
        this.applyDefaultSort()
        this.listQuery.page = 1
        this.getList()
      }
    }
  },
  created() {
    this.applyRouteQuery()
    this.applyDefaultSort()
    this.getList()
  },
  methods: {
    resetForTable() {
      this.queryDate = ''
      this.queryName = ''
      this.onlyBrokerSeat = true
      this.seatFilteredCount = 0
      this.rawList = []
      this.list = []
      this.tableColumns = []
      this.total = 0
      this.listQuery.date = undefined
      this.listQuery.stock_name = undefined
      // queryCode 由 applyRouteQuery 再填；换表时先清空再按 query 写入
      this.queryCode = ''
      this.listQuery.code = undefined
    },
    applyRouteQuery() {
      const q = this.$route.query || {}
      if (q.code) {
        this.queryCode = String(q.code)
        this.listQuery.code = this.queryCode
      }
      if (q.date) {
        this.queryDate = String(q.date)
        this.listQuery.date = this.queryDate
      }
    },
    applyDefaultSort() {
      if (SCORE_SORT_TABLES.indexOf(this.tableName) !== -1) {
        this.listQuery.sort = '-score'
      } else {
        this.listQuery.sort = '+id'
      }
    },
    getList() {
      const table_name = this.tableName
      if (table_name === ':tableName' || !table_name) {
        this.list = []
        this.total = 0
        this.listLoading = false
        return
      }
      this.listQuery.name = table_name
      this.listQuery.date = this.queryDate || undefined
      this.listQuery.code = this.queryCode
      this.listQuery.stock_name = this.queryName
      this.applyDefaultSort()
      this.listLoading = true
      fetchList(this.listQuery).then(response => {
        this.rawList = response.data || []
        this.tableColumns = response.tableColumns || []
        this.total = response.total || 0
        // 买卖推荐表后端会默认最新日；把日期回填到选择器，避免误以为是全表。
        if (!this.queryDate && response.date && SCORE_SORT_TABLES.indexOf(table_name) !== -1) {
          this.queryDate = String(response.date)
          this.listQuery.date = this.queryDate
        }
        this.applySeatFilter()
        this.listLoading = false
      }).catch(() => {
        this.rawList = []
        this.list = []
        this.total = 0
        this.listLoading = false
      })
    },
    applySeatFilter() {
      if (!this.isLhbSeatTable || !this.onlyBrokerSeat) {
        this.list = this.rawList.slice()
        this.seatFilteredCount = 0
        return
      }
      const filtered = []
      let hidden = 0
      this.rawList.forEach(row => {
        const name = String(row.dept_name || '').trim()
        if (NON_BROKER_DEPTS.indexOf(name) !== -1) {
          hidden += 1
        } else {
          filtered.push(row)
        }
      })
      this.list = filtered
      this.seatFilteredCount = hidden
    },
    isChangeColumn(col) {
      return CHANGE_COLUMNS.indexOf(col) !== -1
    },
    isNetAmountColumn(col) {
      return col === 'net_amount' || col === 'net_ratio'
    },
    changeClass(val) {
      const n = Number(val)
      if (!isFinite(n) || n === 0) return ''
      return n > 0 ? 'text-up' : 'text-down'
    },
    formatChange(val) {
      if (val === null || val === undefined || val === '') return ''
      const n = Number(val)
      if (!isFinite(n)) return val
      return (n > 0 ? '+' : '') + n
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleView(row) {
      const url = 'http://quote.eastmoney.com/' + row['code'] + '.html'
      window.open(url, '_blank')
    },
    goSeatDetail(row) {
      this.$router.push({
        path: '/stock/table/stock_lhb_seat_detail',
        query: { code: row.code }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  padding: 16px 20px 24px;
  background: #f3f6fa;
  min-height: calc(100vh - 56px);
}

.filter-container {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
  background: #fff;
  border: 1px solid #e8edf3;
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);

  .filter-item {
    margin: 0;
  }

  .filter-search-btn {
    border-radius: 8px;
    padding: 10px 18px;
  }

  .seat-filter {
    margin-left: 4px;
    display: inline-flex;
    align-items: center;
  }
  .seat-filter-tip {
    margin-left: 10px;
    color: #909399;
    font-size: 12px;
  }
}

::v-deep .el-table {
  border-radius: 10px;
  overflow: hidden;
}

.text-up { color: #f56c6c; font-weight: 600; }
.text-down { color: #67c23a; font-weight: 600; }
</style>
