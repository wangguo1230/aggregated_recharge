<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">74 Recharge</p>
        <h2>{{ t('vip.heroTitle') }}</h2>
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
            <h2>{{ t('vip.flowTitle') }}</h2>
          </div>
        </div>

        <div class="account-strip" :class="{ 'is-ready': step > 0 }">
          <span>{{ t('vip.product') }}</span>
          <strong>{{ cardCode || t('vip.pendingVerify') }}</strong>
          <em>{{ succeeded ? t('vip.success') : step > 0 ? t('vip.fillAccount') : t('vip.enterCardFirst') }}</em>
        </div>

        <ol class="submit-steps">
          <li :class="{ active: step === 0, done: step > 0 }">
            <span>1</span>
            <div>
              <strong>{{ t('vip.step1Title') }}</strong>
              <small>{{ step > 0 ? t('vip.gotCard') : t('vip.step1Desc') }}</small>
            </div>
          </li>
          <li :class="{ active: step === 1, done: succeeded }">
            <span>2</span>
            <div>
              <strong>{{ t('vip.step2Title') }}</strong>
              <small>{{ succeeded ? t('vip.success') : t('vip.step2Desc') }}</small>
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
          <el-tag :type="succeeded ? 'success' : 'info'">{{ succeeded ? t('vip.success') : t('vip.pendingVerify') }}</el-tag>
        </div>

        <!-- Step 1: 卡密 -->
        <el-form v-if="step === 0" label-position="top" @submit.prevent>
          <el-form-item :label="t('vip.cardLabel')">
            <el-input v-model.trim="cardCode" :placeholder="t('vip.cardPlaceholder')" clearable @keyup.enter="goNext" />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button type="primary" @click="goNext">{{ t('vip.next') }}</el-button>
          </div>
        </el-form>

        <!-- Step 2: 账号 JSON + 充值 -->
        <div v-else class="submit-review">
          <div class="step-summary">
            <span>{{ t('vip.cardLabel') }}</span>
            <strong class="mono">{{ cardCode }}</strong>
          </div>

          <div class="gpt-guide">
            <strong class="gpt-guide__title">{{ t('vip.getAccountTitle') }}</strong>
            <ol class="gpt-guide__steps">
              <li v-html="t('vip.accountStep1')"></li>
              <li v-html="t('vip.accountStep2')"></li>
              <li>{{ t('vip.accountStep3') }}</li>
            </ol>
          </div>

          <el-form label-position="top" @submit.prevent>
            <el-form-item :label="t('vip.accountLabel')">
              <el-input
                v-model="account"
                type="textarea"
                :rows="8"
                resize="vertical"
                :placeholder="t('vip.accountPlaceholder')"
              />
            </el-form-item>
          </el-form>

          <div v-if="resultMessage" class="step-summary" :class="succeeded ? 'is-success' : 'is-failed'">
            <strong>{{ resultMessage }}</strong>
            <span v-if="resultAccount">{{ t('vip.accountPrefix') }}{{ resultAccount }}</span>
          </div>

          <div class="action-row submit-action-row">
            <el-button @click="goPrev">{{ t('vip.prev') }}</el-button>
            <el-button :loading="verifying" @click="handleVerify">{{ t('vip.verifyBtn') }}</el-button>
            <el-button v-if="!succeeded" :loading="recharging" type="primary" @click="handleRecharge">{{ t('vip.rechargeBtn') }}</el-button>
            <el-button v-else @click="resetAll">{{ t('vip.again') }}</el-button>
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
import { activateVip, verifyVipCard } from '../api/vip';
import BrandLogo from '../components/BrandLogo.vue';

const { t } = useI18n();

const cardCode = ref('');
const account = ref('');
const step = ref(0);
const verifying = ref(false);
const recharging = ref(false);
const resultMessage = ref('');
const resultAccount = ref('');
const succeeded = ref(false);

const stepEyebrow = computed(() => `Step ${String(step.value + 1).padStart(2, '0')}`);
const stepTitle = computed(() => (step.value === 0 ? t('vip.step1Title') : t('vip.step2Title')));
const progressValue = computed(() => (step.value === 0 ? 20 : succeeded.value ? 100 : 64));

function goNext() {
  if (!cardCode.value.trim()) {
    ElMessage.warning(t('vip.enterCard'));
    return;
  }
  step.value = 1;
}

function goPrev() {
  step.value = 0;
}

async function handleVerify() {
  if (!account.value.trim()) {
    ElMessage.warning(t('vip.enterAccount'));
    return;
  }
  verifying.value = true;
  try {
    const msg = await verifyVipCard(cardCode.value, account.value);
    ElMessage.success(msg || t('vip.verifyOk'));
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifying.value = false;
  }
}

async function handleRecharge() {
  if (!account.value.trim()) {
    ElMessage.warning(t('vip.enterAccount'));
    return;
  }
  recharging.value = true;
  try {
    const r = await activateVip(cardCode.value, account.value);
    succeeded.value = r.ok;
    resultAccount.value = r.account;
    resultMessage.value = r.message || (r.ok ? t('vip.success') : t('vip.fail'));
    if (r.ok) {
      ElMessage.success(t('vip.success'));
    } else {
      ElMessage.warning(r.message || t('vip.fail'));
    }
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    recharging.value = false;
  }
}

function resetAll() {
  cardCode.value = '';
  account.value = '';
  step.value = 0;
  resultMessage.value = '';
  resultAccount.value = '';
  succeeded.value = false;
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
.step-summary.is-success strong {
  color: var(--recharge-green);
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
