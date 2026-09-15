/**
 * BaseChart 组件测试: 验证 ECharts 初始化 / 数据版本更新 / 卸载销毁 / 空态展示。
 * 通过 mock echarts/core 保持测试快速且不依赖 Canvas。
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

const { chartInstances, setOptionSpy, disposeSpy, initSpy } = vi.hoisted(() => {
  const instances: Array<Record<string, unknown>> = []
  const setOption = vi.fn()
  const dispose = vi.fn()
  const init = vi.fn(() => {
    const instance = { setOption, dispose, resize: vi.fn(), on: vi.fn() }
    instances.push(instance)
    return instance
  })
  return { chartInstances: instances, setOptionSpy: setOption, disposeSpy: dispose, initSpy: init }
})

vi.mock('echarts/core', () => {
  return {
    init: initSpy,
    use: vi.fn(),
    registerTheme: vi.fn(),
  }
})

vi.mock('echarts/charts', () => ({ BarChart: {}, LineChart: {}, PieChart: {} }))
vi.mock('echarts/components', () => ({
  DatasetComponent: {},
  GridComponent: {},
  LegendComponent: {},
  TitleComponent: {},
  TooltipComponent: {},
}))
vi.mock('echarts/features', () => ({ LabelLayout: {}, UniversalTransition: {} }))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

import BaseChart from '@/components/charts/BaseChart.vue'

class ResizeObserverStub {
  observe(): void {}
  disconnect(): void {}
  unobserve(): void {}
}

function optionWith(points: number[]): { series: Array<{ type: string; data: number[] }> } {
  return { series: [{ type: 'line', data: points }] }
}

describe('BaseChart', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    chartInstances.length = 0
    setOptionSpy.mockClear()
    disposeSpy.mockClear()
    initSpy.mockClear()
    vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  })

  it('挂载时初始化实例并按 optionFactory 设置配置', () => {
    const wrapper = mount(BaseChart, {
      props: { optionFactory: () => optionWith([1, 2, 3]), dataVersion: 0 },
    })

    expect(initSpy).toHaveBeenCalledTimes(1)
    expect(setOptionSpy).toHaveBeenCalledTimes(1)
    expect(setOptionSpy.mock.calls[0]?.[0]).toEqual(optionWith([1, 2, 3]))
    // 渲染出画布容器
    expect(wrapper.find('.base-chart__canvas').exists()).toBe(true)
    wrapper.unmount()
  })

  it('dataVersion 变化时重新应用配置', async () => {
    let data = [1, 2, 3]
    const wrapper = mount(BaseChart, {
      props: { optionFactory: () => optionWith(data), dataVersion: 0 },
    })
    expect(setOptionSpy).toHaveBeenCalledTimes(1)

    data = [4, 5, 6, 7]
    await wrapper.setProps({ dataVersion: 1 })

    expect(setOptionSpy).toHaveBeenCalledTimes(2)
    expect(setOptionSpy.mock.calls[1]?.[0]).toEqual(optionWith([4, 5, 6, 7]))
    wrapper.unmount()
  })

  it('卸载时销毁实例', () => {
    const wrapper = mount(BaseChart, { props: { optionFactory: () => optionWith([1]) } })
    wrapper.unmount()
    expect(disposeSpy).toHaveBeenCalledTimes(1)
  })

  it('数据为空时展示空状态', async () => {
    const wrapper = mount(BaseChart, {
      props: { optionFactory: () => optionWith([]), emptyText: '暂无趋势数据' },
    })
    await nextTick()
    expect(wrapper.find('.base-chart__empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无趋势数据')
    wrapper.unmount()
  })

  it('loading 为 true 时不展示空状态遮罩', () => {
    const wrapper = mount(BaseChart, {
      props: { optionFactory: () => optionWith([]), loading: true },
    })
    expect(wrapper.find('.base-chart__empty').exists()).toBe(false)
    expect(wrapper.find('.base-chart__loading').exists()).toBe(true)
    wrapper.unmount()
  })

  it('以 CSS 变量字符串作为高度', () => {
    const wrapper = mount(BaseChart, {
      props: { optionFactory: () => optionWith([1]), height: '420px' },
    })
    expect(wrapper.attributes('style')).toContain('420px')
    wrapper.unmount()
  })
})
