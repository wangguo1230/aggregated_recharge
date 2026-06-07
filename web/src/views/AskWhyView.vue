<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">AskWhy Recharge</p>
        <h2>账号充值申请</h2>
      </div>
      <div class="submit-hero__meter">
        <span>{{ stepEyebrow }}</span>
        <strong>{{ stepTitle }}</strong>
        <div class="meter-track">
          <i :style="{ width: `${progressValue}%` }"></i>
        </div>
      </div>
    </div>

    <div class="submit-flow">
      <aside class="submit-rail">
        <div class="rail-brand">
          <span class="rail-mark">AW</span>
          <div>
            <p class="eyebrow">Flow</p>
            <h2>提交流程</h2>
          </div>
        </div>

        <div class="account-strip" :class="{ 'is-ready': Boolean(card) }">
          <span>充值类型</span>
          <strong>{{ card?.typeLabel || '待校验' }}</strong>
          <em>{{ tokenInfo ? `账号：${tokenInfo.email}` : card ? `卡密状态：${card.status}` : '先校验卡密' }}</em>
        </div>

        <ol class="submit-steps">
          <li :class="{ active: activeStep === 0, done: Boolean(card) }">
            <span>1</span>
            <div>
              <strong>校验卡密</strong>
              <small>{{ card ? '卡密可提交' : '检查卡密是否可用' }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 1, done: Boolean(tokenInfo) }">
            <span>2</span>
            <div>
              <strong>校验 Session</strong>
              <small>{{ tokenInfo ? `已识别 ${tokenInfo.planType}` : '粘贴 Session JSON' }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 2, done: isTerminal }">
            <span>3</span>
            <div>
              <strong>充值进度</strong>
              <small>{{ orderId ? (isTerminal ? statusLabel : '处理中') : '确认后开始充值' }}</small>
            </div>
          </li>
        </ol>
      </aside>

      <main class="submit-panel">
        <div class="submit-panel__head">
          <div>
            <p class="eyebrow">{{ stepEyebrow }}</p>
            <h3>{{ stepTitle }}</h3>
          </div>
          <el-tag :type="stepTagType">{{ stepTagText }}</el-tag>
        </div>

        <!-- Step 1: 校验卡密 -->
        <el-form v-if="activeStep === 0" label-position="top" @submit.prevent>
          <el-form-item label="卡密">
            <el-input v-model.trim="form.cardCode" placeholder="例如 AW-XXXXX-XXXXX" @input="resetCard" />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="verifying" type="primary" @click="handleVerifyCard">校验并进入下一步</el-button>
          </div>
        </el-form>

        <!-- Step 2: 校验 Session JSON -->
        <el-form v-else-if="activeStep === 1" label-position="top" @submit.prevent>
          <div class="step-summary">
            <span>已校验充值类型</span>
            <strong>{{ card?.typeLabel }}</strong>
            <em>卡密：{{ form.cardCode }}</em>
          </div>
          <div class="session-guide">
            <p class="session-guide__title">获取 Session JSON</p>
            <ol>
              <li>
                登录
                <a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">https://chatgpt.com/</a>
              </li>
              <li>
                访问
                <a href="https://chatgpt.com/api/auth/session" target="_blank" rel="noopener noreferrer">
                  https://chatgpt.com/api/auth/session
                </a>
                并复制完整返回 JSON
              </li>
              <li>把整段 JSON 粘贴到下方（不支持只粘贴 token）</li>
            </ol>
          </div>
          <el-form-item label="Session JSON">
            <el-input
              v-model="form.sessionJson"
              type="textarea"
              :rows="8"
              resize="vertical"
              placeholder="粘贴完整 Session JSON"
              @input="resetToken"
            />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button @click="goToStep(0)">上一步</el-button>
            <el-button :loading="verifyingToken" type="primary" @click="handleVerifyToken">校验 Session 并继续</el-button>
          </div>
        </el-form>

        <!-- Step 3: 确认充值 / 进度 -->
        <div v-else class="submit-review">
          <div class="review-grid">
            <div>
              <span>充值类型</span>
              <strong>{{ card?.typeLabel || '-' }}</strong>
            </div>
            <div>
              <span>账号邮箱</span>
              <strong>{{ order?.email || tokenInfo?.email || '-' }}</strong>
            </div>
            <div>
              <span>当前套餐</span>
              <strong>{{ tokenInfo?.planType || '-' }}</strong>
            </div>
            <div>
              <span>{{ orderId ? '订单状态' : 'CDK 状态' }}</span>
              <strong>{{ orderId ? statusLabel : card?.status || '-' }}</strong>
            </div>
          </div>

          <template v-if="orderId">
            <div class="step-summary">
              <span>订单号</span>
              <strong class="mono">{{ orderId }}</strong>
              <em>{{ order?.resultMessage || (polling ? '处理中…' : statusLabel) }}</em>
            </div>
            <div v-if="subscription" class="step-summary">
              <span>订阅有效期（北京时间）</span>
              <strong>{{ subscription.activeUntilBeijing || subscription.activeUntil }}</strong>
              <em>套餐 {{ subscription.planType }} · 共 {{ subscription.subscriptionDays ?? subscription.durationDays }} 天</em>
            </div>
          </template>

          <div class="action-row submit-action-row">
            <template v-if="!orderId">
              <el-button @click="goToStep(1)">上一步</el-button>
              <el-button :loading="submitting" type="primary" @click="handleRecharge">确认并开始充值</el-button>
            </template>
            <template v-else>
              <el-button v-if="isTerminal" @click="resetAll">再充一单</el-button>
              <el-button v-else :loading="polling" type="primary" @click="refreshOnce">刷新状态</el-button>
            </template>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import {
  createOrder,
  fetchOrderStatus,
  fetchSubscription,
  verifyCard,
  verifyToken,
  type AskWhyCard,
  type AskWhyOrder,
  type AskWhySubscription,
  type AskWhyTokenInfo,
} from '../api/askwhy';

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED']);
const STATUS_LABELS: Record<string, string> = {
  PENDING: '已创建，等待处理',
  RUNNING: '处理中',
  SUCCEEDED: '充值成功',
  FAILED: '充值失败',
  CANCELLED: '已取消',
};
// 进行中订单存本地，刷新/断线后可恢复轮询，避免丢单。
const STORAGE_KEY = 'askwhy:activeOrder';

const form = reactive({ cardCode: '', sessionJson: '' });
const card = ref<AskWhyCard | null>(null);
const tokenInfo = ref<AskWhyTokenInfo | null>(null);
const orderId = ref('');
const order = ref<AskWhyOrder | null>(null);
const subscription = ref<AskWhySubscription | null>(null);

const verifying = ref(false);
const verifyingToken = ref(false);
const submitting = ref(false);
const polling = ref(false);
const currentStep = ref(0);
let pollTimer: ReturnType<typeof setInterval> | undefined;

const activeStep = computed(() => currentStep.value);
const statusLabel = computed(() => STATUS_LABELS[order.value?.status || ''] || order.value?.status || '等待处理');
const isTerminal = computed(() => TERMINAL.has(order.value?.status || ''));
const stepEyebrow = computed(() => `Step ${String(activeStep.value + 1).padStart(2, '0')}`);
const stepTitle = computed(() => {
  if (activeStep.value === 0) return '校验卡密';
  if (activeStep.value === 1) return '校验 Session';
  return orderId.value ? '充值进度' : '确认并充值';
});
const progressValue = computed(() => {
  if (activeStep.value === 0) return card.value ? 34 : 12;
  if (activeStep.value === 1) return tokenInfo.value ? 67 : 48;
  if (!orderId.value) return 76;
  return isTerminal.value ? 100 : 88;
});
const stepTagText = computed(() => {
  if (activeStep.value === 0) return card.value ? card.value.typeLabel : '待校验';
  if (activeStep.value === 1) return tokenInfo.value ? '已识别' : '待校验';
  return orderId.value ? statusLabel.value : '待确认';
});
const stepTagType = computed(() => {
  if (activeStep.value === 2 && orderId.value) {
    if (order.value?.status === 'SUCCEEDED') return 'success';
    if (order.value?.status === 'FAILED' || order.value?.status === 'CANCELLED') return 'danger';
    return 'warning';
  }
  if (activeStep.value === 0) return card.value ? 'success' : 'info';
  if (activeStep.value === 1) return tokenInfo.value ? 'success' : 'info';
  return 'warning';
});

function persistActiveOrder() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ orderId: orderId.value, typeLabel: card.value?.typeLabel || '', type: card.value?.type || '' }),
    );
  } catch {
    // localStorage 不可用时忽略（无痕模式等），不影响主流程。
  }
}

function clearActiveOrder() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 忽略
  }
}

function goToStep(step: number) {
  currentStep.value = step;
}

function resetCard() {
  card.value = null;
  resetToken();
  if (currentStep.value > 0) currentStep.value = 0;
}

function resetToken() {
  tokenInfo.value = null;
  if (currentStep.value > 1) currentStep.value = 1;
}

async function handleVerifyCard() {
  if (!form.cardCode.trim()) {
    ElMessage.warning('请填写卡密');
    return;
  }
  verifying.value = true;
  try {
    const result = await verifyCard(form.cardCode);
    if (!result.canSubmit) {
      ElMessage.error('该卡密当前不可提交');
      return;
    }
    card.value = result;
    ElMessage.success('卡密校验通过');
    currentStep.value = 1;
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifying.value = false;
  }
}

async function handleVerifyToken() {
  if (!card.value) {
    ElMessage.warning('请先校验卡密');
    return;
  }
  if (!form.sessionJson.trim()) {
    ElMessage.warning('请粘贴 Session JSON');
    return;
  }
  verifyingToken.value = true;
  try {
    tokenInfo.value = await verifyToken(form.sessionJson);
    ElMessage.success('Session 校验通过');
    currentStep.value = 2;
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifyingToken.value = false;
  }
}

async function handleRecharge() {
  if (!card.value || !tokenInfo.value) {
    ElMessage.warning('请先完成卡密与 Session 校验');
    return;
  }
  submitting.value = true;
  try {
    const result = await createOrder(form.cardCode, form.sessionJson);
    orderId.value = result.orderId;
    order.value = { id: result.orderId, status: result.status };
    persistActiveOrder();
    ElMessage.success('订单已创建，开始充值');
    startPolling();
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    submitting.value = false;
  }
}

async function refreshOnce() {
  if (!orderId.value) return;
  polling.value = true;
  try {
    order.value = await fetchOrderStatus(orderId.value);
    if (order.value.status === 'SUCCEEDED' && !subscription.value) {
      await loadSubscription();
    }
    if (isTerminal.value) {
      stopPolling();
      clearActiveOrder();
    }
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    polling.value = false;
  }
}

async function loadSubscription() {
  try {
    // 仅传 orderId，后端用该订单加密存储的 Session JSON 查询。
    subscription.value = await fetchSubscription(orderId.value);
  } catch {
    // 订阅查询失败不阻断主流程，用户可稍后到「查询订阅」tab 再查。
  }
}

function startPolling() {
  stopPolling();
  void refreshOnce();
  // 第三方建议 3~5 秒轮询一次，终态停止。
  pollTimer = setInterval(() => {
    if (isTerminal.value) {
      stopPolling();
      return;
    }
    void refreshOnce();
  }, 4000);
}

function stopPolling() {
  if (pollTimer !== undefined) {
    clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

function resetAll() {
  stopPolling();
  clearActiveOrder();
  form.cardCode = '';
  form.sessionJson = '';
  card.value = null;
  tokenInfo.value = null;
  orderId.value = '';
  order.value = null;
  subscription.value = null;
  currentStep.value = 0;
}

function restoreActiveOrder() {
  let saved: { orderId?: string; typeLabel?: string; type?: string } | null = null;
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
  } catch {
    saved = null;
  }
  if (!saved?.orderId) return;
  orderId.value = saved.orderId;
  order.value = { id: saved.orderId, status: 'PENDING' };
  if (saved.typeLabel) {
    card.value = {
      code: '',
      type: saved.type || '',
      typeLabel: saved.typeLabel,
      channelOpen: true,
      canSubmit: false,
      status: 'LOCKED',
    };
  }
  currentStep.value = 2;
  startPolling();
}

onMounted(restoreActiveOrder);
onBeforeUnmount(stopPolling);
</script>
