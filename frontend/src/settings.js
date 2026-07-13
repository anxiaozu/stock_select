module.exports = {

  title: '股票选股系统',

  /**
   * 左侧导航栏：设为 true 则隐藏（界面更干净，导航改到顶部）
   */
  hideSidebar: true,

  /**
   * 顶栏头像 / Logo 图片（二选一）：
   * 1) brandAvatarUrl：填网络图片地址，例如 'https://xxx.com/me.png'
   * 2) brandAvatar：本地文件名，把图片放到 frontend/src/assets/ 下后改这里
   *    例如放了 my-avatar.png，则写 'my-avatar.png'
   * 优先使用 brandAvatarUrl；都空则用默认 stock-logo.svg
   */
  brandAvatarUrl: '',
  brandAvatar: 'stock-logo.svg',

  /**
   * 右上角下拉「我的项目」链接。换成你自己的 GitHub / 主页即可。
   * 不想显示该项：把 projectUrl 留空字符串 ''
   */
  projectUrl: 'https://github.com/anxiaozu/stock_select',
  projectLabel: '我的 GitHub',

  /** 是否显示 Log Out（本地自用不需要可 false） */
  showLogout: false,

  /**
   * @type {boolean} true | false
   * @description Whether fix the header
   */
  fixedHeader: true,

  /**
   * @type {boolean} true | false
   * @description Whether show the logo in sidebar
   */
  sidebarLogo: true
}
