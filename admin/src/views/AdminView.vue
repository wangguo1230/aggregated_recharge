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
          <el-tab-pane label="接码卡密" name="sms" />
        </el-tabs>
        <div class="admin-toolbar">
          <span style="font-size: 13px; color: var(--recharge-muted)">
            {{ tabCountLabel }}
          </span>
          <el-button size="small" @click="handleLogout">退出登录</el-button>
        </div>
      </div>

      <!-- ===== 卡密映射 ===== -->
      <template v-if="activeTab === 'mappings'">
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="真实卡密（每行一个，最多 500）">
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
            <el-table-column label="真实卡密" min-width="200" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ row.realCard || '-' }}</span></template>
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
              <span class="mono">{{ row.realCard || '-' }}</span>
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
      <template v-else-if="activeTab === 'orders'">
        <div class="admin-card__head" style="border: none; margin: 0 0 6px; padding: 0">
          <div><p class="kicker">Orders</p><h3>充值记录</h3></div>
          <div class="admin-toolbar">
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
              <span class="mono">{{ row.realCard || '-' }}</span>
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

      <!-- ===== 接码卡密 ===== -->
      <template v-else>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="接码卡密（每行一个，格式 手机号----查询URL，最多 500）">
            <el-input
              v-model="smsImportRaw"
              type="textarea"
              :rows="4"
              resize="vertical"
              placeholder="13527097093----https://api.k8sms.com/q/xxxxxxxx"
            />
          </el-form-item>
          <el-form-item label="备注（可选）">
            <el-input v-model.trim="smsImportNote" maxlength="255" placeholder="例如 批次/来源" style="max-width: 360px" />
          </el-form-item>
          <el-button :loading="smsImporting" type="primary" @click="handleSmsImport">导入并生成兑换码</el-button>
        </el-form>

        <template v-if="smsImportResults.length">
          <div class="admin-result-bar">
            <span>导入结果</span>
            <strong>新建 {{ smsImportCreated }} / 共 {{ smsImportResults.length }}</strong>
            <el-button size="small" @click="copyNewSmsExternals">复制全部新兑换码</el-button>
          </div>
          <el-table :data="smsImportResults" border size="small" empty-text="无结果">
            <el-table-column label="手机号" min-width="140">
              <template #default="{ row }"><span class="mono">{{ row.phone || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="兑换码" min-width="170">
              <template #default="{ row }"><span class="mono">{{ row.externalCode || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="结果" width="90">
              <template #default="{ row }">
                <el-tag :type="smsImportTagType(row.status)" size="small">{{ smsImportLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.message || '-' }}</template>
            </el-table-column>
          </el-table>
        </template>

        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">SMS Cards</p><h3>接码卡密列表</h3></div>
          <div class="admin-toolbar">
            <el-input v-model.trim="smsSearch" placeholder="搜兑换码/手机号" style="width: 180px" clearable @keyup.enter="loadSmsMappings" />
            <el-button :loading="smsLoading" @click="loadSmsMappings">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="smsLoading" :data="smsMappings" border empty-text="暂无接码卡密">
          <el-table-column label="兑换码" min-width="170">
            <template #default="{ row }">
              <span class="mono">{{ row.externalCode }}</span>
              <el-button link type="primary" size="small" @click="copyText(row.externalCode)">复制</el-button>
            </template>
          </el-table-column>
          <el-table-column label="手机号" min-width="140">
            <template #default="{ row }"><span class="mono">{{ row.phone || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="完整卡密（手机号----URL）" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="mono">{{ row.realCard || '-' }}</span>
            </template>
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
              <el-button link type="primary" size="small" @click="toggleSmsStatus(row)">
                {{ row.status === 'active' ? '停用' : '启用' }}
              </el-button>
              <el-button link type="danger" size="small" @click="removeSmsMapping(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </template>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import {
  adminCheck,
  deleteMapping,
  deleteSmsMapping,
  getAdminToken,
  importMappings,
  importSmsMappings,
  listMappings,
  listOrders,
  listSmsMappings,
  setAdminToken,
  updateMappingStatus,
  updateSmsMappingStatus,
  type ImportResultItem,
  type MappingItem,
  type OrderItem,
  type SmsImportResultItem,
  type SmsMappingItem,
} from '../api/admin';

const authed = ref(false);
const tokenInput = ref('');
const loggingIn = ref(false);
const activeTab = ref<'mappings' | 'orders' | 'sms'>('mappings');

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

const smsImportRaw = ref('');
const smsImportNote = ref('');
const smsImporting = ref(false);
const smsImportResults = ref<SmsImportResultItem[]>([]);
const smsImportCreated = ref(0);
const smsMappings = ref<SmsMappingItem[]>([]);
const smsLoading = ref(false);
const smsSearch = ref('');

const tabCountLabel = computed(() => {
  if (activeTab.value === 'orders') return `记录 ${orders.value.length}`;
  if (activeTab.value === 'sms') return `接码卡密 ${smsMappings.value.length}`;
  return `映射 ${mappings.value.length}`;
});

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

function fallbackCopy(text: string): boolean {
  // 非安全上下文（http://IP 访问）下 navigator.clipboard 不可用，退回 execCommand。
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.position = 'fixed';
  ta.style.top = '-9999px';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  document.body.removeChild(ta);
  return ok;
}

async function copyText(text: string) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      ElMessage.success('已复制');
      return;
    }
  } catch {
    // 安全上下文下仍失败则继续走兜底
  }
  if (fallbackCopy(text)) {
    ElMessage.success('已复制');
  } else {
    ElMessage.warning('复制失败，请手动选择文本复制');
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
  smsMappings.value = [];
  smsImportResults.value = [];
}

function onTabChange() {
  if (activeTab.value === 'orders' && !orders.value.length) {
    void loadOrders();
  }
  if (activeTab.value === 'sms' && !smsMappings.value.length) {
    void loadSmsMappings();
  }
}

function smsImportLabel(status: string) {
  return { created: '已生成', exists: '已存在', duplicate: '重复', invalid: '格式错误' }[status] || status;
}
function smsImportTagType(status: string) {
  return { created: 'success', exists: 'warning', duplicate: 'info', invalid: 'danger' }[status] || 'info';
}

function copyNewSmsExternals() {
  const codes = smsImportResults.value
    .filter((r) => r.status === 'created' && r.externalCode)
    .map((r) => r.externalCode as string);
  if (!codes.length) {
    ElMessage.warning('没有新生成的兑换码');
    return;
  }
  void copyText(codes.join('\n'));
}

async function handleSmsImport() {
  const cards = Array.from(new Set(smsImportRaw.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)));
  if (!cards.length) {
    ElMessage.warning('请至少输入一个接码卡密');
    return;
  }
  smsImporting.value = true;
  try {
    const r = await importSmsMappings(cards, smsImportNote.value);
    smsImportResults.value = r.results;
    smsImportCreated.value = r.created;
    ElMessage.success(`导入完成，新建 ${r.created} 条`);
    smsImportRaw.value = '';
    await loadSmsMappings();
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    smsImporting.value = false;
  }
}

async function loadSmsMappings() {
  smsLoading.value = true;
  try {
    smsMappings.value = await listSmsMappings(smsSearch.value);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    smsLoading.value = false;
  }
}

async function toggleSmsStatus(row: SmsMappingItem) {
  const next = row.status === 'active' ? 'disabled' : 'active';
  try {
    await updateSmsMappingStatus(row.id, next);
    row.status = next;
    ElMessage.success('已更新');
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function removeSmsMapping(row: SmsMappingItem) {
  try {
    await ElMessageBox.confirm(`确认删除兑换码 ${row.externalCode} 的接码卡密？`, '删除确认', { type: 'warning' });
  } catch {
    return;
  }
  try {
    await deleteSmsMapping(row.id);
    smsMappings.value = smsMappings.value.filter((m) => m.id !== row.id);
    ElMessage.success('已删除');
  } catch (error) {
    ElMessage.error((error as Error).message);
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
