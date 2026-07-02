<template>
  <div class="data-table-card">
    <div v-if="title" class="table-header">
      <span class="table-title">{{ title }}</span>
      <slot name="actions"></slot>
    </div>
    <el-table
      :data="data"
      :border="false"
      style="width: 100%"
      :default-sort="defaultSort"
    >
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth"
        :sortable="col.sortable"
        :formatter="col.formatter"
      >
        <template v-if="col.type === 'tag'" #default="{ row }">
          <el-tag :type="col.tagType?.(row)" size="small">
            {{ row[col.prop] }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="showPagination" class="table-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="pageSizes"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        background
        small
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface Column {
  prop: string
  label: string
  width?: number
  minWidth?: number
  sortable?: boolean
  type?: 'tag'
  tagType?: (row: any) => string
  formatter?: (row: any) => string
}

const props = withDefaults(defineProps<{
  title?: string
  data: any[]
  columns: Column[]
  showPagination?: boolean
  total?: number
  defaultSort?: { prop: string; order: string }
}>(), {
  showPagination: false,
  total: 0,
})

const currentPage = ref(1)
const pageSize = ref(10)
const pageSizes = [10, 20, 50, 100]

const emit = defineEmits<{
  (e: 'page-change', page: number, pageSize: number): void
}>()

watch([currentPage, pageSize], ([page, size]) => {
  emit('page-change', page, size)
})
</script>

<style lang="scss" scoped>
.data-table {
  background: #fff;
  border-radius: $card-radius;
  box-shadow: $card-shadow;
  padding: 16px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.table-title {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
}

.table-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
