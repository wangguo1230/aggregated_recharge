<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">Card Lookup</p>
        <h2>卡密查询</h2>
      </div>
    </div>

    <div class="submit-flow">
      <main class="submit-panel" style="grid-column: 1 / -1">
        <div class="submit-panel__head">
          <div>
            <p class="eyebrow">Lookup</p>
            <h3>查询卡密使用状况</h3>
          </div>
          <el-tag :type="items.length ? 'success' : 'info'">{{ items.length ? `共 ${items.length} 条` : '待查询' }}</el-tag>
        </div>

        <el-form label-position="top" @submit.prevent>
          <el-form-item label="卡密（每行一个，或用逗号分隔，最多 200 个）">
            <el-input
              v-model="raw"
              type="textarea"
              :rows="6"
              resize="vertical"
              placeholder="AW-XXXXX-XXXXX&#10;AW-YYYYY-YYYYY"
            />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="loading" type="primary" @click="handleQuery">查询</el-button>
          </div>
        </el-form>

        <el-table v-if="items.length" :data="items" border style="margin-top: 8px" empty-text="无结果">
          <el-table-column label="卡密" min-width="220" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.cardCode }}</span></template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusType(row.cardStatus)" size="small">{{ statusLabel(row.cardStatus) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="充值账号" min-width="200" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.rechargeAccount || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="充值时间" min-width="180">
            <template #default="{ row }">{{ formatTime(row.rechargeTime) }}</template>
          </el-table-column>
          <el-table-column label="置换" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.replacedByCardCode" class="mono">→ {{ row.replacedByCardCode }}</span>
              <span v-else-if="row.previousCardCode" class="mono">← {{ row.previousCardCode }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { ref } from 'vue';
import { queryCards, type AskWhyCardStatus } from '../api/askwhy';

const STATUS_LABELS: Record<string, string> = {
  UNUSED: '未使用',
  LOCKED: '处理中',
  USED: '已使用',
  ABNORMAL: '异常',
  DISABLED: '已禁用',
  NOT_FOUND: '不存在',
};
const STATUS_TYPES: Record<string, string> = {
  UNUSED: 'success',
  LOCKED: 'warning',
  USED: 'info',
  ABNORMAL: 'danger',
  DISABLED: 'danger',
  NOT_FOUND: 'info',
};

const raw = ref('');
const loading = ref(false);
const items = ref<AskWhyCardStatus[]>([]);

function statusLabel(status: string) {
  return STATUS_LABELS[status] || status || '-';
}
function statusType(status: string) {
  return STATUS_TYPES[status] || 'info';
}
function formatTime(value: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function parseCodes(): string[] {
  return Array.from(
    new Set(
      raw.value
        .split(/[\s,，]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    ),
  );
}

async function handleQuery() {
  const codes = parseCodes();
  if (!codes.length) {
    ElMessage.warning('请至少输入一个卡密');
    return;
  }
  if (codes.length > 200) {
    ElMessage.warning('一次最多查询 200 个卡密');
    return;
  }
  loading.value = true;
  items.value = [];
  try {
    items.value = await queryCards(codes);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    loading.value = false;
  }
}
</script>
