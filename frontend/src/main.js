import Vue from 'vue'

import 'normalize.css/normalize.css' // A modern alternative to CSS resets

import ElementUI from 'element-ui'
import 'element-ui/lib/theme-chalk/index.css'
import locale from 'element-ui/lib/locale/lang/en' // lang i18n

import '@/styles/index.scss' // global css

import App from './App'
import store from './store'
import router from './router'

import '@/icons' // icon
// import '@/permission' // permission control
// 不进行登录校验。

/**
 * 前端 Mock.js 开关。
 * 生产环境永远不启用 Mock（避免线上返回假数据/绕过后端）。
 * 默认关闭；仅在非生产环境且显式设置 VUE_APP_MOCK=true 时启用。
 * 本地开发默认走 devServer 代理到真实后端，不受影响。
 */
if (process.env.NODE_ENV !== 'production' && process.env.VUE_APP_MOCK === 'true') {
  const { mockXHR } = require('../mock')
  mockXHR()
}

// set ElementUI lang to EN
Vue.use(ElementUI, { locale })
// 如果想要中文版 element-ui，按如下方式声明
// Vue.use(ElementUI)

Vue.config.productionTip = false

new Vue({
  el: '#app',
  router,
  store,
  render: h => h(App)
})
