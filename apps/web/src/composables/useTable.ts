/**
 * 列表页通用逻辑: 分页 + 加载状态 + 查询条件 + 排序。
 *
 * 用法:
 *   const { rows, total, loading, query, load, search, reset } = useTable(fetchFn)
 */

import { reactive, ref, type Ref } from 'vue'

import type { Paginated } from '@/types/common'

/** 查询条件 (额外筛选项以泛型叠加) */
export interface TableQuery<F extends object = Record<string, never>> {
  page: number
  page_size: number
  sort_by?: string
  filters: F
}

export interface UseTableOptions<F extends object> {
  /** 初始每页条数 */
  pageSize?: number
  /** 默认排序 (前缀 - 表示倒序) */
  sortBy?: string
  /** 初始筛选条件 */
  filters?: F
}

export interface UseTableResult<Row, F extends object> {
  rows: Ref<Row[]>
  total: Ref<number>
  loading: Ref<boolean>
  query: TableQuery<F>
  load: () => Promise<void>
  search: () => Promise<void>
  reset: () => Promise<void>
  changePage: (page: number) => Promise<void>
  changePageSize: (size: number) => Promise<void>
  changeSort: (sortBy: string) => Promise<void>
}

export function useTable<Row, F extends object = Record<string, never>>(
  fetcher: (query: TableQuery<F>) => Promise<Paginated<Row>>,
  options: UseTableOptions<F> = {},
): UseTableResult<Row, F> {
  const rows = ref<Row[]>([]) as Ref<Row[]>
  const total = ref(0)
  const loading = ref(false)

  const initialFilters = { ...(options.filters ?? ({} as F)) }
  const query = reactive<TableQuery<F>>({
    page: 1,
    page_size: options.pageSize ?? 10,
    sort_by: options.sortBy,
    filters: { ...initialFilters },
  }) as TableQuery<F>

  /** 拉取数据 */
  async function load(): Promise<void> {
    loading.value = true
    try {
      const result = await fetcher({
        page: query.page,
        page_size: query.page_size,
        sort_by: query.sort_by,
        filters: { ...query.filters },
      })
      rows.value = result.items ?? []
      total.value = result.meta?.total ?? 0
    } finally {
      loading.value = false
    }
  }

  /** 条件变化后从第一页重新查询 */
  async function search(): Promise<void> {
    query.page = 1
    await load()
  }

  /** 重置筛选条件与分页 */
  async function reset(): Promise<void> {
    query.page = 1
    query.page_size = options.pageSize ?? 10
    query.sort_by = options.sortBy
    query.filters = { ...initialFilters }
    await load()
  }

  async function changePage(page: number): Promise<void> {
    query.page = page
    await load()
  }

  async function changePageSize(size: number): Promise<void> {
    query.page_size = size
    query.page = 1
    await load()
  }

  async function changeSort(sortBy: string): Promise<void> {
    query.sort_by = sortBy
    query.page = 1
    await load()
  }

  return {
    rows,
    total,
    loading,
    query,
    load,
    search,
    reset,
    changePage,
    changePageSize,
    changeSort,
  }
}
