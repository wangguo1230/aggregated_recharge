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
          <el-tab-pane label="GPT充值" name="gpt" />
          <el-tab-pane label="86GPT批量提交" name="gptbatch" />
          <el-tab-pane label="74批量提交" name="vipbatch" />
          <el-tab-pane label="软件订阅批量提交" name="softbatch" />
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

        <!-- 批量反查原始卡密：粘贴外部码 → 反查 realCard，可一键复制 -->
        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">Lookup</p><h3>批量反查原始卡密</h3></div>
        </div>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="外部码（每行一个，反查对应原始卡密，最多 500）">
            <el-input v-model="lookupRaw" type="textarea" :rows="4" resize="vertical" placeholder="AW 开头外部码，每行一个" />
          </el-form-item>
          <el-button :loading="lookupLoading" type="primary" @click="handleLookup">查询并反查原始卡密</el-button>
        </el-form>

        <template v-if="lookupResults.length">
          <div class="admin-result-bar">
            <span>反查结果</span>
            <strong>命中 {{ lookupFound }} / 共 {{ lookupResults.length }}</strong>
            <el-button size="small" @click="copyLookupReals(lookupResults)">复制全部原始卡密</el-button>
            <el-button size="small" @click="copyLookupDual(lookupResults)">复制双码</el-button>
            <el-button size="small" type="primary" plain @click="exportLookupDual(lookupResults)">导出双码CSV</el-button>
          </div>
          <el-table :data="lookupResults" border size="small" empty-text="无结果">
            <el-table-column label="输入外部码" min-width="150">
              <template #default="{ row }"><span class="mono">{{ row.input }}</span></template>
            </el-table-column>
            <el-table-column label="原始卡密" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.found" class="mono">{{ row.realCard }}</span>
                <el-tag v-else type="info" size="small">未找到</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="套餐" width="100">
              <template #default="{ row }">{{ row.cardTypeLabel || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button v-if="row.found" link type="primary" size="small" @click="copyText(row.realCard)">复制</el-button>
                <span v-else>-</span>
              </template>
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
              <el-tag :type="mappingStatusType(row.status)" size="small">
                {{ mappingStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.note || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <template v-if="row.status !== 'reissued'">
                <el-button link type="primary" size="small" @click="toggleStatus(row)">
                  {{ row.status === 'active' ? '停用' : '启用' }}
                </el-button>
                <el-button link type="warning" size="small" @click="reissueMappingRow(row)">重新生成</el-button>
              </template>
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
      <template v-else-if="activeTab === 'sms'">
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

        <!-- 批量反查接码原始卡密：粘贴兑换码 → 反查 手机号----URL -->
        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">Lookup</p><h3>批量反查原始卡密</h3></div>
        </div>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="兑换码（每行一个，反查对应接码原始卡密，最多 500）">
            <el-input v-model="smsLookupRaw" type="textarea" :rows="4" resize="vertical" placeholder="SM 开头兑换码，每行一个" />
          </el-form-item>
          <el-button :loading="smsLookupLoading" type="primary" @click="handleSmsLookup">查询并反查原始卡密</el-button>
        </el-form>

        <template v-if="smsLookupResults.length">
          <div class="admin-result-bar">
            <span>反查结果</span>
            <strong>命中 {{ smsLookupFound }} / 共 {{ smsLookupResults.length }}</strong>
            <el-button size="small" @click="copyLookupReals(smsLookupResults)">复制全部原始卡密</el-button>
            <el-button size="small" @click="copyLookupDual(smsLookupResults)">复制双码</el-button>
            <el-button size="small" type="primary" plain @click="exportLookupDual(smsLookupResults)">导出双码CSV</el-button>
          </div>
          <el-table :data="smsLookupResults" border size="small" empty-text="无结果">
            <el-table-column label="输入兑换码" min-width="150">
              <template #default="{ row }"><span class="mono">{{ row.input }}</span></template>
            </el-table-column>
            <el-table-column label="手机号" min-width="130">
              <template #default="{ row }"><span class="mono">{{ row.phone || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="完整卡密（手机号----URL）" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.found" class="mono">{{ row.realCard }}</span>
                <el-tag v-else type="info" size="small">未找到</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button v-if="row.found" link type="primary" size="small" @click="copyText(row.realCard)">复制</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">SMS Cards</p><h3>接码卡密列表</h3></div>
          <div class="admin-toolbar">
            <span v-if="smsSelected.length" style="font-size: 13px; color: var(--recharge-muted)">已选 {{ smsSelected.length }}</span>
            <el-button :loading="smsBatching" :disabled="!smsSelected.length" size="small" @click="batchSms('enable')">批量启用</el-button>
            <el-button :loading="smsBatching" :disabled="!smsSelected.length" size="small" @click="batchSms('disable')">批量停用</el-button>
            <el-button :loading="smsBatching" :disabled="!smsSelected.length" size="small" type="danger" @click="batchSms('delete')">批量删除</el-button>
            <el-button size="small" type="primary" plain @click="exportSmsDual">导出双码CSV</el-button>
            <el-input v-model.trim="smsSearch" placeholder="搜兑换码/手机号" style="width: 180px" clearable @keyup.enter="loadSmsMappings" />
            <el-button :loading="smsLoading" @click="loadSmsMappings">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="smsLoading" :data="smsMappings" border empty-text="暂无接码卡密" @selection-change="onSmsSelectionChange">
          <el-table-column type="selection" width="44" />
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
              <el-tag :type="mappingStatusType(row.status)" size="small">
                {{ mappingStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.note || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <template v-if="row.status !== 'reissued'">
                <el-button link type="primary" size="small" @click="toggleSmsStatus(row)">
                  {{ row.status === 'active' ? '停用' : '启用' }}
                </el-button>
                <el-button link type="warning" size="small" @click="reissueSmsMappingRow(row)">重新生成</el-button>
              </template>
              <el-button link type="danger" size="small" @click="removeSmsMapping(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- 批量提交（多渠道复用：86GPT / 74 / 软件订阅）：上传 cdkey + 账号 JSON，后台并发逐条提交 -->
      <template v-if="isBatchTab">
        <div class="admin-card__head">
          <div><p class="kicker">Batch · {{ batchChannel }}</p><h3>{{ batchChannelLabel }} 批量提交</h3></div>
        </div>
        <p class="admin-hint">
          两种方式任选其一：①上传 <b>Excel/CSV</b>（第 1 列 = 卡密，第 2 列 = 账号；首行可为表头 <code>cdkey</code>/<code>account</code>）；
          ②文本域每行一条 <code>卡密----账号</code>（按首个 <code>----</code> 切分）。后台并发逐条提交并做到账确认；批内重复卡密/账号、非法账号、已用过的卡密会自动跳过（按渠道隔离）。
          <template v-if="batchChannel === 'gpt86'"><br />86 渠道「账号」可为 <b>Session JSON</b>，或 <b>账号行</b>（<code>邮箱----密码----xxx----rt.开头令牌</code>，系统自动用 rt 换取 token 并拼装）。</template>
        </p>
        <div class="admin-toolbar" style="margin-bottom: 10px">
          <input
            ref="gptBatchFileInput"
            type="file"
            accept=".xlsx,.xls,.csv"
            style="display: none"
            @change="handleGptBatchFile"
          />
          <el-button :loading="gptBatchParsing" @click="gptBatchFileInput?.click()">上传 Excel/CSV</el-button>
          <el-tag v-if="gptBatchFileItems.length" type="success" closable @close="clearGptBatchFile">
            {{ gptBatchFileName }}：已解析 {{ gptBatchFileItems.length }} 条
          </el-tag>
          <span v-else style="font-size: 12px; color: var(--recharge-muted)">未选择文件（或改用下方文本域）</span>
        </div>
        <el-input
          v-model="gptBatchRaw"
          type="textarea"
          :rows="6"
          resize="vertical"
          :disabled="gptBatchFileItems.length > 0"
          :placeholder="gptBatchFileItems.length ? '已使用上传的文件，如需手动输入请先清除文件' : 'cdkey----{&quot;accessToken&quot;:&quot;...&quot;,&quot;user&quot;:{&quot;email&quot;:&quot;a@b.com&quot;}}'"
        />
        <div class="admin-toolbar" style="margin-top: 10px">
          <el-checkbox v-if="batchChannel === 'gpt86'" v-model="gptBatchForce">强制提交（跳过套餐检查）</el-checkbox>
          <span style="font-size: 13px; color: var(--recharge-muted)">并发数</span>
          <el-input-number v-model="gptBatchConcurrency" :min="1" :max="10" size="small" controls-position="right" style="width: 110px" />
          <el-input v-model.trim="gptBatchNote" maxlength="255" placeholder="备注（可选，如批次/来源）" style="max-width: 260px" />
          <el-button :loading="gptBatchCreating" type="primary" @click="handleCreateGptBatch">创建批量任务</el-button>
        </div>
        <div v-if="gptBatchCreateSummary" class="admin-result-bar">
          <strong>{{ gptBatchCreateSummary }}</strong>
        </div>

        <!-- 批量任务列表 -->
        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">Tasks</p><h3>批量任务</h3></div>
          <div class="admin-toolbar">
            <el-input
              v-model.trim="gptBatchSearch"
              placeholder="搜备注/编号"
              style="width: 180px"
              clearable
              @keyup.enter="loadGptBatches"
              @clear="loadGptBatches"
            />
            <el-button :loading="gptBatchesLoading" @click="loadGptBatches">刷新/筛选</el-button>
          </div>
        </div>
        <el-table v-loading="gptBatchesLoading" :data="gptBatches" border empty-text="暂无批量任务">
          <el-table-column label="#" width="64">
            <template #default="{ row }">{{ row.id }}</template>
          </el-table-column>
          <el-table-column label="状态" width="150">
            <template #default="{ row }">
              <el-tag :type="gptBatchStatusType(row.status)" size="small">{{ gptBatchStatusLabel(row.status) }}</el-tag>
              <div v-if="row.status === 'RUNNING' && row.retryWaiting" style="font-size: 11px; color: #e6a23c; margin-top: 2px">
                重试等待中
              </div>
              <div v-else-if="row.status === 'RUNNING'" style="font-size: 11px; color: var(--recharge-muted); margin-top: 2px">
                并发 {{ row.concurrency }}·在跑 {{ row.inFlight }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="进度（成功/失败/处理中/待人工/跳过 · 共）" min-width="240">
            <template #default="{ row }">
              <span class="mono">{{ batchProgressText(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.note || '-' }}</template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openGptBatch(row.id)">查看</el-button>
              <el-button
                v-if="row.status === 'PAUSED'"
                link
                type="success"
                size="small"
                @click="handleResumeGptBatch(row.id)"
              >继续</el-button>
              <el-button
                v-if="row.status === 'RUNNING' || row.status === 'PENDING' || row.status === 'PAUSED'"
                link
                type="danger"
                size="small"
                @click="handleCancelGptBatch(row.id)"
              >取消</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 任务明细（含轮询）-->
        <template v-if="gptBatchDetail">
          <div class="admin-card__head admin-section-gap">
            <div>
              <p class="kicker">Detail</p>
              <h3>任务 #{{ gptBatchDetail.batch.id }} 明细 · {{ gptBatchStatusLabel(gptBatchDetail.batch.status) }}</h3>
            </div>
            <div class="admin-toolbar">
              <span v-if="gptBatchPolling" style="font-size: 13px; color: var(--recharge-muted)">自动刷新中…</span>
              <el-button
                v-if="gptBatchDetail.batch.status === 'PAUSED'"
                type="success"
                @click="handleResumeGptBatch(gptBatchDetail.batch.id)"
              >继续执行</el-button>
              <el-button
                v-if="gptBatchDetail.batch.status !== 'RUNNING' && (gptBatchDetail.batch.counts.FAILED || gptBatchDetail.batch.counts.SKIPPED || gptBatchDetail.batch.counts.NEEDS_REVIEW)"
                type="warning"
                plain
                @click="handleRetryFailed"
              >重试全部失败</el-button>
              <el-button
                v-if="['PENDING', 'RUNNING', 'PAUSED'].includes(gptBatchDetail.batch.status)"
                type="danger"
                plain
                @click="handleCancelGptBatch(gptBatchDetail.batch.id)"
              >取消</el-button>
              <el-button @click="handleExportBatch">导出CSV</el-button>
              <el-button :loading="gptBatchDetailLoading" @click="refreshGptBatchDetail">刷新</el-button>
              <el-button @click="closeGptBatch">关闭</el-button>
            </div>
          </div>
          <!-- 实时阶段横幅：当前在干什么 -->
          <div
            class="admin-result-bar"
            :style="
              gptBatchDetail.batch.status === 'PAUSED'
                ? 'background:#fef0f0;border-color:#fbc4c4'
                : gptBatchDetail.batch.retryWaiting
                  ? 'background:#fdf6ec;border-color:#f5dab1'
                  : ''
            "
          >
            <strong>{{ batchPhaseText(gptBatchDetail.batch) }}</strong>
          </div>
          <el-table :data="gptBatchDetail.items" border size="small" empty-text="无条目" max-height="420">
            <el-table-column label="#" width="56">
              <template #default="{ row }">{{ row.seq }}</template>
            </el-table-column>
            <el-table-column label="账号邮箱" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.email || '-' }}</template>
            </el-table-column>
            <el-table-column label="卡尾号" width="90">
              <template #default="{ row }"><span class="mono">{{ row.cdkeyLast4 || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="gptItemStatusType(row.status)" size="small">{{ gptItemStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="结果" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.resultMessage || '-' }}</template>
            </el-table-column>
            <el-table-column label="到账账号" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.account || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button
                  v-if="canRetryItem(row.status)"
                  link
                  :type="row.status === 'NEEDS_REVIEW' ? 'warning' : 'primary'"
                  size="small"
                  @click="handleRetryItem(row.seq, row.status)"
                >重新提交</el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </template>

      <!-- GPT 充值记录（GPT充值标签：单笔充值的对账记录）-->
      <template v-if="activeTab === 'gpt'">
        <div class="admin-card__head">
          <div><p class="kicker">Orders</p><h3>GPT 充值记录</h3></div>
          <div class="admin-toolbar">
            <el-input v-model.trim="gptOrderSearch" placeholder="搜卡尾号/账号" style="width: 200px" clearable @keyup.enter="loadGptOrders" />
            <el-button :loading="gptOrdersLoading" @click="loadGptOrders">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="gptOrdersLoading" :data="gptOrders" border empty-text="暂无充值记录">
          <el-table-column label="原始 cdkey" min-width="200" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.realCard || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="账号" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.account || '-' }}</template>
          </el-table-column>
          <el-table-column label="商品" width="110">
            <template #default="{ row }">{{ row.giftName || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="gptOrderTagType(row.status)" size="small">{{ gptOrderLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="结果" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.resultMessage || '-' }}</template>
          </el-table-column>
          <el-table-column label="提交时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </template>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus';
import { computed, onMounted, onUnmounted, ref, type Ref } from 'vue';
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
  lookupMappings,
  lookupSmsMappings,
  reissueMapping,
  reissueSmsMapping,
  setAdminToken,
  updateMappingStatus,
  updateSmsMappingStatus,
  listGptOrders,
  createGptBatch,
  listGptBatches,
  getGptBatch,
  cancelGptBatch,
  resumeGptBatch,
  retryGptBatchItem,
  retryFailedGptBatch,
  exportGptBatch,
  batchSmsMappings,
  type BatchAction,
  type ImportResultItem,
  type LookupResultItem,
  type MappingItem,
  type OrderItem,
  type SmsImportResultItem,
  type SmsMappingItem,
  type GptOrderItem,
  type GptBatchSummary,
  type GptBatchItem,
} from '../api/admin';

const authed = ref(false);
const tokenInput = ref('');
const loggingIn = ref(false);
const activeTab = ref<'mappings' | 'orders' | 'sms' | 'gpt' | 'gptbatch' | 'vipbatch' | 'softbatch'>('mappings');
// 当前批量标签对应的渠道。
const BATCH_TAB_CHANNEL: Record<string, string> = { gptbatch: 'gpt86', vipbatch: 'vip74', softbatch: 'soft' };
const BATCH_CHANNEL_LABEL: Record<string, string> = { gpt86: '86GPT', vip74: '74渠道', soft: '软件订阅' };
const isBatchTab = computed(() => activeTab.value in BATCH_TAB_CHANNEL);
const batchChannel = computed(() => BATCH_TAB_CHANNEL[activeTab.value] || 'gpt86');
const batchChannelLabel = computed(() => BATCH_CHANNEL_LABEL[batchChannel.value] || batchChannel.value);

const importRaw = ref('');
const importNote = ref('');
const importing = ref(false);
const importResults = ref<ImportResultItem[]>([]);
const importCreated = ref(0);

const mappings = ref<MappingItem[]>([]);
const loading = ref(false);
const search = ref('');

// 批量反查原始卡密（卡密映射）。
const lookupRaw = ref('');
const lookupLoading = ref(false);
const lookupResults = ref<LookupResultItem[]>([]);
const lookupFound = computed(() => lookupResults.value.filter((r) => r.found).length);

// 批量反查原始卡密（接码卡密）。
const smsLookupRaw = ref('');
const smsLookupLoading = ref(false);
const smsLookupResults = ref<LookupResultItem[]>([]);
const smsLookupFound = computed(() => smsLookupResults.value.filter((r) => r.found).length);

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
// 接码卡密列表多选（批量操作）。
const smsSelected = ref<SmsMappingItem[]>([]);
const smsBatching = ref(false);

const gptOrders = ref<GptOrderItem[]>([]);
const gptOrdersLoading = ref(false);
const gptOrderSearch = ref('');

// GPT 批量订阅
const gptBatchRaw = ref('');
const gptBatchForce = ref(false);
const gptBatchNote = ref('');
const gptBatchConcurrency = ref(1);
const gptBatchCreating = ref(false);
const gptBatchCreateSummary = ref('');
const gptBatches = ref<GptBatchSummary[]>([]);
const gptBatchesLoading = ref(false);
const gptBatchSearch = ref('');
const gptBatchDetail = ref<{ batch: GptBatchSummary; items: GptBatchItem[] } | null>(null);
const gptBatchDetailLoading = ref(false);
const gptBatchPolling = ref(false);
let gptBatchPollTimer: ReturnType<typeof setInterval> | undefined;
// Excel/CSV 上传解析结果（存在时优先于文本域）。
const gptBatchFileInput = ref<HTMLInputElement | null>(null);
const gptBatchParsing = ref(false);
const gptBatchFileItems = ref<{ cdkey: string; sessionInfo: string }[]>([]);
const gptBatchFileName = ref('');

const tabCountLabel = computed(() => {
  if (activeTab.value === 'orders') return `记录 ${orders.value.length}`;
  if (activeTab.value === 'sms') return `接码卡密 ${smsMappings.value.length}`;
  if (activeTab.value === 'gpt') return `GPT ${gptOrders.value.length}`;
  if (isBatchTab.value) return `批量任务 ${gptBatches.value.length}`;
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

// 反查结果一键复制全部原始卡密（卡密映射与接码卡密通用）。
function copyLookupReals(results: LookupResultItem[]) {
  const cards = results.filter((r) => r.found && r.realCard).map((r) => r.realCard);
  if (!cards.length) {
    ElMessage.warning('没有可复制的原始卡密');
    return;
  }
  void copyText(cards.join('\n'));
}

// 反查结果双码导出：两列——映射后码(输入的外部码) + 原码(反查出的真实卡密)。
function exportLookupDual(results: LookupResultItem[]) {
  const found = results.filter((r) => r.found && r.realCard);
  if (!found.length) {
    ElMessage.warning('没有命中的可导出');
    return;
  }
  const esc = (v: string) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = ['映射后码,原码', ...found.map((r) => `${esc(r.externalCode || r.input)},${esc(r.realCard)}`)];
  const content = '﻿' + lines.join('\r\n'); // BOM，Excel 中文不乱码
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `lookup-dual-${found.length}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  ElMessage.success(`已导出 ${found.length} 条（映射后码/原码）`);
}

// 复制双码：每行 映射后码----原码（接码即 新卡密----手机号----查询URL）。
function copyLookupDual(results: LookupResultItem[]) {
  const lines = results
    .filter((r) => r.found && r.realCard)
    .map((r) => `${r.externalCode || r.input}----${r.realCard}`);
  if (!lines.length) {
    ElMessage.warning('没有命中的可复制');
    return;
  }
  void copyText(lines.join('\n'));
}

async function handleLookup() {
  const codes = Array.from(new Set(lookupRaw.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)));
  if (!codes.length) {
    ElMessage.warning('请至少输入一个外部码');
    return;
  }
  lookupLoading.value = true;
  try {
    lookupResults.value = await lookupMappings(codes);
    ElMessage.success(`反查完成，命中 ${lookupFound.value} / ${lookupResults.value.length}`);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    lookupLoading.value = false;
  }
}

async function handleSmsLookup() {
  const codes = Array.from(new Set(smsLookupRaw.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)));
  if (!codes.length) {
    ElMessage.warning('请至少输入一个兑换码');
    return;
  }
  smsLookupLoading.value = true;
  try {
    smsLookupResults.value = await lookupSmsMappings(codes);
    ElMessage.success(`反查完成，命中 ${smsLookupFound.value} / ${smsLookupResults.value.length}`);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    smsLookupLoading.value = false;
  }
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
  lookupResults.value = [];
  smsMappings.value = [];
  smsImportResults.value = [];
  smsLookupResults.value = [];
  smsSelected.value = [];
}

function onTabChange() {
  if (activeTab.value === 'orders' && !orders.value.length) {
    void loadOrders();
  }
  if (activeTab.value === 'sms' && !smsMappings.value.length) {
    void loadSmsMappings();
  }
  if (activeTab.value === 'gpt' && !gptOrders.value.length) {
    void loadGptOrders();
  }
  if (isBatchTab.value) {
    // 切换批量标签（渠道）时清掉上一个渠道的明细/轮询/搜索，避免串台。
    closeGptBatch();
    gptBatchSearch.value = '';
    void loadGptBatches();
  }
}

// 订单状态标签（GPT 充值记录 / 批量明细复用）。
function gptOrderTagType(status: string) {
  if (status === 'SUCCEEDED') return 'success';
  if (status === 'FAILED') return 'danger';
  if (status === 'PROCESSING') return 'warning';
  return 'info';
}
function gptOrderLabel(status: string) {
  return { SUCCEEDED: '充值成功', PROCESSING: '处理中', FAILED: '失败', PENDING: '待处理' }[status] || status;
}

async function loadGptOrders() {
  gptOrdersLoading.value = true;
  try {
    gptOrders.value = await listGptOrders(gptOrderSearch.value);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    gptOrdersLoading.value = false;
  }
}

// ===== GPT 批量订阅 =====
const GPT_BATCH_STATUS: Record<string, string> = {
  PENDING: '待执行',
  RUNNING: '执行中',
  PAUSED: '已暂停',
  DONE: '已完成',
  CANCELLED: '已取消',
};
function gptBatchStatusLabel(status: string) {
  return GPT_BATCH_STATUS[status] || status;
}
function gptBatchStatusType(status: string) {
  return { RUNNING: 'warning', PAUSED: 'danger', DONE: 'success', CANCELLED: 'info', PENDING: 'info' }[status] || 'info';
}
// 实时阶段文案：当前在干什么。
function batchPhaseText(b: GptBatchSummary) {
  if (b.status === 'DONE') return '已完成';
  if (b.status === 'CANCELLED') return '已取消';
  if (b.status === 'PAUSED') return `已暂停（需处理）：${b.pausedReason || '遇到错误'}`;
  if (b.status === 'PENDING') return '排队中，等待执行…';
  if (b.retryWaiting) return `暂不可用（缺货/冷却/上游临时异常），按间隔重试中…（${b.inFlight} 条并发，并发数 ${b.concurrency}）`;
  return `执行中：${b.inFlight} 条并发处理中（并发数 ${b.concurrency}）`;
}
const GPT_ITEM_STATUS: Record<string, string> = {
  PENDING: '待处理',
  SUBMITTING: '提交中',
  SUCCEEDED: '成功',
  PROCESSING: '处理中',
  FAILED: '失败',
  SKIPPED: '跳过',
  NEEDS_REVIEW: '待人工确认',
};
function gptItemStatusLabel(status: string) {
  return GPT_ITEM_STATUS[status] || status;
}
function gptItemStatusType(status: string) {
  return (
    {
      SUCCEEDED: 'success',
      PROCESSING: 'warning',
      SUBMITTING: 'warning',
      FAILED: 'danger',
      NEEDS_REVIEW: 'danger',
      SKIPPED: 'info',
      PENDING: 'info',
    }[status] || 'info'
  );
}
function batchProgressText(row: GptBatchSummary) {
  const c = row.counts || {};
  const g = (k: string) => c[k] || 0;
  return `${g('SUCCEEDED')}/${g('FAILED')}/${g('PROCESSING')}/${g('NEEDS_REVIEW')}/${g('SKIPPED')} · 共 ${row.total}`;
}

// 解析文本域为 cdkey + sessionInfo 列表；遇到格式错误的行直接中止并提示行号。
function parseGptPairs(raw: string): { items: { cdkey: string; sessionInfo: string }[]; badLines: number[] } {
  const items: { cdkey: string; sessionInfo: string }[] = [];
  const badLines: number[] = [];
  const lines = raw.split(/\r?\n/);
  let lineNo = 0;
  for (const rawLine of lines) {
    lineNo += 1;
    const line = rawLine.trim();
    if (!line) continue;
    const idx = line.indexOf('----');
    if (idx <= 0) {
      badLines.push(lineNo);
      continue;
    }
    const cdkey = line.slice(0, idx).trim();
    const sessionInfo = line.slice(idx + 4).trim();
    if (!cdkey || !sessionInfo) {
      badLines.push(lineNo);
      continue;
    }
    items.push({ cdkey, sessionInfo });
  }
  return { items, badLines };
}

// 解析上传的 Excel/CSV：第 1 列卡密、第 2 列 SessionJSON，首行可为表头。
function parseSheetRows(rows: unknown[][]): { items: { cdkey: string; sessionInfo: string }[]; badRows: number[] } {
  const items: { cdkey: string; sessionInfo: string }[] = [];
  const badRows: number[] = [];
  const first = (rows[0] || []).map((c) => String(c ?? '').trim().toLowerCase());
  const looksLikeHeader = first.some(
    (c) => c.includes('cdkey') || c.includes('卡密') || c.includes('session') || c.includes('会话'),
  );
  const start = looksLikeHeader ? 1 : 0;
  for (let i = start; i < rows.length; i++) {
    const row = rows[i] || [];
    const cdkey = String(row[0] ?? '').trim();
    const sessionInfo = String(row[1] ?? '').trim();
    if (!cdkey && !sessionInfo) continue; // 空行
    if (!cdkey || !sessionInfo) {
      badRows.push(i + 1); // 残缺行（仅有卡密或仅有 Session）→ 报错，避免错配
      continue;
    }
    items.push({ cdkey, sessionInfo });
  }
  return { items, badRows };
}

async function handleGptBatchFile(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  gptBatchParsing.value = true;
  try {
    // 动态按需加载 xlsx，避免拖累首屏体积（仅批量 tab 用到）。
    const XLSX = await import('xlsx');
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: 'array' });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    if (!sheet) throw new Error('文件没有可读工作表');
    const rows = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, blankrows: false, defval: '' });
    const { items, badRows } = parseSheetRows(rows);
    if (badRows.length) {
      throw new Error(`第 ${badRows.slice(0, 10).join('、')} 行数据不完整（需同时有卡密和 SessionJSON）`);
    }
    if (!items.length) throw new Error('未解析到有效数据（第 1 列卡密、第 2 列 SessionJSON）');
    if (items.length > 500) throw new Error(`单次最多 500 条，当前 ${items.length} 条`);
    gptBatchFileItems.value = items;
    gptBatchFileName.value = file.name;
    gptBatchRaw.value = '';
    ElMessage.success(`已解析 ${items.length} 条`);
  } catch (error) {
    clearGptBatchFile();
    ElMessage.error((error as Error).message);
  } finally {
    gptBatchParsing.value = false;
    input.value = ''; // 允许再次选择同一文件
  }
}

function clearGptBatchFile() {
  gptBatchFileItems.value = [];
  gptBatchFileName.value = '';
}

async function handleCreateGptBatch() {
  // 文件解析结果优先；否则用文本域。
  let items: { cdkey: string; sessionInfo: string }[];
  if (gptBatchFileItems.value.length) {
    items = gptBatchFileItems.value;
  } else {
    const parsed = parseGptPairs(gptBatchRaw.value);
    if (parsed.badLines.length) {
      ElMessage.error(`第 ${parsed.badLines.slice(0, 10).join('、')} 行格式错误（应为 卡密----SessionJSON）`);
      return;
    }
    items = parsed.items;
  }
  if (!items.length) {
    ElMessage.warning('请上传文件或在文本域输入至少一条');
    return;
  }
  if (items.length > 500) {
    ElMessage.warning('单次最多 500 条');
    return;
  }
  gptBatchCreating.value = true;
  try {
    const r = await createGptBatch(
      items,
      batchChannel.value,
      batchChannel.value === 'gpt86' ? gptBatchForce.value : false,
      gptBatchNote.value,
      gptBatchConcurrency.value,
    );
    gptBatchCreateSummary.value = `任务 #${r.batchId} 已创建：待执行 ${r.accepted}，跳过 ${r.skipped}（共 ${r.total}）`;
    ElMessage.success(`已创建任务 #${r.batchId}`);
    gptBatchRaw.value = '';
    gptBatchNote.value = '';
    clearGptBatchFile();
    await loadGptBatches();
    if (r.accepted > 0) openGptBatch(r.batchId);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    gptBatchCreating.value = false;
  }
}

async function loadGptBatches() {
  gptBatchesLoading.value = true;
  try {
    gptBatches.value = await listGptBatches(batchChannel.value, gptBatchSearch.value);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    gptBatchesLoading.value = false;
  }
}

async function openGptBatch(id: number) {
  await refreshGptBatchDetail(id);
  // 打开时把并发滑块同步成该批当前并发；不动滑块=不改，动了重试才生效。
  if (gptBatchDetail.value) gptBatchConcurrency.value = gptBatchDetail.value.batch.concurrency || 1;
}

async function refreshGptBatchDetail(id?: number) {
  const batchId = id ?? gptBatchDetail.value?.batch.id;
  if (!batchId) return;
  gptBatchDetailLoading.value = true;
  try {
    gptBatchDetail.value = await getGptBatch(batchId);
    syncGptBatchPolling();
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    gptBatchDetailLoading.value = false;
  }
}

function closeGptBatch() {
  stopGptBatchPolling();
  gptBatchDetail.value = null;
}

// 任务进行中时自动轮询明细与列表；终态停止。
function syncGptBatchPolling() {
  const status = gptBatchDetail.value?.batch.status;
  const running = status === 'RUNNING' || status === 'PENDING';
  if (running && !gptBatchPollTimer) {
    gptBatchPolling.value = true;
    gptBatchPollTimer = setInterval(() => {
      void refreshGptBatchDetail();
      void loadGptBatches();
    }, 3000);
  } else if (!running) {
    stopGptBatchPolling();
  }
}

function stopGptBatchPolling() {
  if (gptBatchPollTimer !== undefined) {
    clearInterval(gptBatchPollTimer);
    gptBatchPollTimer = undefined;
  }
  gptBatchPolling.value = false;
}

async function handleCancelGptBatch(id: number) {
  try {
    await ElMessageBox.confirm('确认取消该批量任务？已在途的当前条目仍会落库，剩余条目将跳过。', '取消任务', {
      type: 'warning',
    });
  } catch {
    return;
  }
  try {
    await cancelGptBatch(id);
    ElMessage.success('已请求取消');
    await loadGptBatches();
    if (gptBatchDetail.value?.batch.id === id) await refreshGptBatchDetail(id);
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function handleResumeGptBatch(id: number) {
  try {
    await resumeGptBatch(id, gptBatchConcurrency.value);
    ElMessage.success('已继续执行');
    await loadGptBatches();
    if (gptBatchDetail.value?.batch.id === id) await refreshGptBatchDetail(id);
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

// 可重新提交的条目状态（成功/排队/处理中除外）。
function canRetryItem(status: string) {
  return ['FAILED', 'SKIPPED', 'NEEDS_REVIEW'].includes(status);
}

async function handleRetryItem(seq: number, status: string) {
  const batchId = gptBatchDetail.value?.batch.id;
  if (!batchId) return;
  let force = false;
  if (status === 'NEEDS_REVIEW') {
    try {
      await ElMessageBox.confirm(
        '该条目结果未知，可能已扣卡/已订阅。请先人工核实确认“未到账”后再强制重试，否则可能重复扣卡。确认强制重试？',
        '结果未知 · 强制重试',
        { type: 'warning', confirmButtonText: '已核实，强制重试', cancelButtonText: '取消' },
      );
      force = true;
    } catch {
      return;
    }
  }
  try {
    await retryGptBatchItem(batchId, seq, force, gptBatchConcurrency.value);
    ElMessage.success(`第 ${seq} 条已重新提交`);
    await refreshGptBatchDetail(batchId);
    await loadGptBatches();
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function handleRetryFailed() {
  const batchId = gptBatchDetail.value?.batch.id;
  if (!batchId) return;
  let includeReview = false;
  try {
    await ElMessageBox.confirm(
      '将把本批所有「失败/跳过」条目重置为待处理并继续执行（已被占用的卡密会自动跳过）。是否连「待人工确认」也一并重试？',
      '重试全部失败',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '含待人工确认',
        cancelButtonText: '仅失败/跳过',
        type: 'warning',
      },
    );
    includeReview = true;
  } catch (action) {
    if (action === 'close') return; // 右上角关闭 = 放弃
    includeReview = false; // 点了「仅失败/跳过」
  }
  try {
    const reset = await retryFailedGptBatch(batchId, includeReview, gptBatchConcurrency.value);
    ElMessage.success(`已重置 ${reset} 条并继续执行`);
    await refreshGptBatchDetail(batchId);
    await loadGptBatches();
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function handleExportBatch() {
  const batchId = gptBatchDetail.value?.batch.id;
  if (!batchId) return;
  try {
    await exportGptBatch(batchId);
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

onUnmounted(stopGptBatchPolling);

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

async function reissueSmsMappingRow(row: SmsMappingItem) {
  try {
    await ElMessageBox.confirm(
      `确认为兑换码 ${row.externalCode} 重新生成新码？旧码将立即失效，新码指向同一张接码卡密。`,
      '重新生成确认',
      { type: 'warning', confirmButtonText: '确认生成' },
    );
  } catch {
    return;
  }
  try {
    const next = await reissueSmsMapping(row.id);
    await loadSmsMappings();
    ElMessage.success(next ? `已生成新兑换码 ${next}` : '已重新生成');
    if (next) void copyText(next);
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

// ===== 列表批量操作（接码卡密）=====
const BATCH_LABELS: Record<BatchAction, string> = { enable: '启用', disable: '停用', delete: '删除' };

function onSmsSelectionChange(rows: SmsMappingItem[]) {
  smsSelected.value = rows;
}

// 统一的批量操作流程：校验勾选 → 删除前二次确认 → 调用接口 → 刷新列表。
async function runBatch<T extends { id: number }>(
  action: BatchAction,
  selected: T[],
  apiCall: (ids: number[], action: BatchAction) => Promise<number>,
  reload: () => Promise<void>,
  busy: Ref<boolean>,
) {
  if (!selected.length) {
    ElMessage.warning('请先勾选要操作的卡密');
    return;
  }
  const label = BATCH_LABELS[action];
  if (action === 'delete') {
    try {
      await ElMessageBox.confirm(`确认删除选中的 ${selected.length} 条卡密？此操作不可恢复。`, '批量删除确认', {
        type: 'warning',
        confirmButtonText: '确认删除',
      });
    } catch {
      return;
    }
  }
  busy.value = true;
  try {
    const affected = await apiCall(selected.map((r) => r.id), action);
    ElMessage.success(`已${label} ${affected} 条`);
    await reload();
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    busy.value = false;
  }
}

function batchSms(action: BatchAction) {
  void runBatch(action, smsSelected.value, batchSmsMappings, loadSmsMappings, smsBatching);
}

// 双码导出：选中则导选中，未选中则导全部；两列——原码(手机号----URL) + 映射后码(兑换码)。
function exportSmsDual() {
  const rows = smsSelected.value.length ? smsSelected.value : smsMappings.value;
  if (!rows.length) {
    ElMessage.warning('没有可导出的接码卡密');
    return;
  }
  const esc = (v: string) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = ['原码,映射后码', ...rows.map((r) => `${esc(r.realCard)},${esc(r.externalCode)}`)];
  const content = '﻿' + lines.join('\r\n'); // BOM，Excel 中文不乱码
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sms-dual-${rows.length}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  ElMessage.success(`已导出 ${rows.length} 条（原码/映射后码）`);
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

// 卡密映射 / 接码卡密通用的状态展示（active 启用 / disabled 停用 / reissued 已重发失效）。
function mappingStatusLabel(status: string) {
  return { active: '启用', disabled: '停用', reissued: '已重发' }[status] || status;
}
function mappingStatusType(status: string) {
  return { active: 'success', disabled: 'info', reissued: 'info' }[status] || 'info';
}

async function reissueMappingRow(row: MappingItem) {
  try {
    await ElMessageBox.confirm(
      `确认为外部码 ${row.externalCode} 重新生成新码？旧码将立即失效，新码指向同一张真实卡密。`,
      '重新生成确认',
      { type: 'warning', confirmButtonText: '确认生成' },
    );
  } catch {
    return;
  }
  try {
    const next = await reissueMapping(row.id);
    await loadMappings();
    ElMessage.success(next ? `已生成新外部码 ${next}` : '已重新生成');
    if (next) void copyText(next);
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
