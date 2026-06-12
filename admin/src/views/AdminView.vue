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
          <el-tab-pane label="Claude卡密" name="claude" />
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

      <!-- ===== Claude 卡密 ===== -->
      <template v-else>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="Claude cdkey（每行一个，最多 500）">
            <el-input
              v-model="claudeImportRaw"
              type="textarea"
              :rows="4"
              resize="vertical"
              placeholder="XXXXX-XXXXX-XXXXX"
            />
          </el-form-item>
          <el-form-item label="备注（可选）">
            <el-input v-model.trim="claudeImportNote" maxlength="255" placeholder="例如 批次/来源" style="max-width: 360px" />
          </el-form-item>
          <el-button :loading="claudeImporting" type="primary" @click="handleClaudeImport">导入并生成外部码</el-button>
        </el-form>

        <template v-if="claudeImportResults.length">
          <div class="admin-result-bar">
            <span>导入结果</span>
            <strong>新建 {{ claudeImportCreated }} / 共 {{ claudeImportResults.length }}</strong>
            <el-button size="small" @click="copyNewClaudeExternals">复制全部新外部码</el-button>
          </div>
          <el-table :data="claudeImportResults" border size="small" empty-text="无结果">
            <el-table-column label="cdkey" min-width="200" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ row.realCard || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="外部码" min-width="170">
              <template #default="{ row }"><span class="mono">{{ row.externalCode || '-' }}</span></template>
            </el-table-column>
            <el-table-column label="商品" width="120">
              <template #default="{ row }">{{ row.giftName || '-' }}</template>
            </el-table-column>
            <el-table-column label="结果" width="90">
              <template #default="{ row }">
                <el-tag :type="claudeImportTagType(row.status)" size="small">{{ claudeImportLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.message || '-' }}</template>
            </el-table-column>
          </el-table>
        </template>

        <!-- 批量反查原始 cdkey -->
        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">Lookup</p><h3>批量反查原始卡密</h3></div>
        </div>
        <el-form label-position="top" @submit.prevent>
          <el-form-item label="外部码（每行一个，反查对应原始 cdkey，最多 500）">
            <el-input v-model="claudeLookupRaw" type="textarea" :rows="4" resize="vertical" placeholder="CL 开头外部码，每行一个" />
          </el-form-item>
          <el-button :loading="claudeLookupLoading" type="primary" @click="handleClaudeLookup">查询并反查原始卡密</el-button>
        </el-form>

        <template v-if="claudeLookupResults.length">
          <div class="admin-result-bar">
            <span>反查结果</span>
            <strong>命中 {{ claudeLookupFound }} / 共 {{ claudeLookupResults.length }}</strong>
            <el-button size="small" @click="copyLookupReals(claudeLookupResults)">复制全部原始卡密</el-button>
          </div>
          <el-table :data="claudeLookupResults" border size="small" empty-text="无结果">
            <el-table-column label="输入外部码" min-width="150">
              <template #default="{ row }"><span class="mono">{{ row.input }}</span></template>
            </el-table-column>
            <el-table-column label="原始 cdkey" min-width="220" show-overflow-tooltip>
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
          <div><p class="kicker">Claude Cards</p><h3>Claude 卡密列表</h3></div>
          <div class="admin-toolbar">
            <el-input v-model.trim="claudeSearch" placeholder="搜外部码" style="width: 160px" clearable @keyup.enter="loadClaudeMappings" />
            <el-button :loading="claudeLoading" @click="loadClaudeMappings">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="claudeLoading" :data="claudeMappings" border empty-text="暂无 Claude 卡密">
          <el-table-column label="外部码" min-width="170">
            <template #default="{ row }">
              <span class="mono">{{ row.externalCode }}</span>
              <el-button link type="primary" size="small" @click="copyText(row.externalCode)">复制</el-button>
            </template>
          </el-table-column>
          <el-table-column label="原始 cdkey" min-width="200" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.realCard || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="商品" width="120">
            <template #default="{ row }">{{ row.giftName || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="mappingStatusType(row.status)" size="small">{{ mappingStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.note || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <template v-if="row.status !== 'reissued'">
                <el-button link type="primary" size="small" @click="toggleClaudeStatus(row)">
                  {{ row.status === 'active' ? '停用' : '启用' }}
                </el-button>
                <el-button link type="warning" size="small" @click="reissueClaudeMappingRow(row)">重新生成</el-button>
              </template>
              <el-button link type="danger" size="small" @click="removeClaudeMapping(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- Claude 充值记录 -->
        <div class="admin-card__head admin-section-gap">
          <div><p class="kicker">Orders</p><h3>Claude 充值记录</h3></div>
          <div class="admin-toolbar">
            <el-input v-model.trim="claudeOrderSearch" placeholder="搜外部码/uid/账号" style="width: 200px" clearable @keyup.enter="loadClaudeOrders" />
            <el-button :loading="claudeOrdersLoading" @click="loadClaudeOrders">刷新</el-button>
          </div>
        </div>
        <el-table v-loading="claudeOrdersLoading" :data="claudeOrders" border empty-text="暂无充值记录">
          <el-table-column label="外部码" min-width="150">
            <template #default="{ row }"><span class="mono">{{ row.externalCode || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="uid" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><span class="mono">{{ row.uid || '-' }}</span></template>
          </el-table-column>
          <el-table-column label="商品" width="110">
            <template #default="{ row }">{{ row.giftName || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="claudeOrderTagType(row.status)" size="small">{{ claudeOrderLabel(row.status) }}</el-tag>
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
  lookupMappings,
  lookupSmsMappings,
  reissueMapping,
  reissueSmsMapping,
  setAdminToken,
  updateMappingStatus,
  updateSmsMappingStatus,
  importClaudeMappings,
  listClaudeMappings,
  lookupClaudeMappings,
  updateClaudeMappingStatus,
  reissueClaudeMapping,
  deleteClaudeMapping,
  listClaudeOrders,
  type ImportResultItem,
  type LookupResultItem,
  type MappingItem,
  type OrderItem,
  type SmsImportResultItem,
  type SmsMappingItem,
  type ClaudeImportResultItem,
  type ClaudeMappingItem,
  type ClaudeOrderItem,
} from '../api/admin';

const authed = ref(false);
const tokenInput = ref('');
const loggingIn = ref(false);
const activeTab = ref<'mappings' | 'orders' | 'sms' | 'claude'>('mappings');

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

// Claude Pro 卡密
const claudeImportRaw = ref('');
const claudeImportNote = ref('');
const claudeImporting = ref(false);
const claudeImportResults = ref<ClaudeImportResultItem[]>([]);
const claudeImportCreated = ref(0);
const claudeMappings = ref<ClaudeMappingItem[]>([]);
const claudeLoading = ref(false);
const claudeSearch = ref('');
const claudeLookupRaw = ref('');
const claudeLookupLoading = ref(false);
const claudeLookupResults = ref<LookupResultItem[]>([]);
const claudeLookupFound = computed(() => claudeLookupResults.value.filter((r) => r.found).length);
const claudeOrders = ref<ClaudeOrderItem[]>([]);
const claudeOrdersLoading = ref(false);
const claudeOrderSearch = ref('');

const tabCountLabel = computed(() => {
  if (activeTab.value === 'orders') return `记录 ${orders.value.length}`;
  if (activeTab.value === 'sms') return `接码卡密 ${smsMappings.value.length}`;
  if (activeTab.value === 'claude') return `Claude ${claudeMappings.value.length}`;
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
}

function onTabChange() {
  if (activeTab.value === 'orders' && !orders.value.length) {
    void loadOrders();
  }
  if (activeTab.value === 'sms' && !smsMappings.value.length) {
    void loadSmsMappings();
  }
  if (activeTab.value === 'claude' && !claudeMappings.value.length) {
    void loadClaudeMappings();
    void loadClaudeOrders();
  }
}

// ===== Claude Pro 卡密管理 =====
function claudeImportLabel(status: string) {
  return { created: '已生成', exists: '已存在', duplicate: '重复' }[status] || status;
}
function claudeImportTagType(status: string) {
  return { created: 'success', exists: 'warning', duplicate: 'info' }[status] || 'info';
}
const CLAUDE_USE_STATUS: Record<number, string> = {
  0: '待提交',
  [-1]: '处理中',
  1: '已完成',
  [-9]: '库存不足',
  [-999]: '异常',
  [-1000]: '已作废',
  [-1001]: '售后处理',
};
function claudeUseStatusLabel(useStatus: number) {
  return CLAUDE_USE_STATUS[useStatus] ?? String(useStatus ?? '-');
}
function claudeOrderTagType(status: string) {
  if (status === 'SUCCEEDED') return 'success';
  if (status === 'FAILED') return 'danger';
  if (status === 'PROCESSING') return 'warning';
  return 'info';
}
function claudeOrderLabel(status: string) {
  return { SUCCEEDED: '充值成功', PROCESSING: '处理中', FAILED: '失败', PENDING: '待处理' }[status] || status;
}

function copyNewClaudeExternals() {
  const codes = claudeImportResults.value
    .filter((r) => r.status === 'created' && r.externalCode)
    .map((r) => r.externalCode as string);
  if (!codes.length) {
    ElMessage.warning('没有新生成的外部码');
    return;
  }
  void copyText(codes.join('\n'));
}

async function handleClaudeImport() {
  const cards = Array.from(new Set(claudeImportRaw.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)));
  if (!cards.length) {
    ElMessage.warning('请至少输入一个 cdkey');
    return;
  }
  claudeImporting.value = true;
  try {
    const r = await importClaudeMappings(cards, claudeImportNote.value);
    claudeImportResults.value = r.results;
    claudeImportCreated.value = r.created;
    ElMessage.success(`导入完成，新建 ${r.created} 条`);
    claudeImportRaw.value = '';
    await loadClaudeMappings();
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    claudeImporting.value = false;
  }
}

async function handleClaudeLookup() {
  const codes = Array.from(new Set(claudeLookupRaw.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)));
  if (!codes.length) {
    ElMessage.warning('请至少输入一个外部码');
    return;
  }
  claudeLookupLoading.value = true;
  try {
    claudeLookupResults.value = await lookupClaudeMappings(codes);
    ElMessage.success(`反查完成，命中 ${claudeLookupFound.value} / ${claudeLookupResults.value.length}`);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    claudeLookupLoading.value = false;
  }
}

async function loadClaudeMappings() {
  claudeLoading.value = true;
  try {
    claudeMappings.value = await listClaudeMappings(claudeSearch.value);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    claudeLoading.value = false;
  }
}

async function toggleClaudeStatus(row: ClaudeMappingItem) {
  const next = row.status === 'active' ? 'disabled' : 'active';
  try {
    await updateClaudeMappingStatus(row.id, next);
    row.status = next;
    ElMessage.success('已更新');
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function reissueClaudeMappingRow(row: ClaudeMappingItem) {
  try {
    await ElMessageBox.confirm(
      `确认为外部码 ${row.externalCode} 重新生成新码？旧码将立即失效，新码指向同一张真实 cdkey。`,
      '重新生成确认',
      { type: 'warning', confirmButtonText: '确认生成' },
    );
  } catch {
    return;
  }
  try {
    const next = await reissueClaudeMapping(row.id);
    await loadClaudeMappings();
    ElMessage.success(next ? `已生成新外部码 ${next}` : '已重新生成');
    if (next) void copyText(next);
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function removeClaudeMapping(row: ClaudeMappingItem) {
  try {
    await ElMessageBox.confirm(`确认删除外部码 ${row.externalCode} 的映射？`, '删除确认', { type: 'warning' });
  } catch {
    return;
  }
  try {
    await deleteClaudeMapping(row.id);
    claudeMappings.value = claudeMappings.value.filter((m) => m.id !== row.id);
    ElMessage.success('已删除');
  } catch (error) {
    ElMessage.error((error as Error).message);
  }
}

async function loadClaudeOrders() {
  claudeOrdersLoading.value = true;
  try {
    claudeOrders.value = await listClaudeOrders(claudeOrderSearch.value);
  } catch (error) {
    ElMessage.error((error as Error).message);
  } finally {
    claudeOrdersLoading.value = false;
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
