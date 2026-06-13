<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">10666 Recharge</p>
        <h2>{{ t('gpt.heroTitle') }}</h2>
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
          <span class="rail-mark"><BrandLogo /></span>
          <div>
            <p class="eyebrow">Flow</p>
            <h2>{{ t('gpt.flowTitle') }}</h2>
          </div>
        </div>

        <div class="account-strip" :class="{ 'is-ready': Boolean(card) }">
          <span>{{ t('gpt.rechargeType') }}</span>
          <strong>{{ card?.typeLabel || t('gpt.pendingVerify') }}</strong>
          <em>{{ tokenInfo ? t('gpt.accountIs', { email: tokenInfo.email }) : card ? t('gpt.cardStatusIs', { status: card.status }) : t('gpt.verifyFirst') }}</em>
        </div>

        <ol class="submit-steps">
          <li :class="{ active: activeStep === 0, done: Boolean(card) }">
            <span>1</span>
            <div>
              <strong>{{ t('gpt.step1Title') }}</strong>
              <small>{{ card ? t('gpt.step1Done') : t('gpt.step1Desc') }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 1, done: Boolean(tokenInfo) }">
            <span>2</span>
            <div>
              <strong>{{ t('gpt.step2Title') }}</strong>
              <small>{{ tokenInfo ? t('gpt.recognized', { plan: tokenInfo.planType }) : t('gpt.step2Desc') }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 2, done: isTerminal }">
            <span>3</span>
            <div>
              <strong>{{ t('gpt.step3Title') }}</strong>
              <small>{{ orderId ? (isTerminal ? statusLabel : t('gpt.status.running')) : t('gpt.step3Desc') }}</small>
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
          <el-form-item :label="t('gpt.cardLabel')">
            <el-input v-model.trim="form.cardCode" :placeholder="t('gpt.cardPlaceholder')" @input="resetCard" />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="verifying" type="primary" @click="handleVerifyCard">{{ t('gpt.verifyNext') }}</el-button>
          </div>
        </el-form>

        <!-- Step 2: 校验 Session JSON -->
        <el-form v-else-if="activeStep === 1" label-position="top" @submit.prevent>
          <div class="step-summary">
            <span>{{ t('gpt.verifiedType') }}</span>
            <strong>{{ card?.typeLabel }}</strong>
            <em>{{ t('gpt.cardIs', { code: form.cardCode }) }}</em>
          </div>
          <div class="session-guide">
            <p class="session-guide__title">{{ t('gpt.getSessionTitle') }}</p>
            <ol>
              <li v-html="t('gpt.sessionStep1')"></li>
              <li v-html="t('gpt.sessionStep2')"></li>
              <li>{{ t('gpt.sessionStep3') }}</li>
            </ol>
          </div>
          <el-form-item :label="t('gpt.sessionLabel')">
            <el-input
              v-model="form.sessionJson"
              type="textarea"
              :rows="8"
              resize="vertical"
              :placeholder="t('gpt.sessionPlaceholder')"
              @input="resetToken"
            />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button @click="goToStep(0)">{{ t('gpt.prev') }}</el-button>
            <el-button :loading="verifyingToken" type="primary" @click="handleVerifyToken">{{ t('gpt.verifySession') }}</el-button>
          </div>
        </el-form>

        <!-- Step 3: 确认充值 / 进度 -->
        <div v-else class="submit-review">
          <div class="review-grid">
            <div>
              <span>{{ t('gpt.rechargeType') }}</span>
              <strong>{{ card?.typeLabel || '-' }}</strong>
            </div>
            <div>
              <span>{{ t('gpt.accountEmail') }}</span>
              <strong>{{ order?.email || tokenInfo?.email || '-' }}</strong>
            </div>
            <div>
              <span>{{ t('gpt.currentPlan') }}</span>
              <strong>{{ tokenInfo?.planType || '-' }}</strong>
            </div>
            <div>
              <span>{{ orderId ? t('gpt.orderStatus') : t('gpt.cdkStatus') }}</span>
              <strong>{{ orderId ? statusLabel : card?.status || '-' }}</strong>
            </div>
          </div>

          <template v-if="orderId">
            <div class="step-summary">
              <span>{{ t('gpt.orderNo') }}</span>
              <strong class="mono">{{ orderId }}</strong>
              <em>{{ order?.resultMessage || (polling ? t('gpt.processingDots') : statusLabel) }}</em>
            </div>
            <div v-if="subscription" class="step-summary">
              <span>{{ t('gpt.subUntil') }}</span>
              <strong>{{ subscription.activeUntilBeijing || subscription.activeUntil }}</strong>
              <em>{{ t('gpt.subInfo', { plan: subscription.planType, days: subscription.subscriptionDays ?? subscription.durationDays }) }}</em>
            </div>
          </template>

          <div class="action-row submit-action-row">
            <template v-if="!orderId">
              <el-button @click="goToStep(1)">{{ t('gpt.prev') }}</el-button>
              <el-button :loading="submitting" type="primary" @click="handleRecharge">{{ t('gpt.confirmRecharge') }}</el-button>
            </template>
            <template v-else>
              <el-button v-if="isTerminal" @click="resetAll">{{ t('gpt.rechargeAgain') }}</el-button>
              <el-button v-else :loading="polling" type="primary" @click="refreshOnce">{{ t('gpt.refresh') }}</el-button>
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
import { useI18n } from 'vue-i18n';
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
import BrandLogo from '../components/BrandLogo.vue';

const { t } = useI18n();

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED']);
// 订单状态码 → locale 键
const STATUS_KEY: Record<string, string> = {
  PENDING: 'pending',
  RUNNING: 'running',
  SUCCEEDED: 'succeeded',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
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
const statusLabel = computed(() => {
  const s = order.value?.status || '';
  const k = STATUS_KEY[s];
  return k ? t(`gpt.status.${k}`) : s || t('gpt.status.waiting');
});
const isTerminal = computed(() => TERMINAL.has(order.value?.status || ''));
const stepEyebrow = computed(() => `Step ${String(activeStep.value + 1).padStart(2, '0')}`);
const stepTitle = computed(() => {
  if (activeStep.value === 0) return t('gpt.step1Title');
  if (activeStep.value === 1) return t('gpt.step2Title');
  return orderId.value ? t('gpt.step3Title') : t('gpt.confirmRecharge');
});
const progressValue = computed(() => {
  if (activeStep.value === 0) return card.value ? 34 : 12;
  if (activeStep.value === 1) return tokenInfo.value ? 67 : 48;
  if (!orderId.value) return 76;
  return isTerminal.value ? 100 : 88;
});
const stepTagText = computed(() => {
  if (activeStep.value === 0) return card.value ? card.value.typeLabel : t('gpt.pendingVerify');
  if (activeStep.value === 1) return tokenInfo.value ? t('gpt.recognizedTag') : t('gpt.pendingVerify');
  return orderId.value ? statusLabel.value : t('gpt.pendingConfirm');
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
    ElMessage.warning(t('gpt.enterCard'));
    return;
  }
  verifying.value = true;
  try {
    const result = await verifyCard(form.cardCode);
    if (!result.canSubmit) {
      ElMessage.error(t('gpt.cannotSubmit'));
      return;
    }
    card.value = result;
    ElMessage.success(t('gpt.cardVerified'));
    currentStep.value = 1;
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifying.value = false;
  }
}

async function handleVerifyToken() {
  if (!card.value) {
    ElMessage.warning(t('gpt.verifyCardFirst'));
    return;
  }
  if (!form.sessionJson.trim()) {
    ElMessage.warning(t('gpt.pasteSession'));
    return;
  }
  verifyingToken.value = true;
  try {
    tokenInfo.value = await verifyToken(form.sessionJson);
    ElMessage.success(t('gpt.sessionVerified'));
    currentStep.value = 2;
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifyingToken.value = false;
  }
}

async function handleRecharge() {
  if (!card.value || !tokenInfo.value) {
    ElMessage.warning(t('gpt.completeBoth'));
    return;
  }
  submitting.value = true;
  try {
    const result = await createOrder(form.cardCode, form.sessionJson);
    orderId.value = result.orderId;
    order.value = { id: result.orderId, status: result.status };
    persistActiveOrder();
    ElMessage.success(t('gpt.orderCreated'));
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
