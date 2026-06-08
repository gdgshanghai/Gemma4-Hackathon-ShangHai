<template>
  <el-container class="app-wrapper">
    <obs-live-status-bar variant="bar" />
    <el-main>
      <keep-alive>
        <router-view></router-view>
      </keep-alive>
    </el-main>
  </el-container>
</template>

<script>
import ObsLiveStatusBar from '@/components/ObsLiveStatusBar'

export default {
  name: 'Layout',
  components: {
    ObsLiveStatusBar
  }
}
</script>

<style scoped>
.app-wrapper {
  height: 100%;
  width: 100%;
  flex-direction: column;
}

.el-main {
  padding: 0;
  height: 100%;
}
</style>
