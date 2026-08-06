import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { ElMessage } from 'element-plus'
import App from './App.vue'
import router from './router'
import './styles/tokens.css'

const app = createApp(App)

// 全局错误边界：捕获组件渲染/事件处理中的未处理异常
app.config.errorHandler = (err, instance, info) => {
  console.error('[GlobalError]', err, info)
  ElMessage.error(err?.message || '页面发生异常，请稍后重试')
}

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
