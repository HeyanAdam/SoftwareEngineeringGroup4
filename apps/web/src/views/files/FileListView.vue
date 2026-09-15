<script setup lang="ts">
/**
 * 文件管理: 上传 (服务端中转 / 前端直传) + 列表 + 分类筛选 + 预签名下载 + 删除
 */

import { computed, onMounted, ref } from 'vue'
import {
  ElButton,
  ElIcon,
  ElMessage,
  ElOption,
  ElPagination,
  ElPopconfirm,
  ElProgress,
  ElRadioButton,
  ElRadioGroup,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
  ElUpload,
  type UploadRequestOptions,
} from 'element-plus'
import { Delete, Download, Refresh, Search, UploadFilled } from '@element-plus/icons-vue'

import PageContainer from '@/components/common/PageContainer.vue'
import SearchToolbar from '@/components/common/SearchToolbar.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import {
  deleteFile,
  getDownloadUrl,
  getFileStats,
  listFiles,
  uploadFile,
  uploadFileByPresign,
} from '@/api/file'
import { useTable } from '@/composables/useTable'
import { useAuthStore } from '@/stores/auth'
import { formatBytes, formatDateTime, truncate } from '@/utils/format'
import type { FileCategoryOption, FileItem, FileStats } from '@/types/file'

interface FileFilters {
  keyword: string
  category: string
  only_mine: boolean
}

/** 文件分类 (后端为自由字符串, 此处给出常用枚举) */
const CATEGORIES: FileCategoryOption[] = [
  { value: 'attachment', label: '附件' },
  { value: 'image', label: '图片' },
  { value: 'document', label: '文档' },
  { value: 'avatar', label: '头像' },
  { value: 'dataset', label: '数据集' },
]

const authStore = useAuthStore()

const stats = ref<FileStats>({ files: 0, bytes: 0 })
const uploadCategory = ref('attachment')
const uploadMode = ref<'server' | 'presign'>('server')
const uploading = ref(false)
const uploadPercent = ref(0)

const { rows, total, loading, query, load, search, reset, changePage, changePageSize } = useTable<
  FileItem,
  FileFilters
>(
  (params) =>
    listFiles({
      page: params.page,
      page_size: params.page_size,
      keyword: params.filters.keyword || undefined,
      category: params.filters.category || undefined,
      only_mine: params.filters.only_mine || undefined,
    }),
  {
    pageSize: 10,
    filters: { keyword: '', category: '', only_mine: false },
  },
)

const categoryLabel = computed(() => {
  const map = new Map(CATEGORIES.map((item) => [item.value, item.label]))
  return (value: string): string => map.get(value) ?? value
})

/** 概览统计文案 */
const statsText = computed(
  () => `共 ${stats.value.files} 个文件, 占用 ${formatBytes(stats.value.bytes)}`,
)

async function loadStats(): Promise<void> {
  try {
    stats.value = await getFileStats()
  } catch {
    // 统计失败不阻塞主流程
  }
}

/**
 * el-upload 自定义上传 (http-request)。
 * 根据 uploadMode 选择服务端中转或前端直传。
 */
async function handleUpload(options: UploadRequestOptions): Promise<void> {
  const file = options.file
  uploading.value = true
  uploadPercent.value = 0
  try {
    const onProgress = (percent: number): void => {
      uploadPercent.value = percent
    }
    if (uploadMode.value === 'presign') {
      await uploadFileByPresign(file, uploadCategory.value, onProgress)
    } else {
      await uploadFile(file, uploadCategory.value, onProgress)
    }
    options.onSuccess?.({})
    ElMessage.success(`文件「${file.name}」上传成功`)
    await Promise.all([load(), loadStats()])
  } catch {
    // el-upload 的 onError 要求 UploadAjaxError 结构 (name/status/method/url)
    const errorLike = Object.assign(new Error('上传失败'), {
      name: 'UploadAjaxError',
      status: 0,
      method: 'POST',
      url: '/files/upload',
    })
    options.onError?.(errorLike as Parameters<UploadRequestOptions['onError']>[0])
    ElMessage.error(`文件「${file.name}」上传失败`)
  } finally {
    uploading.value = false
    uploadPercent.value = 0
  }
}

/**
 * el-table-column 作用域插槽的行类型为 DefaultRow, 无法自动收窄为 FileItem,
 * 这里集中做一次类型收口。
 */
function asFile(row: unknown): FileItem {
  return row as FileItem
}

/** 通过预签名地址下载 (自动触发浏览器下载) */
async function handleDownload(row: unknown): Promise<void> {
  const file = asFile(row)
  const { url, original_name } = await getDownloadUrl(file.id)
  const link = document.createElement('a')
  link.href = url
  link.download = original_name || file.original_name
  link.target = '_blank'
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  ElMessage.success('已开始下载')
}

async function handleDelete(row: unknown): Promise<void> {
  await deleteFile(asFile(row).id)
  ElMessage.success('文件已删除')
  await Promise.all([load(), loadStats()])
}

async function handleOnlyMineChange(): Promise<void> {
  await search()
}

onMounted(async () => {
  await Promise.all([load(), loadStats()])
})
</script>

<template>
  <PageContainer title="文件管理" description="MinIO 对象存储文件的上传、下载与删除">
    <template #actions>
      <ElButton :icon="Refresh" :loading="loading" @click="load()">刷新</ElButton>
    </template>

    <section class="file-upload">
      <div class="file-upload__controls">
        <ElSelect v-model="uploadCategory" class="file-upload__category">
          <ElOption
            v-for="item in CATEGORIES"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </ElSelect>
        <ElRadioGroup v-model="uploadMode">
          <ElRadioButton value="server">服务端中转</ElRadioButton>
          <ElRadioButton value="presign">前端直传</ElRadioButton>
        </ElRadioGroup>
        <span class="text-muted">
          {{ uploadMode === 'server' ? '适合小文件, 服务端转发' : '适合大文件, 直传 MinIO' }}
        </span>
      </div>

      <ElUpload
        v-permission="'files:upload'"
        class="file-upload__drop"
        drag
        multiple
        :show-file-list="false"
        :http-request="handleUpload"
        :disabled="uploading"
      >
        <div class="file-upload__inner">
          <ElIcon :size="34" class="file-upload__icon"><UploadFilled /></ElIcon>
          <p class="file-upload__text">将文件拖到此处, 或 <em>点击上传</em></p>
          <p class="file-upload__hint">单个文件不超过 50MB</p>
        </div>
      </ElUpload>

      <ElProgress
        v-if="uploading"
        :percentage="uploadPercent"
        :stroke-width="10"
        striped
        striped-flow
      />
    </section>

    <div class="file-meta">
      <span class="text-secondary">{{ statsText }}</span>
      <span class="text-muted">当前用户: {{ authStore.displayName }}</span>
    </div>

    <SearchToolbar>
      <ElInput
        v-model="query.filters.keyword"
        placeholder="按文件名搜索"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search()"
        @clear="search()"
      />
      <ElSelect v-model="query.filters.category" placeholder="分类" clearable @change="search()">
        <ElOption label="全部分类" value="" />
        <ElOption
          v-for="item in CATEGORIES"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </ElSelect>
      <ElSelect
        v-model="query.filters.only_mine"
        placeholder="归属"
        @change="handleOnlyMineChange"
      >
        <ElOption label="全部文件" :value="false" />
        <ElOption label="仅我的文件" :value="true" />
      </ElSelect>
      <template #actions>
        <ElButton type="primary" :icon="Search" @click="search()">查询</ElButton>
        <ElButton @click="reset()">重置</ElButton>
      </template>
    </SearchToolbar>

    <ElTable v-loading="loading" :data="rows" border stripe row-key="id">
      <template #empty>
        <EmptyState description="暂无文件" />
      </template>

      <ElTableColumn label="文件名" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="file-name">
            <span class="file-name__text">{{ row.original_name }}</span>
            <span class="file-name__object text-mono">{{ truncate(row.object_name, 48) }}</span>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn label="分类" width="110" align="center">
        <template #default="{ row }">
          <ElTag size="small" effect="light">{{ categoryLabel(row.category) }}</ElTag>
        </template>
      </ElTableColumn>

      <ElTableColumn label="大小" width="120" align="right">
        <template #default="{ row }">
          <span class="text-secondary">{{ formatBytes(row.size) }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="类型" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="text-mono">{{ row.content_type }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="状态" width="100" align="center">
        <template #default="{ row }">
          <ElTag
            size="small"
            effect="light"
            :type="row.status === 'active' || row.status === 'ready' ? 'success' : 'info'"
          >
            {{ row.status }}
          </ElTag>
        </template>
      </ElTableColumn>

      <ElTableColumn label="上传时间" width="180">
        <template #default="{ row }">
          <span class="text-secondary">{{ formatDateTime(row.created_at) }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="操作" width="170" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <ElButton
              v-permission="'files:download'"
              link
              type="primary"
              :icon="Download"
              @click="handleDownload(row)"
            >
              下载
            </ElButton>
            <ElPopconfirm
              v-permission="'files:delete'"
              title="确定删除该文件吗?"
              confirm-button-text="删除"
              cancel-button-text="取消"
              confirm-button-type="danger"
              width="220"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <ElButton link type="danger" :icon="Delete">删除</ElButton>
              </template>
            </ElPopconfirm>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="file-pagination">
      <ElPagination
        :current-page="query.page"
        :page-size="query.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </div>
  </PageContainer>
</template>

<style scoped lang="scss">
.file-upload {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 18px;

  &__controls {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
  }

  &__category {
    width: 160px;
  }

  &__drop {
    :deep(.el-upload-dragger) {
      padding: 22px;
      background-color: var(--app-bg-hover);
      border: 1px dashed var(--app-border-color);
      border-radius: var(--app-radius-md);
      transition: border-color 0.2s ease;

      &:hover {
        border-color: var(--app-color-primary);
      }
    }
  }

  &__inner {
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: center;
    color: var(--app-text-secondary);
  }

  &__icon {
    color: var(--app-color-primary);
  }

  &__text {
    font-size: 14px;

    em {
      font-style: normal;
      color: var(--app-color-primary);
    }
  }

  &__hint {
    font-size: 12px;
    color: var(--app-text-placeholder);
  }
}

.file-meta {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
}

.file-name {
  display: flex;
  flex-direction: column;
  line-height: 1.35;

  &__text {
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__object {
    color: var(--app-text-placeholder);
  }
}

.row-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.file-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
