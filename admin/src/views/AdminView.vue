<template>
  <!-- 未登录：居中登录卡 -->
  <div v-if="!authed" class="admin-login-wrap">
    <div class="admin-card admin-login">
      <div class="admin-card__head">
        <div>
          <p class="kicker">Login</p>
          <h3>管理员登录</h3>
        </div>
      </div>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="管理员口令">
          <el-input v-model.trim="tokenInput" type="password" show-password placeholder="ASKWHY_ADMIN_TOKEN" @keyup.enter="handleLogin" />
        </el-form-item>
        <el-button :loading="loggingIn" type="primary" style="width: 100%" @click="handleLogin">登 录</el-button>
      </el-form>
    </div>
  </div>

  <template v-else>
    <div class="admin-card">
      <div class="admin-card__head">
        <el-tabs v-model="activeTab" style="flex: 1; margin-bottom: -14px" @tab-change="onTabChange">
          <el-tab-pane label="卡密映射" name="mappings" />
          <el-tab-pane label="充值记录" name="orders" />
        </el-tabs>
        <div class="admin-toolbar">
          <span style="font-size: 13px; color: var(--recharge-muted)">
            {{ activeTab === 'mappings' ? `映射 ${mappings.length}` : `记录 ${orders.length}` }}
          </span>
          <el-button size="small" @click="handleLogout">退出登录</el-button>
        </div>
      </div>

      <!-- ===== 卡密映射 ===== -->
      <template v-if="activeTab === 'mappings'">
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="真实 AskWhy 卡密（每行一个，最多 500）">
            <el-input v-model="importRaw" type="textarea" :rows="4" resize="vertical" placeholder="pro20xXXXXXXXXXX&#10;plusYYYYYYYYYY" />
          </el-form-item>
          <el-form-item label="备注（可选）">
            <el-input v-model.trim="importNote" maxlength="255" placeholder="例如 批次/来源" style="max-width: 360px" />
          </el-form-item>
          <el-button :loading="importing" type="primary" @click="handleImport">导入并生成外部码</el-button>
        </el-form>

        <template v-if="importResults.length">
          <div class="admin-result-bar">
            <span>导入结果</span>
            <strong>新建 {{ importCreated }} / 共 {{ importResults.length }}</strong>
            <el-button size="small" @click="copyNewExternals">复制全部新外部码</el-button>
          </div>
          <el-table :data="importResults" border size="small" empty-text="无结果">
            <el-table-column label="真实卡尾号" width="110">
              <template #default="{ row }"><span class="mono">****{{ row.realCardLast4 }}</span></template>
            </el-table-column>
            <el-table-column label="外部码" min-width="170">
              <template #default="{ row }"><span class="mono">{{ row.externalCode || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="套餐" width="100">
              <template #default="{ row }">{{ row.typeLabel || '-' }}</template>
            </el-table-column>
            <el-table-column label="结果" width="90">
              <template #default="{ row }">
                <el-tag :type="importTagType(row.status)" size="small">{{ importLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.message || '-' }}</template>
            </el-table-column>
          </el-table>
        </template>

        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">Mappings</p><h3>映射列表</h3></div>
          <div class="admin-toolbar">
            <el-switch v-model="revealReal" active-text="显示真实卡密" />
            <el-input v-model.trim="search" placeholder="搜外部码" style="width: 160px" clearable @keyup.enter="loadMappings" />
            <el-button :loading="loading" @click="loadMappings">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="loading" :data="mappings" border empty-text="暂无映射">
          <el-table-column label="外部码" min-width="170">
            <template #default="{ row }">
              <span class="mono">{{ row.externalCode }}</span>
              <el-button link type="primary" size="small" @click="copyText(row.externalCode)">复制</el-button>
            </template>
          </el-table-column>
          <el-table-column label="真实卡密" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="mono">{{ revealReal ? row.realCard : `****${row.realCardLast4}` }}</span>
            </template>
          </el-table-column>
          <el-table-column label="套餐" width="90">
            <template #default="{ row }">{{ row.cardTypeLabel || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status === 'active' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.note || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="toggleStatus(row)">
                {{ row.status === 'active' ? '停用' : '启用' }}
              </el-button>
              <el-button link type="danger" size="small" @click="removeMapping(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- ===== 充值记录 ===== -->
      <template v-else>
        <div class="admin-card__head" style="border: none; margin: 0 0 6px; padding: 0">
          <div><p class="kicker">Orders</p><h3>充值记录</h3></div>
          <div class="admin-toolbar">
            <el-switch v-model="revealReal" active-text="显示真实卡密" />
            <el-input v-model.trim="orderSearch" placeholder="搜订单号/外部码/邮箱" style="width: 220px" clearable @keyup.enter="loadOrders" />
            <el-button :loading="ordersLoading" @click="loadOrders">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="ordersLoading" :data="orders" border empty-text="暂无充值记录">
          <el-table-column label="订单号" min-width="170" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.orderId }}</span></template>
          </el-table-column>
          <el-table-column label="外部码" min-width="150">
            <template #default="{ row }"><span class="mono">{{ row.externalCode || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="真实卡密" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="mono">{{ revealReal ? row.realCard : `****${row.cardLast4}` }}</span>
            </template>
          </el-table-column>
          <el-table-column label="套餐" width="90">
            <template #default="{ row }">{{ row.cardTypeLabel || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="orderTagType(row.status)" size="small">{{ orderLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="账号邮箱" min-width="190" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.accountEmail || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="订阅到期" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.subscriptionUntil || '-' }}</template>
          </el-table-column>
          <el-table-column label="结果" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">{{ row.resultMessage || '-' }}</template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </template>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { onMounted, ref } from 'vue';
import {
  adminCheck,
  deleteMapping,
  getAdminToken,
  importMappings,
  listMappings,
  listOrders,
  setAdminToken,
  updateMappingStatus,
  type ImportResultItem,
  type MappingItem,
  type OrderItem,
} from '../api/admin';

const authed = ref(false);
const tokenInput = ref('');
const loggingIn = ref(false);
const activeTab = ref<'mappings' | 'orders'>('mappings');
const revealReal = ref(false);

const importRaw = ref('');
const importNote = ref('');
const importing = ref(false);
const importResults = ref<ImportResultItem[]>([]);
const importCreated = ref(0);

const mappings = ref<MappingItem[]>([]);
const loading = ref(false);
const search = ref('');

const orders = ref<OrderItem[]>([]);
const ordersLoading = ref(false);
const orderSearch = ref('');

const ORDER_LABELS: Record<string, string> = {
  PENDING: '待处理',
  RUNNING: '处理中',
  SUCCEEDED: '成功',
  FAILED: '失败',
  CANCELLED: '已取消',
};

function importLabel(status: string) {
  return { created: '已生成', exists: '已存在', duplicate: '重复' }[status] || status;
}
function importTagType(status: string) {
  return { created: 'success', exists: 'warning', duplicate: 'info' }[status] || 'info';
}
function orderLabel(status: string) {
  return ORDER_LABELS[status] || status || '-';
}
function orderTagType(status: string) {
  if (status === 'SUCCEEDED') return 'success';
  if (status === 'FAILED' || status === 'CANCELLED') return 'danger';
  if (status === 'RUNNING') return 'warning';
  return 'info';
}
function formatTime(value: string) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制');
  } catch {
    ElMessage.warning('复制失败，请手动复制');
  }
}

function copyNewExternals() {
  const codes = importResults.value.filter((r) => r.status === 'created' && r.externalCode).map((r) => r.externalCode);
  if (!codes.length) {
    ElMessage.warning('没有新生成的外部码');
    return;
  }
  void copyText(codes.join('\n'));
}

async function handleLogin() {
  if (!tokenInput.value) {
    ElMessage.warning('请输入管理员口令');
    return;
  }
  loggingIn.value = true;
  setAdminToken(tokenInput.value);
  try {
    await adminCheck();
    authed.value = true;
    await loadMappings();
  } catch (error) {
    setAdminToken('');
    ElMessage.error((error as Error).message);
  } finally {
    loggingIn.value = false;
  }
}

function handleLogout() {
  setAdminToken('');
  authed.value = false;
  tokenInput.value = '';
  mappings.value = [];
  orders.value = [];
  importResults.value = [];
}

function onTabChange() {
  if (activeTab.value === 'orders' && !orders.value.length) {
    void loadOrders();
  }
}

async function handleImport() {
  const cards = Array.from(new Set(importRaw.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)));
  if (!cards.length) {
    ElMessage.warning('请至少输入一个真实卡密');
    return;
  }
  importing.value = true;
  try {
    const r = await importMappings(cards, importNote.value);
    importResults.value = r.results;
    importCreated.value = r.created;
    ElMessage.success(`导入完成，新建 ${r.created} 条`);
    importRaw.value = '';
    await loadMappings();
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    importing.value = false;
  }
}

async function loadMappings() {
  loading.value = true;
  try {
    mappings.value = await listMappings(search.value);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    loading.value = false;
  }
}

async function loadOrders() {
  ordersLoading.value = true;
  try {
    orders.value = await listOrders(orderSearch.value);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    ordersLoading.value = false;
  }
}

async function toggleStatus(row: MappingItem) {
  const next = row.status === 'active' ? 'disabled' : 'active';
  try {
    await updateMappingStatus(row.id, next);
    row.status = next;
    ElMessage.success('已更新');
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function removeMapping(row: MappingItem) {
  try {
    await ElMessageBox.confirm(`确认删除外部码 ${row.externalCode} 的映射？`, '删除确认', { type: 'warning' });
  } catch {
    return;
  }
  try {
    await deleteMapping(row.id);
    mappings.value = mappings.value.filter((m) => m.id !== row.id);
    ElMessage.success('已删除');
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

onMounted(async () => {
  if (!getAdminToken()) return;
  try {
    await adminCheck();
    authed.value = true;
    await loadMappings();
  } catch {
    setAdminToken('');
  }
});
</script>
