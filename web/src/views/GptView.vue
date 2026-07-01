<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">GPT Recharge</p>
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
          <span>{{ t('gpt.product') }}</span>
          <strong>{{ card?.giftName || t('gpt.pendingVerify') }}</strong>
          <em>{{ card ? t('gpt.cardReady') : t('gpt.verifyFirst') }}</em>
        </div>

        <ol class="submit-steps">
          <li :class="{ active: activeStep === 0, done: Boolean(card) }">
            <span>1</span>
            <div>
              <strong>{{ t('gpt.step1Title') }}</strong>
              <small>{{ card ? t('gpt.gotProduct') : t('gpt.step1Desc') }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 1, done: succeeded }">
            <span>2</span>
            <div>
              <strong>{{ t('gpt.step2Title') }}</strong>
              <small>{{ succeeded ? t('gpt.success') : t('gpt.step2Desc') }}</small>
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
            <el-input v-model.trim="cardCode" :placeholder="t('gpt.cardPlaceholder')" clearable @keyup.enter="handleVerify" />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="verifying" type="primary" @click="handleVerify">{{ t('gpt.step1Title') }}</el-button>
          </div>
        </el-form>

        <!-- Step 2: 提交激活 -->
        <div v-else class="submit-review">
          <div class="review-grid">
            <div>
              <span>{{ t('gpt.product') }}</span>
              <strong>{{ card?.giftName || '-' }}</strong>
            </div>
            <div>
              <span>{{ t('gpt.cardStatus') }}</span>
              <strong>{{ card?.statusHint || useStatusText }}</strong>
            </div>
          </div>

          <!-- 如何获取 Session JSON 引导 -->
          <div class="gpt-guide">
            <strong class="gpt-guide__title">{{ t('gpt.getSessionTitle') }}</strong>
            <ol class="gpt-guide__steps">
              <li v-html="t('gpt.sessionStep1')"></li>
              <li v-html="t('gpt.sessionStep2')"></li>
              <li>{{ t('gpt.sessionStep3') }}</li>
            </ol>
          </div>

          <el-form label-position="top" @submit.prevent>
            <el-form-item :label="t('gpt.sessionLabel')">
              <el-input
                v-model="sessionInfo"
                type="textarea"
                :rows="8"
                resize="vertical"
                :placeholder="t('gpt.sessionPlaceholder')"
              />
            </el-form-item>
            <el-checkbox v-model="force">{{ t('gpt.forceLabel') }}</el-checkbox>
            <p class="gpt-force-hint">{{ t('gpt.forceHint') }}</p>
          </el-form>

          <!-- 结果提示 -->
          <div v-if="resultMessage" class="step-summary" :class="resultClass">
            <strong>{{ resultMessage }}</strong>
            <span v-if="order?.account">{{ t('gpt.accountPrefix') }}{{ order.account }}</span>
          </div>

          <div class="action-row submit-action-row">
            <el-button v-if="!succeeded" :loading="activating" type="primary" @click="handleActivate">{{ t('gpt.step2Title') }}</el-button>
            <el-button v-if="processing" :loading="rechecking" @click="handleRecheck">{{ t('gpt.refresh') }}</el-button>
            <el-button :disabled="activating" @click="resetAll">{{ t('gpt.changeCard') }}</el-button>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { activateGpt, verifyGptCard, type GptActivateResult, type GptCard } from '../api/gpt';
import BrandLogo from '../components/BrandLogo.vue';

const { t } = useI18n();

const cardCode = ref('');
const card = ref<GptCard | null>(null);
const verifying = ref(false);
const currentStep = ref(0);

const sessionInfo = ref('');
const force = ref(false);
const activating = ref(false);
const rechecking = ref(false);
const order = ref<GptActivateResult | null>(null);
const resultMessage = ref('');
const lastUseStatus = ref<number | null>(null);

const activeStep = computed(() => currentStep.value);
const succeeded = computed(() => lastUseStatus.value === 1);
const processing = computed(() => lastUseStatus.value === -1);

// use_status 数值 → locale 键
const USE_STATUS_KEY: Record<number, string> = {
  0: 'pending',
  [-1]: 'processing',
  1: 'done',
  [-9]: 'outOfStock',
  [-999]: 'error',
  [-1000]: 'voided',
  [-1001]: 'aftersale',
};
const useStatusText = computed(() => {
  const s = card.value?.useStatus;
  if (s == null) return '-';
  const k = USE_STATUS_KEY[s];
  return k ? t(`gpt.use.${k}`) : String(s);
});

const stepEyebrow = computed(() => `Step ${String(activeStep.value + 1).padStart(2, '0')}`);
const stepTitle = computed(() => (activeStep.value === 0 ? t('gpt.step1Title') : t('gpt.step2Title')));
const progressValue = computed(() => {
  if (activeStep.value === 0) return card.value ? 50 : 14;
  if (succeeded.value) return 100;
  return processing.value ? 84 : 72;
});
const stepTagText = computed(() => {
  if (activeStep.value === 0) return card.value ? card.value.giftName || t('gpt.verified') : t('gpt.pendingVerify');
  if (succeeded.value) return t('gpt.success');
  if (processing.value) return t('gpt.use.processing');
  return t('gpt.use.pending');
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
    ElMessage.warning(t('gpt.enterCard'));
    return;
  }
  verifying.value = true;
  try {
    const { card: c } = await verifyGptCard(cardCode.value);
    card.value = c;
    lastUseStatus.value = c.useStatus ?? null;
    resultMessage.value = '';
    order.value = null;
    currentStep.value = 1;
    ElMessage.success(t('gpt.verifyOk'));
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifying.value = false;
  }
}

async function handleActivate() {
  if (!sessionInfo.value.trim()) {
    ElMessage.warning(t('gpt.enterSession'));
    return;
  }
  activating.value = true;
  try {
    const r = await activateGpt(cardCode.value, sessionInfo.value, force.value);
    order.value = r.order;
    lastUseStatus.value = r.order?.useStatus ?? (r.ok ? 1 : lastUseStatus.value);
    resultMessage.value = r.message || (r.ok ? t('gpt.success') : t('gpt.submitFail'));
    if (r.ok && lastUseStatus.value === 1) {
      ElMessage.success(t('gpt.success'));
    } else if (processing.value) {
      ElMessage.info(t('gpt.processingTip'));
    } else {
      ElMessage.warning(r.message || t('gpt.submitNotOk'));
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
    const { card: c, message } = await verifyGptCard(cardCode.value);
    card.value = c;
    lastUseStatus.value = c.useStatus ?? null;
    if (c.useStatus === 1) {
      resultMessage.value = t('gpt.success');
      ElMessage.success(t('gpt.success'));
    } else if (c.useStatus === -1) {
      ElMessage.info(t('gpt.stillProcessing'));
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
  sessionInfo.value = '';
  force.value = false;
  order.value = null;
  resultMessage.value = '';
  lastUseStatus.value = null;
  currentStep.value = 0;
}
</script>

<style scoped>
.gpt-guide {
  margin: 4px 0 8px;
  padding: 14px 16px;
  border: 1px solid rgba(40, 103, 122, 0.18);
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fbfc, #f1f7fb);
}
.gpt-guide__title {
  font-size: 13px;
  color: var(--recharge-blue);
}
.gpt-guide__steps {
  margin: 10px 0 0;
  padding-left: 20px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--recharge-muted);
}
.gpt-guide__steps b {
  color: var(--recharge-ink, #1f2d3d);
}
.gpt-force-hint {
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
