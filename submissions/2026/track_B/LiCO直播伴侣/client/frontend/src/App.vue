<template>
  <div id="app">
    <router-view></router-view>
  </div>
</template>

<script>
export default {
  name: 'app'
}
</script>

<style>
html {
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "\5FAE \8F6F \96C5 \9ED1 ", "微软雅黑", Arial, sans-serif;
}

html, body, #app {
  height: 100%;
}

body {
  margin: 0;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  background-attachment: fixed;
}

/* 全局覆盖 Element UI */
.el-button--primary {
  background-color: #7964e6 !important;
  border-color: #7964e6 !important;
}

.el-tabs--border-card > .el-tabs__header .el-tabs__item.is-active {
  color: #7964e6 !important;
}

.el-switch.is-checked .el-switch__core {
  background-color: #7964e6 !important;
  border-color: #7964e6 !important;
}
</style>
