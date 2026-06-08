<template>
  <div class="clip-timeline-chart">
    <div v-show="hasData" ref="chartRef" class="clip-timeline-chart-canvas"></div>
    <el-empty v-if="!hasData" :description="emptyText"></el-empty>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import { formatStreamDuration } from '@/utils/liveArchive'

const THEME_PRESETS = {
  blue: {
    pointColor: '#0ea5e9',
    lineGradient: [
      { offset: 0, color: '#3b82f6' },
      { offset: 1, color: '#2dd4bf' }
    ],
    areaGradient: [
      { offset: 0, color: 'rgba(45, 212, 191, 0.3)' },
      { offset: 1, color: 'rgba(59, 130, 246, 0)' }
    ],
    shadowColor: 'rgba(45, 212, 191, 0.4)'
  },
  gold: {
    pointColor: '#fbbf24',
    lineGradient: [
      { offset: 0, color: '#f59e0b' },
      { offset: 1, color: '#ffd633' }
    ],
    areaGradient: [
      { offset: 0, color: 'rgba(255, 214, 51, 0.32)' },
      { offset: 1, color: 'rgba(245, 158, 11, 0)' }
    ],
    shadowColor: 'rgba(255, 214, 51, 0.45)'
  }
}

function formatAxisTime(seconds) {
  let total = Math.max(0, Math.floor(Number(seconds) || 0))
  let hours = Math.floor(total / 3600)
  let minutes = Math.floor((total % 3600) / 60)
  let secs = total % 60
  let pad = n => String(n).padStart(2, '0')
  if (hours > 0) {
    return `${hours}:${pad(minutes)}:${pad(secs)}`
  }
  return `${minutes}:${pad(secs)}`
}

export default {
  name: 'ClipTimelineChart',
  props: {
    points: {
      type: Array,
      default: () => []
    },
    xMax: {
      type: Number,
      default: 0
    },
    valueKey: {
      type: String,
      required: true
    },
    title: {
      type: String,
      default: ''
    },
    theme: {
      type: String,
      default: 'blue'
    },
    seriesName: {
      type: String,
      default: ''
    },
    emptyText: {
      type: String,
      default: ''
    },
    yValueFormatter: {
      type: Function,
      default: null
    },
    highlightRange: {
      type: Object,
      default: null
    }
  },
  data() {
    return {
      chart: null,
      resizeObserver: null
    }
  },
  computed: {
    normalizedPoints() {
      return (this.points || [])
        .map(item => ({
          x: Number(item.timeSeconds) || 0,
          y: Number(item[this.valueKey]) || 0
        }))
        .filter(item => item.x >= 0)
        .sort((a, b) => a.x - b.x)
    },
    hasData() {
      return this.normalizedPoints.length > 0 && this.xMax > 0
    },
    themePreset() {
      return THEME_PRESETS[this.theme] || THEME_PRESETS.blue
    }
  },
  watch: {
    points: {
      deep: true,
      handler() {
        this.renderChart()
      }
    },
    xMax() {
      this.renderChart()
    },
    theme() {
      this.renderChart()
    },
    title() {
      this.renderChart()
    },
    highlightRange: {
      deep: true,
      handler() {
        this.renderChart()
      }
    },
    hasData(value) {
      if (value) {
        this.$nextTick(() => {
          this.initChart()
          this.renderChart()
        })
      } else {
        this.disposeChart()
      }
    }
  },
  mounted() {
    if (this.hasData) {
      this.initChart()
      this.renderChart()
    }
    this.bindResize()
  },
  beforeDestroy() {
    this.unbindResize()
    this.disposeChart()
  },
  methods: {
    formatYValue(value) {
      if (typeof this.yValueFormatter === 'function') {
        return this.yValueFormatter(value)
      }
      return String(Math.round(value))
    },
    buildMarkArea() {
      if (!this.highlightRange) {
        return undefined
      }
      let start = Number(this.highlightRange.startSeconds)
      let end = Number(this.highlightRange.endSeconds)
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
        return undefined
      }
      return {
        silent: true,
        itemStyle: {
          color: 'rgba(244, 63, 94, 0.16)',
          borderColor: 'rgba(244, 63, 94, 0.55)',
          borderWidth: 1
        },
        data: [[{ xAxis: start }, { xAxis: end }]]
      }
    },
    buildOption() {
      let preset = this.themePreset
      let seriesData = this.normalizedPoints.map(point => [point.x, point.y])
      let seriesLabel = this.seriesName || this.title || 'Value'

      return {
        backgroundColor: 'transparent',
        title: {
          text: this.title,
          textStyle: {
            color: '#e2e8f0',
            fontSize: 15,
            fontWeight: 'normal'
          },
          left: 8,
          top: 4
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross',
            label: {
              backgroundColor: '#475569'
            }
          },
          backgroundColor: 'rgba(15, 23, 42, 0.92)',
          borderColor: 'rgba(148, 163, 184, 0.25)',
          textStyle: {
            color: '#e2e8f0'
          },
          formatter: params => {
            let item = params && params[0]
            if (!item) {
              return ''
            }
            let timeText = formatStreamDuration(item.value[0])
            let valueText = this.formatYValue(item.value[1])
            return `${timeText}<br/>${seriesLabel}: ${valueText}`
          }
        },
        grid: {
          left: 12,
          right: 20,
          top: this.title ? 48 : 28,
          bottom: 12,
          containLabel: true
        },
        xAxis: {
          type: 'value',
          min: 0,
          max: this.xMax,
          boundaryGap: false,
          axisLabel: {
            color: '#94a3b8',
            formatter: value => formatAxisTime(value)
          },
          axisLine: {
            lineStyle: {
              color: '#334155'
            }
          },
          splitLine: {
            show: false
          }
        },
        yAxis: {
          type: 'value',
          min: 0,
          axisLabel: {
            color: '#94a3b8',
            formatter: value => this.formatYValue(value)
          },
          axisLine: {
            show: false
          },
          splitLine: {
            lineStyle: {
              color: '#1e293b',
              type: 'dashed'
            }
          }
        },
        series: [
          {
            name: seriesLabel,
            type: 'line',
            smooth: true,
            symbol: 'circle',
            symbolSize: 8,
            showSymbol: this.normalizedPoints.length <= 24,
            itemStyle: {
              color: preset.pointColor,
              borderColor: '#fff',
              borderWidth: 2,
              shadowColor: preset.shadowColor,
              shadowBlur: 10
            },
            lineStyle: {
              width: 3,
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, preset.lineGradient),
              shadowColor: preset.shadowColor,
              shadowBlur: 10,
              shadowOffsetY: 5
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, preset.areaGradient)
            },
            data: seriesData,
            markArea: this.buildMarkArea(),
            markPoint: {
              symbol: 'pin',
              symbolSize: 48,
              data: [{ type: 'max', name: 'Max' }],
              itemStyle: {
                color: '#f43f5e'
              },
              label: {
                color: '#fff',
                fontSize: 11
              }
            }
          }
        ]
      }
    },
    initChart() {
      if (this.chart || !this.$refs.chartRef) {
        return
      }
      this.chart = echarts.init(this.$refs.chartRef)
      this.setupResizeObserver()
    },
    renderChart() {
      if (!this.hasData) {
        return
      }
      this.$nextTick(() => {
        this.initChart()
        if (!this.chart) {
          return
        }
        this.chart.setOption(this.buildOption(), true)
        this.chart.resize()
      })
    },
    handleResize() {
      if (this.chart) {
        this.chart.resize()
      }
    },
    bindResize() {
      this.handleResizeRef = this.handleResize.bind(this)
      window.addEventListener('resize', this.handleResizeRef)
    },
    setupResizeObserver() {
      if (this.resizeObserver || typeof ResizeObserver === 'undefined' || !this.$refs.chartRef) {
        return
      }
      this.resizeObserver = new ResizeObserver(() => {
        this.handleResize()
      })
      this.resizeObserver.observe(this.$refs.chartRef)
    },
    unbindResize() {
      if (this.handleResizeRef) {
        window.removeEventListener('resize', this.handleResizeRef)
      }
      if (this.resizeObserver) {
        this.resizeObserver.disconnect()
        this.resizeObserver = null
      }
    },
    disposeChart() {
      if (this.chart) {
        this.chart.dispose()
        this.chart = null
      }
    }
  }
}
</script>

<style scoped>
.clip-timeline-chart {
  width: 100%;
  padding: 12px 8px 4px;
  border-radius: 12px;
  background-color: #0f172a;
  box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.06);
}

.clip-timeline-chart-canvas {
  width: 100%;
  height: 400px;
}
</style>
