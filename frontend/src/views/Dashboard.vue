<template>
  <div>
    <h2>仪表盘</h2>
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6">
        <el-card>
          <el-statistic title="项目总数" :value="stats.projects">
            <template #suffix>
              <el-icon><Files /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card>
          <el-statistic title="运行中任务" :value="stats.runningTasks">
            <template #suffix>
              <el-icon><VideoPlay /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card>
          <el-statistic title="今日任务" :value="stats.todayTasks">
            <template #suffix>
              <el-icon><Document /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card>
          <el-statistic title="成功率" :value="stats.successRate" suffix="%">
            <template #prefix>
              <el-icon><SuccessFilled /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card style="margin-top: 20px">
      <template #header>
        <h3>欢迎使用 CrawloPilot</h3>
      </template>
      <p>CrawloPilot 是 Crawlo 爬虫框架的配套管理部署平台。</p>
      <p>当前版本：v1.0.0</p>
      <el-divider />
      <h4>快速开始</h4>
      <ul>
        <li>创建您的第一个爬虫项目</li>
        <li>配置任务调度</li>
        <li>监控运行状态</li>
        <li>查看数据统计</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const stats = ref({
  projects: 0,
  runningTasks: 0,
  todayTasks: 0,
  successRate: 0
})
</script>
