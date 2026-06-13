<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">Claude Recharge</p>
        <h2>{{ t('claude.heroTitle') }}</h2>
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
            <h2>{{ t('claude.flowTitle') }}</h2>
          </div>
        </div>

        <div class="account-strip" :class="{ 'is-ready': Boolean(card) }">
          <span>{{ t('claude.product') }}</span>
          <strong>{{ card?.giftName || t('claude.pendingVerify') }}</strong>
          <em>{{ card ? t('claude.cardReady') : t('claude.verifyFirst') }}</em>
        </div>

        <ol class="submit-steps">
          <li :class="{ active: activeStep === 0, done: Boolean(card) }">
            <span>1</span>
            <div>
              <strong>{{ t('claude.step1Title') }}</strong>
              <small>{{ card ? t('claude.gotProduct') : t('claude.step1Desc') }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 1, done: succeeded }">
            <span>2</span>
            <div>
              <strong>{{ t('claude.step2Title') }}</strong>
              <small>{{ succeeded ? t('claude.success') : t('claude.step2Desc') }}</small>
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
          <el-form-item :label="t('claude.cardLabel')">
            <el-input v-model.trim="cardCode" :placeholder="t('claude.cardPlaceholder')" clearable @keyup.enter="handleVerify" />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="verifying" type="primary" @click="handleVerify">{{ t('claude.step1Title') }}</el-button>
          </div>
        </el-form>

        <!-- Step 2: 提交激活 -->
        <div v-else class="submit-review">
          <div class="review-grid">
            <div>
              <span>{{ t('claude.product') }}</span>
              <strong>{{ card?.giftName || '-' }}</strong>
            </div>
            <div>
              <span>{{ t('claude.cardStatus') }}</span>
              <strong>{{ card?.statusHint || useStatusText }}</strong>
            </div>
          </div>

          <el-form label-position="top" @submit.prevent>
            <el-form-item :label="t('claude.uidLabel')">
              <el-input
                v-model.trim="uid"
                :placeholder="t('claude.uidPlaceholder')"
                clearable
                @keyup.enter="handleActivate"
              />
            </el-form-item>
          </el-form>

          <!-- 如何获取 Organization ID 引导 -->
          <div class="claude-guide">
            <div class="claude-guide__head">
              <strong>{{ t('claude.guideTitle') }}</strong>
              <a
                class="claude-guide__btn"
                href="https://claude.ai/new#settings/account"
                target="_blank"
                rel="noopener noreferrer"
              >{{ t('claude.openAccount') }}</a>
            </div>
            <ol class="claude-guide__steps">
              <li v-html="t('claude.guideStep1')"></li>
              <li v-html="t('claude.guideStep2')"></li>
              <li v-html="t('claude.guideStep3')"></li>
            </ol>
          </div>

          <!-- 结果提示 -->
          <div v-if="resultMessage" class="step-summary" :class="resultClass">
            <strong>{{ resultMessage }}</strong>
            <span v-if="order?.account">{{ t('claude.accountPrefix') }}{{ order.account }}</span>
          </div>

          <div class="action-row submit-action-row">
            <el-button v-if="!succeeded" :loading="activating" type="primary" @click="handleActivate">{{ t('claude.step2Title') }}</el-button>
            <el-button v-if="processing" :loading="rechecking" @click="handleRecheck">{{ t('claude.refresh') }}</el-button>
            <el-button :disabled="activating" @click="resetAll">{{ t('claude.changeCard') }}</el-button>
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
import { activateClaude, verifyClaudeCard, type ClaudeActivateResult, type ClaudeCard } from '../api/claude';
import BrandLogo from '../components/BrandLogo.vue';

const { t } = useI18n();

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
  return k ? t(`claude.use.${k}`) : String(s);
});

const stepEyebrow = computed(() => `Step ${String(activeStep.value + 1).padStart(2, '0')}`);
const stepTitle = computed(() => (activeStep.value === 0 ? t('claude.step1Title') : t('claude.step2Title')));
const progressValue = computed(() => {
  if (activeStep.value === 0) return card.value ? 50 : 14;
  if (succeeded.value) return 100;
  return processing.value ? 84 : 72;
});
const stepTagText = computed(() => {
  if (activeStep.value === 0) return card.value ? card.value.giftName || t('claude.verified') : t('claude.pendingVerify');
  if (succeeded.value) return t('claude.success');
  if (processing.value) return t('claude.use.processing');
  return t('claude.use.pending');
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
    ElMessage.warning(t('claude.enterCard'));
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
    ElMessage.success(t('claude.verifyOk'));
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifying.value = false;
  }
}

async function handleActivate() {
  if (!uid.value) {
    ElMessage.warning(t('claude.enterUid'));
    return;
  }
  activating.value = true;
  try {
    const r = await activateClaude(cardCode.value, uid.value);
    order.value = r.order;
    lastUseStatus.value = r.order?.useStatus ?? (r.ok ? 1 : lastUseStatus.value);
    resultMessage.value = r.message || (r.ok ? t('claude.success') : t('claude.submitFail'));
    if (r.ok && lastUseStatus.value === 1) {
      ElMessage.success(t('claude.success'));
    } else if (processing.value) {
      ElMessage.info(t('claude.processingTip'));
    } else {
      ElMessage.warning(r.message || t('claude.submitNotOk'));
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
      resultMessage.value = t('claude.success');
      ElMessage.success(t('claude.success'));
    } else if (c.useStatus === -1) {
      ElMessage.info(t('claude.stillProcessing'));
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
.claude-guide {
  margin: 4px 0 8px;
  padding: 14px 16px;
  border: 1px solid rgba(40, 103, 122, 0.18);
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fbfc, #f1f7fb);
}
.claude-guide__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.claude-guide__head strong {
  font-size: 13px;
  color: var(--recharge-blue);
}
.claude-guide__btn {
  font-size: 12px;
  font-weight: 800;
  color: #fff;
  background: var(--recharge-blue);
  padding: 6px 12px;
  border-radius: 999px;
  text-decoration: none;
  white-space: nowrap;
}
.claude-guide__btn:hover {
  opacity: 0.9;
}
.claude-guide__steps {
  margin: 10px 0 0;
  padding-left: 20px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--recharge-muted);
}
.claude-guide__steps b {
  color: var(--recharge-ink, #1f2d3d);
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
