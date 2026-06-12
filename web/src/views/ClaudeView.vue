<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">Claude Recharge</p>
        <h2>Claude Pro 充值</h2>
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
            <h2>充值流程</h2>
          </div>
        </div>

        <div class="account-strip" :class="{ 'is-ready': Boolean(card) }">
          <span>商品</span>
          <strong>{{ card?.giftName || '待校验' }}</strong>
          <em>{{ card ? '卡密可用，填写 Organization ID 提交' : '先校验外部码' }}</em>
        </div>

        <ol class="submit-steps">
          <li :class="{ active: activeStep === 0, done: Boolean(card) }">
            <span>1</span>
            <div>
              <strong>校验外部码</strong>
              <small>{{ card ? '已获取商品信息' : '检查卡密是否可用' }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 1, done: succeeded }">
            <span>2</span>
            <div>
              <strong>提交充值</strong>
              <small>{{ succeeded ? '充值成功' : '填写 Organization ID' }}</small>
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

        <!-- Step 1: 校验外部码 -->
        <el-form v-if="activeStep === 0" label-position="top" @submit.prevent>
          <el-form-item label="充值卡密（外部码）">
            <el-input v-model.trim="cardCode" placeholder="例如 CL-XXXXX-XXXXX" clearable @keyup.enter="handleVerify" />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="verifying" type="primary" @click="handleVerify">校验卡密</el-button>
          </div>
        </el-form>

        <!-- Step 2: 提交激活 -->
        <div v-else class="submit-review">
          <div class="review-grid">
            <div>
              <span>商品</span>
              <strong>{{ card?.giftName || '-' }}</strong>
            </div>
            <div>
              <span>卡密状态</span>
              <strong>{{ card?.statusHint || useStatusText }}</strong>
            </div>
          </div>

          <el-form label-position="top" @submit.prevent>
            <el-form-item label="Claude Organization ID（uid）">
              <el-input v-model.trim="uid" placeholder="例如 org_xxxxxxxxxxxxx" clearable @keyup.enter="handleActivate" />
              <p class="claude-hint">在 Claude → Settings → Account 页面里的 Organization ID。</p>
            </el-form-item>
          </el-form>

          <!-- 结果提示 -->
          <div v-if="resultMessage" class="step-summary" :class="resultClass">
            <strong>{{ resultMessage }}</strong>
            <span v-if="order?.account">账号：{{ order.account }}</span>
          </div>

          <div class="action-row submit-action-row">
            <el-button v-if="!succeeded" :loading="activating" type="primary" @click="handleActivate">提交充值</el-button>
            <el-button v-if="processing" :loading="rechecking" @click="handleRecheck">刷新状态</el-button>
            <el-button :disabled="activating" @click="resetAll">更换卡密</el-button>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, ref } from 'vue';
import { activateClaude, verifyClaudeCard, type ClaudeActivateResult, type ClaudeCard } from '../api/claude';
import BrandLogo from '../components/BrandLogo.vue';

const cardCode = ref('');
const card = ref<ClaudeCard | null>(null);
const verifying = ref(false);
const currentStep = ref(0);

const uid = ref('');
const activating = ref(false);
const rechecking = ref(false);
const order = ref<ClaudeActivateResult | null>(null);
const resultMessage = ref('');
const lastUseStatus = ref<number | null>(null);

const activeStep = computed(() => currentStep.value);
const succeeded = computed(() => lastUseStatus.value === 1);
const processing = computed(() => lastUseStatus.value === -1);

const USE_STATUS_TEXT: Record<number, string> = {
  0: '待提交',
  [-1]: '处理中',
  1: '已完成',
  [-9]: '库存不足',
  [-999]: '异常',
  [-1000]: '已作废',
  [-1001]: '售后处理',
};
const useStatusText = computed(() => {
  const s = card.value?.useStatus;
  return s == null ? '-' : (USE_STATUS_TEXT[s] ?? String(s));
});

const stepEyebrow = computed(() => `Step ${String(activeStep.value + 1).padStart(2, '0')}`);
const stepTitle = computed(() => (activeStep.value === 0 ? '校验外部码' : '提交充值'));
const progressValue = computed(() => {
  if (activeStep.value === 0) return card.value ? 50 : 14;
  if (succeeded.value) return 100;
  return processing.value ? 84 : 72;
});
const stepTagText = computed(() => {
  if (activeStep.value === 0) return card.value ? card.value.giftName || '已校验' : '待校验';
  if (succeeded.value) return '充值成功';
  if (processing.value) return '处理中';
  return '待提交';
});
const stepTagType = computed(() => {
  if (activeStep.value === 0) return card.value ? 'success' : 'info';
  if (succeeded.value) return 'success';
  if (processing.value) return 'warning';
  return 'info';
});
const resultClass = computed(() =>
  succeeded.value ? 'is-success' : processing.value ? 'is-processing' : 'is-failed',
);

async function handleVerify() {
  if (!cardCode.value) {
    ElMessage.warning('请输入外部码');
    return;
  }
  verifying.value = true;
  try {
    const { card: c } = await verifyClaudeCard(cardCode.value);
    card.value = c;
    lastUseStatus.value = c.useStatus ?? null;
    resultMessage.value = '';
    order.value = null;
    currentStep.value = 1;
    ElMessage.success('校验通过');
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifying.value = false;
  }
}

async function handleActivate() {
  if (!uid.value) {
    ElMessage.warning('请输入 Organization ID（uid）');
    return;
  }
  activating.value = true;
  try {
    const r = await activateClaude(cardCode.value, uid.value);
    order.value = r.order;
    lastUseStatus.value = r.order?.useStatus ?? (r.ok ? 1 : lastUseStatus.value);
    resultMessage.value = r.message || (r.ok ? '充值成功' : '提交失败');
    if (r.ok && lastUseStatus.value === 1) {
      ElMessage.success('充值成功');
    } else if (processing.value) {
      ElMessage.info('订单处理中，请稍后刷新状态');
    } else {
      ElMessage.warning(r.message || '提交未成功');
    }
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    activating.value = false;
  }
}

async function handleRecheck() {
  rechecking.value = true;
  try {
    const { card: c, message } = await verifyClaudeCard(cardCode.value);
    card.value = c;
    lastUseStatus.value = c.useStatus ?? null;
    if (c.useStatus === 1) {
      resultMessage.value = '充值成功';
      ElMessage.success('充值成功');
    } else if (c.useStatus === -1) {
      ElMessage.info('仍在处理中，请稍后再刷新');
    } else {
      resultMessage.value = c.statusHint || message || '';
    }
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    rechecking.value = false;
  }
}

function resetAll() {
  card.value = null;
  cardCode.value = '';
  uid.value = '';
  order.value = null;
  resultMessage.value = '';
  lastUseStatus.value = null;
  currentStep.value = 0;
}
</script>

<style scoped>
.claude-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--recharge-muted);
}
.step-summary.is-success strong {
  color: var(--recharge-green);
}
.step-summary.is-processing strong {
  color: var(--recharge-blue);
}
.step-summary.is-failed strong {
  color: #c0392b;
}
.step-summary span {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  color: var(--recharge-muted);
}
</style>
