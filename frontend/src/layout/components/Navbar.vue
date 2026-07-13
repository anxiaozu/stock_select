<template>
  <div class="navbar">
    <div class="nav-left">
      <router-link to="/dashboard" class="brand">
        <img :src="avatarSrc" class="brand-logo" alt="logo">
        <span class="brand-title">{{ appTitle }}</span>
      </router-link>
      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        class="top-menu"
        router
        background-color="transparent"
        text-color="#64748b"
        active-text-color="#0f766e"
      >
        <el-menu-item index="/dashboard">总览</el-menu-item>
        <el-submenu index="tables" popper-class="top-menu-popper">
          <template slot="title">数据表</template>
          <el-menu-item
            v-for="item in tableMenus"
            :key="item.path"
            :index="item.path"
          >{{ item.title }}</el-menu-item>
        </el-submenu>
      </el-menu>
    </div>

    <div class="right-menu">
      <el-dropdown class="avatar-container" trigger="click">
        <div class="avatar-wrapper">
          <img :src="avatarSrc" class="user-avatar" alt="avatar">
          <i class="el-icon-caret-bottom" />
        </div>
        <el-dropdown-menu slot="dropdown" class="user-dropdown">
          <router-link to="/">
            <el-dropdown-item>首页</el-dropdown-item>
          </router-link>
          <a
            v-if="projectUrl"
            target="_blank"
            rel="noopener"
            :href="projectUrl"
          >
            <el-dropdown-item>{{ projectLabel }}</el-dropdown-item>
          </a>
          <el-dropdown-item
            v-if="showLogout"
            divided
            @click.native="logout"
          >
            <span style="display:block;">Log Out</span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </el-dropdown>
    </div>
  </div>
</template>

<script>
import defaultSettings from '@/settings'

const avatarModules = require.context('@/assets', false, /\.(png|jpe?g|gif|svg|webp)$/)

function resolveLocalAvatar(filename) {
  const key = './' + String(filename || '').replace(/^\.\//, '')
  if (avatarModules.keys().indexOf(key) !== -1) {
    return avatarModules(key)
  }
  if (avatarModules.keys().indexOf('./stock-logo.svg') !== -1) {
    return avatarModules('./stock-logo.svg')
  }
  return ''
}

export default {
  name: 'Navbar',
  data() {
    return {
      appTitle: defaultSettings.title || '股票选股系统',
      projectUrl: defaultSettings.projectUrl || '',
      projectLabel: defaultSettings.projectLabel || '我的项目',
      showLogout: !!defaultSettings.showLogout
    }
  },
  computed: {
    avatarSrc() {
      const url = (defaultSettings.brandAvatarUrl || '').trim()
      if (url) return url
      return resolveLocalAvatar(defaultSettings.brandAvatar || 'stock-logo.svg')
    },
    activeMenu() {
      const path = this.$route.path || ''
      if (path.indexOf('/stock/') === 0) return path
      return '/dashboard'
    },
    tableMenus() {
      const menus = []
      const routes = (this.$router && this.$router.options && this.$router.options.routes) || []
      routes.forEach(r => {
        if (!r || r.hidden || !r.children || !r.children.length) return
        const base = r.path === '/' ? '' : r.path
        r.children.forEach(c => {
          if (!c || c.hidden) return
          const childPath = c.path || ''
          // 只收数据表类路由；Dashboard 已在顶栏单独入口
          if (childPath.indexOf('table') === -1 && !(base && base.indexOf('/stock') === 0)) {
            return
          }
          let full = childPath.startsWith('/')
            ? childPath
            : (base.replace(/\/$/, '') + '/' + childPath).replace(/\/+/g, '/')
          // 动态 :tableName 路由用具体子路径时已是完整 path
          if (full.indexOf(':') !== -1) return
          menus.push({
            path: full,
            title: (c.meta && c.meta.title) || c.name || full
          })
        })
      })
      // 去重
      const seen = {}
      return menus.filter(m => {
        if (seen[m.path]) return false
        seen[m.path] = true
        return true
      })
    }
  },
  methods: {
    async logout() {
      await this.$store.dispatch('user/logout')
      this.$router.push(`/login?redirect=${this.$route.fullPath}`)
    }
  }
}
</script>

<style lang="scss" scoped>
.navbar {
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px 0 16px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.03);

  .nav-left {
    display: flex;
    align-items: center;
    min-width: 0;
    flex: 1;
  }

  .brand {
    display: inline-flex;
    align-items: center;
    text-decoration: none;
    margin-right: 18px;
    flex-shrink: 0;
    padding: 4px 8px 4px 4px;
    border-radius: 12px;
    transition: background 0.2s ease;

    &:hover {
      background: rgba(15, 118, 110, 0.06);
    }
  }

  .brand-logo {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    object-fit: contain;
    background: #fff;
    padding: 2px;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.1);
  }

  .brand-title {
    margin-left: 10px;
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: 0.01em;
    white-space: nowrap;
  }

  .top-menu {
    border-bottom: none !important;
    flex: 1;
    min-width: 0;
    background: transparent !important;

    ::v-deep .el-menu-item,
    ::v-deep .el-submenu__title {
      height: 58px;
      line-height: 58px;
      font-weight: 500;
      color: #64748b !important;
      border-bottom: 2px solid transparent !important;
      transition: color 0.2s ease;
    }

    ::v-deep .el-menu-item:hover,
    ::v-deep .el-submenu__title:hover {
      color: #0f766e !important;
      background: transparent !important;
    }

    ::v-deep .el-menu-item.is-active,
    ::v-deep .el-submenu.is-active .el-submenu__title {
      color: #0f766e !important;
      border-bottom-color: #0f766e !important;
      background: transparent !important;
      font-weight: 600;
    }
  }

  .right-menu {
    flex-shrink: 0;
    height: 100%;
    display: flex;
    align-items: center;

    .avatar-container {
      .avatar-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        cursor: pointer;
        padding: 4px 6px;
        border-radius: 12px;
        transition: background 0.2s ease;

        &:hover {
          background: rgba(15, 118, 110, 0.06);
        }

        .user-avatar {
          width: 34px;
          height: 34px;
          border-radius: 10px;
          object-fit: contain;
          background: #fff;
          padding: 2px;
          border: 1px solid #e2e8f0;
        }

        .el-icon-caret-bottom {
          margin-left: 6px;
          font-size: 12px;
          color: #94a3b8;
        }
      }
    }
  }
}
</style>
