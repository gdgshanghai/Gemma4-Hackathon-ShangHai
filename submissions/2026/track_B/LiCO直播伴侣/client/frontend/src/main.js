import Vue from 'vue'
import VueRouter from 'vue-router'
import ElementUI from 'element-ui'
if (!process.env.LIB_USE_CDN) {
  import('element-ui/lib/theme-chalk/index.css')
}

import * as apiBase from './api/base'
import * as i18n from './i18n'
import App from './App'
import NotFound from './views/NotFound'

apiBase.init()

if (!process.env.LIB_USE_CDN) {
  Vue.use(VueRouter)
  Vue.use(ElementUI)
}

Vue.config.ignoredElements = [
  /^yt-/
]

const router = new VueRouter({
  mode: 'history',
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('./views/Home')
    },
    {
      path: '/review/:roomId/:streamStartFolder',
      name: 'live_review_detail',
      component: () => import('./views/LiveReviewDetail'),
      props: true
    },
    {
      path: '/others',
      component: () => import('./layout'),
      children: [
        { path: '/stylegen', name: 'stylegen', component: () => import('./views/StyleGenerator') },
        { path: '/help', name: 'help', component: () => import('./views/Help') },
        { path: '/plugins', name: 'plugins', component: () => import('./views/Plugins') },
        { path: '/qwen', name: 'qwen', component: () => import('./views/QwenChat') },
        { path: '/psych', name: 'psych', component: () => import('./views/PsychState') },
      ]
    },
    {
      path: '/qwen/callback',
      name: 'qwen_callback',
      component: () => import('./views/QwenCallback')
    },
    {
      path: '/qwen/popup',
      name: 'qwen_popup',
      component: () => import('./views/QwenChatPopup')
    },
    {
      path: '/room/test',
      name: 'test_room',
      component: () => import('./views/Room'),
      props: route => ({ strConfig: route.query })
    },
    {
      path: '/room/:roomKeyValue',
      name: 'room',
      component: () => import('./views/Room'),
      props(route) {
        let roomKeyType = parseInt(route.query.roomKeyType) || 1
        if (roomKeyType < 1 || roomKeyType > 2) {
          roomKeyType = 1
        }

        let roomKeyValue = route.params.roomKeyValue
        if (roomKeyType === 1) {
          roomKeyValue = parseInt(roomKeyValue) || null
        } else {
          roomKeyValue = roomKeyValue || null
        }
        return { roomKeyType, roomKeyValue, strConfig: route.query }
      }
    },
    { path: '*', component: NotFound }
  ]
})

new Vue({
  render: h => h(App),
  router,
  i18n: i18n.i18n
}).$mount('#app')
