import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import App from './App.vue'
import router from './router'

const app = createApp(App)

// 按需注册图标（各组件通过 import 引入，无需全局注册全部 200+ 图标）
// 常用图标可以在这里按需注册
import {
  Plus, Refresh, Document, VideoPlay, Edit, Delete,
  ArrowDown, More, Back, Upload, SuccessFilled, Warning,
  CircleClose, CircleCheck, Folder, Monitor, Connection,
  Service, Timer, Clock, List, TrendCharts, Bell,
  User, Aim, Link, UploadFilled, Grid, DataLine,
  Rank, Loading, MoreFilled, Odometer, CircleCloseFilled,
  Files
} from '@element-plus/icons-vue'

const icons = {
  Plus, Refresh, Document, VideoPlay, Edit, Delete,
  ArrowDown, More, Back, Upload, SuccessFilled, Warning,
  CircleClose, CircleCheck, Folder, Monitor, Connection,
  Service, Timer, Clock, List, TrendCharts, Bell,
  User, Aim, Link, UploadFilled, Grid, DataLine,
  Rank, Loading, MoreFilled, Odometer, CircleCloseFilled,
  Files
}
for (const [key, component] of Object.entries(icons)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
