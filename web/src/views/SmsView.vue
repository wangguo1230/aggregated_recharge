<template>
  <section class="submit-workbench">
    <div class="submit-hero">
      <div>
        <p class="eyebrow">10666 Recharge</p>
        <h2>{{ t('sms.heroTitle') }}</h2>
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
            <h2>{{ t('sms.flowTitle') }}</h2>
          </div>
        </div>

        <div class="account-strip" :class="{ 'is-ready': Boolean(card) }">
          <span>{{ t('sms.phone') }}</span>
          <strong>{{ card?.phone || t('sms.pendingVerify') }}</strong>
          <em>{{ card ? (latestCode ? t('sms.latestCodeIs', { code: latestCode }) : t('sms.bound')) : t('sms.verifyFirst') }}</em>
        </div>

        <ol class="submit-steps">
          <li :class="{ active: activeStep === 0, done: Boolean(card) }">
            <span>1</span>
            <div>
              <strong>{{ t('sms.step1Title') }}</strong>
              <small>{{ card ? t('sms.step1Done') : t('sms.step1Desc') }}</small>
            </div>
          </li>
          <li :class="{ active: activeStep === 1, done: Boolean(latestCode) }">
            <span>2</span>
            <div>
              <strong>{{ t('sms.step2Title') }}</strong>
              <small>{{ listening ? t('sms.listeningDots') : messages.length ? t('sms.received', { n: messages.length }) : t('sms.getCode') }}</small>
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

        <!-- Step 1: 校验兑换码 -->
        <el-form v-if="activeStep === 0" label-position="top" @submit.prevent>
          <el-form-item :label="t('sms.cardLabel')">
            <el-input v-model.trim="cardCode" :placeholder="t('sms.cardPlaceholder')" clearable @keyup.enter="handleVerify" />
          </el-form-item>
          <div class="action-row submit-action-row">
            <el-button :loading="verifying" type="primary" @click="handleVerify">{{ t('sms.verifyBtn') }}</el-button>
          </div>
        </el-form>

        <!-- Step 2: 接收短信 -->
        <div v-else class="submit-review">
          <div class="review-grid">
            <div>
              <span>{{ t('sms.phone') }}</span>
              <strong class="mono">{{ card?.phone || '-' }}</strong>
            </div>
            <div>
              <span>{{ t('sms.latestCode') }}</span>
              <strong class="mono sms-code-value">{{ latestCode || '-' }}</strong>
            </div>
            <div>
              <span>{{ t('sms.receivedSms') }}</span>
              <strong>{{ t('sms.count', { n: messages.length }) }}</strong>
            </div>
            <div>
              <span>{{ t('sms.currentStatus') }}</span>
              <strong>{{ statusText }}</strong>
            </div>
          </div>

          <!-- 监听中提示条 -->
          <div v-if="listening" class="sms-listening">
            <span class="sms-listening__dot"></span>
            <span>{{ t('sms.listeningTip') }}</span>
            <strong>{{ t('sms.remaining', { s: countdown }) }}</strong>
          </div>

          <div v-else class="session-guide">
            <p class="session-guide__title">{{ t('sms.guideTitle') }}</p>
            <ol>
              <li>{{ t('sms.guide1') }}</li>
              <li>{{ t('sms.guide2') }}</li>
              <li>{{ t('sms.guide3') }}</li>
            </ol>
          </div>

          <!-- 已收到的短信（仅有效短信，去重） -->
          <template v-for="(item, idx) in messages" :key="idx">
            <div class="step-summary">
              <span class="sms-record-content">{{ item.content }}</span>
            </div>
          </template>

          <div class="action-row submit-action-row">
            <el-button v-if="!listening" :type="messages.length ? 'default' : 'primary'" @click="startListening">
              {{ messages.length ? t('sms.retry') : t('sms.getCode') }}
            </el-button>
            <el-button v-else type="primary" loading disabled>{{ t('sms.listeningS', { s: countdown }) }}</el-button>
            <el-button v-if="listening" @click="stopListening">{{ t('sms.stop') }}</el-button>
            <el-button v-if="latestCode" type="success" plain @click="copyText(latestCode)">{{ t('sms.copyCode') }}</el-button>
            <el-button :disabled="listening" @click="resetAll">{{ t('sms.changeCard') }}</el-button>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { computed, onBeforeUnmount, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { fetchSms, verifySmsCard, type SmsCard } from '../api/sms';
import BrandLogo from '../components/BrandLogo.vue';

const { t } = useI18n();

interface SmsMessage {
  time: string;
  code: string;
  content: string;
}

// 自动监听：每隔 POLL_INTERVAL 查一次，最长等待 WAIT_SECONDS。
const POLL_INTERVAL = 4000;
const WAIT_SECONDS = 120;

const cardCode = ref('');
const card = ref<SmsCard | null>(null);
const verifying = ref(false);
const currentStep = ref(0);

// 仅保存「收到的有效短信」，按内容去重；暂无短信不入列表。
const messages = ref<SmsMessage[]>([]);
const seen = new Set<string>();
const listening = ref(false);
const countdown = ref(0);
let pollTimer: ReturnType<typeof setInterval> | undefined;
let countdownTimer: ReturnType<typeof setInterval> | undefined;

const activeStep = computed(() => currentStep.value);
const latestCode = computed(() => messages.value.find((m) => m.code)?.code || '');

const stepEyebrow = computed(() => `Step ${String(activeStep.value + 1).padStart(2, '0')}`);
const stepTitle = computed(() => (activeStep.value === 0 ? t('sms.step1Title') : t('sms.step2Title')));
const statusText = computed(() => {
  if (listening.value) return t('sms.statusListening', { s: countdown.value });
  if (latestCode.value) return t('sms.statusGot');
  return messages.value.length ? t('sms.statusWaiting') : t('sms.statusNone');
});
const progressValue = computed(() => {
  if (activeStep.value === 0) return card.value ? 50 : 14;
  if (latestCode.value) return 100;
  return listening.value ? 84 : 72;
});
const stepTagText = computed(() => {
  if (activeStep.value === 0) return card.value ? card.value.phone : t('sms.pendingVerify');
  if (latestCode.value) return t('sms.codeIs', { code: latestCode.value });
  if (listening.value) return t('sms.listening');
  return messages.value.length ? t('sms.receivedTag') : t('sms.pendingTag');
});
const stepTagType = computed(() => {
  if (activeStep.value === 0) return card.value ? 'success' : 'info';
  if (latestCode.value) return 'success';
  if (listening.value) return 'warning';
  return messages.value.length ? 'warning' : 'info';
});

async function handleVerify() {
  if (!cardCode.value) {
    ElMessage.warning(t('sms.enterCard'));
    return;
  }
  verifying.value = true;
  try {
    card.value = await verifySmsCard(cardCode.value);
    resetMessages();
    currentStep.value = 1;
    ElMessage.success(t('sms.verifyOk'));
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    verifying.value = false;
  }
}

async function pollOnce() {
  try {
    const result = await fetchSms(cardCode.value);
    const content = result.content.trim();
    // 仅在收到「未见过」的有效短信时入列表并结束本轮监听。
    if (result.hasSms && content && !seen.has(content)) {
      seen.add(content);
      messages.value.unshift({
        time: new Date().toLocaleTimeString(),
        code: result.code,
        content: result.content,
      });
      stopListening();
      ElMessage.success(result.code ? t('sms.gotCode', { code: result.code }) : t('sms.gotSms'));
    }
  } catch (error) {
    stopListening();
    ElMessage.error((error as Error).message);
  }
}

function startListening() {
  if (listening.value) return;
  listening.value = true;
  countdown.value = WAIT_SECONDS;
  void pollOnce();
  pollTimer = setInterval(() => {
    if (listening.value) void pollOnce();
  }, POLL_INTERVAL);
  countdownTimer = setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0) {
      stopListening();
      ElMessage.info(t('sms.roundTimeout'));
    }
  }, 1000);
}

function stopListening() {
  listening.value = false;
  if (pollTimer !== undefined) {
    clearInterval(pollTimer);
    pollTimer = undefined;
  }
  if (countdownTimer !== undefined) {
    clearInterval(countdownTimer);
    countdownTimer = undefined;
  }
}

function resetMessages() {
  stopListening();
  messages.value = [];
  seen.clear();
}

function resetAll() {
  resetMessages();
  card.value = null;
  cardCode.value = '';
  currentStep.value = 0;
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
      ElMessage.success(t('common.copied'));
      return;
    }
  } catch {
    // 安全上下文下仍失败则继续走兜底
  }
  if (fallbackCopy(text)) {
    ElMessage.success(t('common.copied'));
  } else {
    ElMessage.warning(t('common.copyFailed'));
  }
}

onBeforeUnmount(stopListening);
</script>

<style scoped>
/* 复用充值页 step-summary 容器，仅微调验证码与短信正文呈现 */
.sms-code-value {
  letter-spacing: 3px;
  color: var(--recharge-green);
}
.sms-record-content {
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.55;
}

/* 监听中提示条 */
.sms-listening {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid rgba(40, 103, 122, 0.22);
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fbfc, #f0f7fb);
  color: var(--recharge-blue);
  font-size: 13px;
  font-weight: 800;
}
.sms-listening strong {
  margin-left: auto;
  color: var(--recharge-blue);
  font-variant-numeric: tabular-nums;
}
.sms-listening__dot {
  width: 10px;
  height: 10px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--recharge-blue);
  box-shadow: 0 0 0 0 rgba(40, 103, 122, 0.45);
  animation: sms-pulse 1.3s ease-out infinite;
}
@keyframes sms-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(40, 103, 122, 0.4);
  }
  70% {
    box-shadow: 0 0 0 8px rgba(40, 103, 122, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(40, 103, 122, 0);
  }
}
</style>
