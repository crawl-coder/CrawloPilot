/**
 * ECharts composable
 * 自动处理实例创建、resize 监听和销毁
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

export function useEcharts(containerRef, option, deps = []) {
  let chart = null

  const init = () => {
    if (!containerRef.value) return
    chart = echarts.init(containerRef.value)
    chart.setOption(option)
  }

  const handleResize = () => {
    chart?.resize()
  }

  onMounted(() => {
    init()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    chart?.dispose()
    chart = null
  })

  // 监听数据变化更新图表
  if (deps.length > 0) {
    watch(deps, () => {
      chart?.setOption(option)
    }, { deep: true })
  }

  return chart
}
