<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">Card Lookup</p>
        <h2>{{ t('cards.title') }}</h2>
      </div>
    </div>

    <div class="submit-flow">
      <main class="submit-panel" style="grid-column: 1 / -1">
        <div class="submit-panel__head">
          <div>
            <p class="eyebrow">Lookup</p>
            <h3>{{ t('cards.subtitle') }}</h3>
          </div>
          <el-tag :type="items.length ? 'success' : 'info'">{{ items.length ? t('cards.totalN', { n: items.length }) : t('cards.pending') }}</el-tag>
        </div>

        <el-form label-position="top" @submit.prevent>
          <el-form-item :label="t('cards.inputLabel')">
            <el-input
              v-model="raw"
              type="textarea"
              :rows="6"
              resize="vertical"
              placeholder="AW-XXXXX-XXXXX&#10;AW-YYYYY-YYYYY"
            />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="loading" type="primary" @click="handleQuery">{{ t('cards.queryBtn') }}</el-button>
          </div>
        </el-form>

        <el-table v-if="items.length" :data="items" border style="margin-top: 8px" :empty-text="t('cards.noResult')">
          <el-table-column :label="t('cards.colCard')" min-width="220" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.cardCode }}</span></template>
          </el-table-column>
          <el-table-column :label="t('cards.colStatus')" width="120">
            <template #default="{ row }">
              <el-tag :type="statusType(row.cardStatus)" size="small">{{ statusLabel(row.cardStatus) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('cards.colAccount')" min-width="200" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.rechargeAccount || '-' }}</span></template>
          </el-table-column>
          <el-table-column :label="t('cards.colTime')" min-width="180">
            <template #default="{ row }">{{ formatTime(row.rechargeTime) }}</template>
          </el-table-column>
          <el-table-column :label="t('cards.colReplace')" min-width="180" show-overflow-tooltip>
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
import { useI18n } from 'vue-i18n';
import { queryCards, type AskWhyCardStatus } from '../api/askwhy';

const { t } = useI18n();

// 上游状态码 → locale 键
const STATUS_KEY: Record<string, string> = {
  UNUSED: 'unused',
  LOCKED: 'locked',
  USED: 'used',
  ABNORMAL: 'abnormal',
  DISABLED: 'disabled',
  NOT_FOUND: 'notFound',
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
  const k = STATUS_KEY[status];
  return k ? t(`cards.status.${k}`) : status || '-';
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
    ElMessage.warning(t('cards.enterCard'));
    return;
  }
  if (codes.length > 200) {
    ElMessage.warning(t('cards.max200'));
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
