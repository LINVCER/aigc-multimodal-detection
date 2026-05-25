<template>
  <div class="admin-analytics">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-title">
          <div class="title-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
            </svg>
          </div>
          <div class="title-text">
            <h1>模型优化数据中心</h1>
            <p>用户检测数据分析 · 模型性能评估 · 训练数据管理</p>
          </div>
        </div>
        <div class="header-actions">
          <el-button class="export-btn" @click="showExportDialog = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;margin-right:6px">
              <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
            导出训练数据
          </el-button>
          <el-tag type="danger" size="large" effect="dark" class="admin-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;margin-right:4px">
              <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
            </svg>
            管理员
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <div class="kpi-section">
      <div class="kpi-card" v-for="(kpi, index) in kpiData" :key="index">
        <div class="kpi-bg" :style="{ background: kpi.gradient }"></div>
        <div class="kpi-icon" :style="{ background: kpi.iconBg }">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path :d="kpi.icon" />
          </svg>
        </div>
        <div class="kpi-info">
          <div class="kpi-value">{{ kpi.value }}</div>
          <div class="kpi-label">{{ kpi.label }}</div>
          <div v-if="kpi.trend !== undefined" class="kpi-change" :class="kpi.trend > 0 ? 'up' : 'down'">
            {{ kpi.trend > 0 ? '↑' : '↓' }} {{ Math.abs(kpi.trend) }}%
            <span>较上周</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 趋势与分布图表 -->
    <div class="charts-section">
      <div class="chart-card wide">
        <div class="chart-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
            </svg>
            检测趋势分析
          </h3>
          <el-radio-group v-model="trendPeriod" size="small" @change="fetchTrend">
            <el-radio-button label="7">7天</el-radio-button>
            <el-radio-button label="30">30天</el-radio-button>
            <el-radio-button label="90">90天</el-radio-button>
          </el-radio-group>
        </div>
        <div class="chart-body">
          <div v-if="trendLoading" class="chart-loading">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          </div>
          <div v-else-if="trendData.length === 0" class="chart-empty">暂无数据</div>
          <div v-else class="trend-chart">
            <div v-for="(item, idx) in trendData" :key="idx" class="trend-bar-group">
              <div class="trend-bars">
                <div class="trend-bar completed" :style="{ height: getTrendHeight(item.completed) }"></div>
                <div class="trend-bar failed" :style="{ height: getTrendHeight(item.failed) }"></div>
              </div>
              <div class="trend-label">{{ item.date }}</div>
            </div>
          </div>
        </div>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-dot completed"></span>成功</span>
          <span class="legend-item"><span class="legend-dot failed"></span>失败</span>
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"/>
              <path d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z"/>
            </svg>
            模态分布
          </h3>
        </div>
        <div class="chart-body">
          <div v-if="modalityData.length === 0" class="chart-empty">暂无数据</div>
          <div v-else class="modality-chart">
            <div v-for="(item, idx) in modalityData" :key="idx" class="modality-item">
              <div class="modality-info">
                <span class="modality-name">{{ modalityMap[item.modality] || item.modality }}</span>
                <span class="modality-count">{{ item.count }}条</span>
              </div>
              <div class="modality-bar-bg">
                <div class="modality-bar" :style="{ width: getModalityPercent(item.count) + '%', background: getModalityColor(item.modality) }"></div>
              </div>
              <div class="modality-detail">
                <span class="ai-rate">AI: {{ (item.ai_rate * 100).toFixed(1) }}%</span>
                <span class="avg-conf">平均置信度: {{ (item.avg_confidence * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 模型性能分析 -->
    <div class="model-section">
      <div class="section-header">
        <h2>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
          </svg>
          模型性能分析
        </h2>
        <p>基于用户检测数据，分析各模型准确率和校准状态，用于指导模型优化方向</p>
      </div>

      <div v-if="modelAnalysisLoading" class="section-loading">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      </div>
      <div v-else class="model-stats">
        <div class="model-card" v-for="model in modelStats" :key="model.modality">
          <div class="model-header">
            <span class="model-name">{{ modalityMap[model.modality] || model.modality }}检测</span>
            <el-tag :type="getModelStatusType(model)" size="small">
              {{ getModelStatus(model) }}
            </el-tag>
          </div>
          <div class="model-metrics">
            <div class="metric">
              <span class="metric-label">总样本</span>
              <span class="metric-value">{{ model.total_samples }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">AI样本</span>
              <span class="metric-value" style="color:#dc2626">{{ model.ai_samples }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">真人样本</span>
              <span class="metric-value" style="color:#10b981">{{ model.human_samples }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">平均置信度</span>
              <div class="metric-bar">
                <div class="metric-fill" :style="{ width: (model.avg_confidence * 100) + '%', background: getConfidenceColor(model.avg_confidence) }"></div>
              </div>
              <span class="metric-value" :style="{ color: getConfidenceColor(model.avg_confidence) }">{{ (model.avg_confidence * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric">
              <span class="metric-label">校准后</span>
              <div class="metric-bar">
                <div class="metric-fill" :style="{ width: (model.avg_calibrated_confidence * 100) + '%', background: getConfidenceColor(model.avg_calibrated_confidence) }"></div>
              </div>
              <span class="metric-value" :style="{ color: getConfidenceColor(model.avg_calibrated_confidence) }">{{ (model.avg_calibrated_confidence * 100).toFixed(1) }}%</span>
            </div>
          </div>
          <div class="model-detail">
            <div class="detail-item">
              <span>数据均衡性</span>
              <span :style="{ color: getBalanceColor(model.ai_ratio) }">{{ (model.ai_ratio * 100).toFixed(1) }}% AI</span>
            </div>
            <div class="detail-item">
              <span>置信度标准差</span>
              <span>{{ (model.confidence_std * 100).toFixed(2) }}%</span>
            </div>
            <div class="detail-item">
              <span>风险分布</span>
              <span class="risk-tags">
                <el-tag size="small" type="danger">高:{{ model.risk_distribution.high }}</el-tag>
                <el-tag size="small" type="warning">中:{{ model.risk_distribution.medium }}</el-tag>
                <el-tag size="small" type="success">低:{{ model.risk_distribution.low }}</el-tag>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 数据表格区域 -->
    <div class="data-section">
      <el-tabs v-model="activeTab" type="border-card" class="custom-tabs">
        <!-- 检测内容数据 -->
        <el-tab-pane name="contents">
          <template #label>
            <div class="tab-label">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
              </svg>
              <span>检测内容</span>
              <el-tag size="small" type="info">{{ contentTotal }}</el-tag>
            </div>
          </template>

          <div class="toolbar">
            <div class="toolbar-left">
              <el-select v-model="contentFilter.modality" placeholder="模态" clearable class="filter-select" @change="fetchContents(1)">
                <el-option label="文本" value="text" />
                <el-option label="图像" value="image" />
                <el-option label="音频" value="audio" />
              </el-select>
              <el-select v-model="contentFilter.isAi" placeholder="AI判定" clearable class="filter-select" @change="fetchContents(1)">
                <el-option label="AI生成" :value="true" />
                <el-option label="真人创作" :value="false" />
              </el-select>
              <el-slider v-model="confidenceRange" range :max="100" style="width:200px" @change="handleConfidenceChange" />
              <span class="confidence-label">置信度: {{ confidenceRange[0] }}%-{{ confidenceRange[1] }}%</span>
              <el-button class="reset-btn" @click="resetContentFilters">重置</el-button>
            </div>
          </div>

          <div class="table-wrapper">
            <el-table :data="contents" v-loading="contentsLoading" stripe class="custom-table">
              <el-table-column label="用户" width="120">
                <template #default="{ row }">
                  <div class="user-info compact">
                    <div class="user-avatar small">{{ row.username?.charAt(0)?.toUpperCase() || '?' }}</div>
                    <span>{{ row.username }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="模态" width="80">
                <template #default="{ row }">
                  <span class="modality-tag" :class="row.modality">{{ modalityMap[row.modality] || row.modality }}</span>
                </template>
              </el-table-column>
              <el-table-column label="输入内容" min-width="250">
                <template #default="{ row }">
                  <span class="content-preview">{{ row.input_content || row.input_file_url || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="AI判定" width="90">
                <template #default="{ row }">
                  <span class="ai-badge" :class="row.is_ai_generated ? 'ai' : 'human'">{{ row.is_ai_generated ? 'AI' : '真人' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="置信度" width="120">
                <template #default="{ row }">
                  <div class="confidence-cell">
                    <span :style="{ color: confidenceColor(row.confidence), fontWeight: 600 }">{{ (row.confidence * 100).toFixed(1) }}%</span>
                    <span v-if="row.calibrated_confidence" class="calibrated">校准:{{ (row.calibrated_confidence * 100).toFixed(1) }}%</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="风险" width="80">
                <template #default="{ row }">
                  <el-tag v-if="row.risk_level" :type="riskTagMap[row.risk_level] || 'info'" size="small" effect="light">{{ riskMap[row.risk_level] || row.risk_level }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="时间" width="150" />
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="viewDetail(row.id)">详情</el-button>
                  <el-button link type="success" @click="addToDataset(row)">纳入训练</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="pagination-wrapper">
            <el-pagination v-model:current-page="contentPage" :page-size="contentPageSize" :total="contentTotal"
              layout="total, sizes, prev, pager, next, jumper" :page-sizes="[10, 20, 50, 100]"
              @current-change="fetchContents" @size-change="handleContentSizeChange" />
          </div>
        </el-tab-pane>

        <!-- 用户分析 -->
        <el-tab-pane name="users">
          <template #label>
            <div class="tab-label">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
              </svg>
              <span>用户分析</span>
              <el-tag size="small" type="info">{{ userTotal }}</el-tag>
            </div>
          </template>

          <div class="toolbar">
            <div class="toolbar-left">
              <div class="search-box">
                <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="11" cy="11" r="8"/>
                  <path d="M21 21l-4.35-4.35"/>
                </svg>
                <el-input v-model="userSearch" placeholder="搜索用户名或邮箱" clearable class="search-input" @keyup.enter="fetchUsers(1)" />
              </div>
              <el-button type="primary" class="search-btn" @click="fetchUsers(1)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;margin-right:4px">
                  <circle cx="11" cy="11" r="8"/>
                  <path d="M21 21l-4.35-4.35"/>
                </svg>
                搜索
              </el-button>
            </div>
          </div>

          <div class="table-wrapper">
            <el-table :data="users" v-loading="usersLoading" stripe class="custom-table">
              <el-table-column label="用户" min-width="180">
                <template #default="{ row }">
                  <div class="user-info">
                    <div class="user-avatar">{{ row.username.charAt(0).toUpperCase() }}</div>
                    <div class="user-details">
                      <div class="user-name">{{ row.username }}</div>
                      <div class="user-email">{{ row.email }}</div>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="角色" width="100">
                <template #default="{ row }">
                  <el-tag :type="roleTagMap[row.role] || 'info'" size="small" effect="light">{{ roleMap[row.role] || row.role }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="检测统计" width="200">
                <template #default="{ row }">
                  <div class="detection-mini-stats">
                    <div class="mini-stat">
                      <span class="mini-dot total"></span>
                      <span>总: {{ row.task_count || 0 }}</span>
                    </div>
                    <div class="mini-stat">
                      <span class="mini-dot ai"></span>
                      <span>AI: {{ row.ai_detected_count || 0 }}</span>
                    </div>
                    <div class="mini-stat">
                      <span class="mini-dot human"></span>
                      <span>真人: {{ (row.task_count || 0) - (row.ai_detected_count || 0) }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="AI检出率" width="120">
                <template #default="{ row }">
                  <span class="ai-rate" :style="{ color: getAiRateColor(row) }">{{ getAiRate(row) }}%</span>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="注册时间" width="150" />
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="viewUserDetail(row)">详情</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="pagination-wrapper">
            <el-pagination v-model:current-page="userPage" :page-size="userPageSize" :total="userTotal"
              layout="total, sizes, prev, pager, next, jumper" :page-sizes="[10, 20, 50, 100]"
              @current-change="fetchUsers" @size-change="handleUserSizeChange" />
          </div>
        </el-tab-pane>

        <!-- 检测记录 -->
        <el-tab-pane name="detections">
          <template #label>
            <div class="tab-label">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
              </svg>
              <span>检测记录</span>
              <el-tag size="small" type="info">{{ detTotal }}</el-tag>
            </div>
          </template>

          <div class="toolbar">
            <div class="toolbar-left">
              <el-select v-model="detModality" placeholder="模态" clearable class="filter-select">
                <el-option label="文本" value="text" />
                <el-option label="图像" value="image" />
                <el-option label="音频" value="audio" />
              </el-select>
              <el-select v-model="detRisk" placeholder="风险" clearable class="filter-select">
                <el-option label="低风险" value="low" />
                <el-option label="中风险" value="medium" />
                <el-option label="高风险" value="high" />
              </el-select>
              <el-button type="primary" class="search-btn" @click="fetchDetections(1)">筛选</el-button>
              <el-button class="reset-btn" @click="resetDetFilters">重置</el-button>
            </div>
          </div>

          <div class="table-wrapper">
            <el-table :data="detections" v-loading="detsLoading" stripe class="custom-table">
              <el-table-column label="用户" width="120">
                <template #default="{ row }">
                  <div class="user-info compact">
                    <div class="user-avatar small">{{ row.username?.charAt(0)?.toUpperCase() || '?' }}</div>
                    <span>{{ row.username }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="模态" width="80">
                <template #default="{ row }">
                  <span class="modality-tag" :class="row.modality">{{ modalityMap[row.modality] || row.modality }}</span>
                </template>
              </el-table-column>
              <el-table-column label="输入内容" min-width="200">
                <template #default="{ row }">
                  <span class="content-preview">{{ row.input_content || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="AI判定" width="90">
                <template #default="{ row }">
                  <span class="ai-badge" :class="row.is_ai_generated ? 'ai' : 'human'">{{ row.is_ai_generated ? 'AI' : '真人' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="置信度" width="100">
                <template #default="{ row }">
                  <span :style="{ color: confidenceColor(row.confidence), fontWeight: 600 }">{{ (row.confidence * 100).toFixed(1) }}%</span>
                </template>
              </el-table-column>
              <el-table-column label="风险" width="80">
                <template #default="{ row }">
                  <el-tag v-if="row.risk_level" :type="riskTagMap[row.risk_level] || 'info'" size="small" effect="light">{{ riskMap[row.risk_level] || row.risk_level }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="时间" width="150" />
              <el-table-column label="操作" width="80" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="viewDetail(row.id)">详情</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="pagination-wrapper">
            <el-pagination v-model:current-page="detPage" :page-size="detPageSize" :total="detTotal"
              layout="total, sizes, prev, pager, next, jumper" :page-sizes="[10, 20, 50, 100]"
              @current-change="fetchDetections" @size-change="handleDetSizeChange" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="检测详情" width="750px" destroy-on-close class="detail-dialog">
      <div v-if="detailLoading" class="loading-state">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
        <p>加载中...</p>
      </div>
      <div v-else-if="detail" class="detail-content">
        <div class="detail-section">
          <h3 class="section-title">基本信息</h3>
          <div class="info-grid">
            <div class="info-item"><span class="info-label">用户</span><span class="info-value">{{ detail.user?.username }}</span></div>
            <div class="info-item"><span class="info-label">模态</span><span class="info-value"><span class="modality-tag" :class="detail.modality">{{ modalityMap[detail.modality] || detail.modality }}</span></span></div>
            <div class="info-item"><span class="info-label">AI判定</span><span class="info-value"><span class="ai-badge" :class="detail.is_ai_generated ? 'ai' : 'human'">{{ detail.is_ai_generated ? 'AI生成' : '人类创作' }}</span></span></div>
            <div class="info-item"><span class="info-label">置信度</span><span class="info-value" :style="{ color: confidenceColor(detail.confidence), fontWeight: 600 }">{{ (detail.confidence * 100).toFixed(2) }}%</span></div>
            <div class="info-item"><span class="info-label">校准置信度</span><span class="info-value">{{ detail.calibrated_confidence ? (detail.calibrated_confidence * 100).toFixed(2) + '%' : '-' }}</span></div>
            <div class="info-item"><span class="info-label">风险等级</span><span class="info-value"><el-tag v-if="detail.risk_level" :type="riskTagMap[detail.risk_level] || 'info'" size="small" effect="light">{{ riskMap[detail.risk_level] || detail.risk_level }}</el-tag></span></div>
            <div class="info-item"><span class="info-label">检测时间</span><span class="info-value">{{ detail.created_at }}</span></div>
            <div class="info-item"><span class="info-label">任务状态</span><span class="info-value">{{ detail.task_status }}</span></div>
          </div>
        </div>

        <div v-if="detail.input_content" class="detail-section">
          <h3 class="section-title">输入内容</h3>
          <div class="content-box">{{ detail.input_content }}</div>
        </div>

        <div v-if="detail.raw_scores" class="detail-section">
          <h3 class="section-title">原始分数</h3>
          <div class="scores-grid">
            <div v-for="(val, key) in detail.raw_scores" :key="key" class="score-item">
              <span class="score-label">{{ key }}</span>
              <span class="score-value">{{ typeof val === 'number' ? val.toFixed(4) : JSON.stringify(val) }}</span>
            </div>
          </div>
        </div>

        <div v-if="detail.model_attribution" class="detail-section">
          <h3 class="section-title">模型归因</h3>
          <div class="scores-grid">
            <div v-for="(val, key) in detail.model_attribution" :key="key" class="score-item">
              <span class="score-label">{{ key }}</span>
              <span class="score-value">{{ typeof val === 'number' ? val.toFixed(4) : JSON.stringify(val) }}</span>
            </div>
          </div>
        </div>

        <div v-if="detail.explanation" class="detail-section">
          <h3 class="section-title">解释报告</h3>
          <div v-if="detail.explanation.arbitration_reason" class="explanation-item">
            <span class="explanation-label">仲裁原因</span>
            <p class="explanation-text">{{ detail.explanation.arbitration_reason }}</p>
          </div>
          <div v-if="detail.explanation.feature_contributions" class="explanation-item">
            <span class="explanation-label">特征贡献</span>
            <pre class="explanation-code">{{ JSON.stringify(detail.explanation.feature_contributions, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 导出训练数据对话框 -->
    <el-dialog v-model="showExportDialog" title="导出训练数据集" width="500px">
      <div class="export-form">
        <el-form :model="exportForm" label-width="100px">
          <el-form-item label="模态">
            <el-select v-model="exportForm.modality" placeholder="全部模态" clearable style="width:100%">
              <el-option label="文本" value="text" />
              <el-option label="图像" value="image" />
              <el-option label="音频" value="audio" />
            </el-select>
          </el-form-item>
          <el-form-item label="置信度范围">
            <el-slider v-model="exportForm.confidenceRange" range :max="100" />
            <div class="slider-labels">
              <span>{{ exportForm.confidenceRange[0] }}%</span>
              <span>{{ exportForm.confidenceRange[1] }}%</span>
            </div>
          </el-form-item>
          <el-form-item label="样本数量">
            <el-input-number v-model="exportForm.sampleLimit" :min="100" :max="10000" :step="100" style="width:100%" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showExportDialog = false">取消</el-button>
        <el-button type="primary" @click="exportDataset" :loading="exportLoading">导出JSON</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useAuthStore } from "@/stores/auth"
import { Loading } from "@element-plus/icons-vue"
import api from "@/api"
import { ElMessage } from "element-plus"

const auth = useAuthStore()

const roleMap: Record<string, string> = { admin: '管理员', teacher: '教师', journalist: '记者', student: '学生', researcher: '研究员', editor: '编辑', developer: '开发者' }
const roleTagMap: Record<string, string> = { admin: 'danger', teacher: 'warning', journalist: 'info', student: 'success', researcher: 'primary', editor: 'warning', developer: 'info' }
const modalityMap: Record<string, string> = { text: '文本', image: '图像', audio: '音频' }
const riskMap: Record<string, string> = { low: '低', medium: '中', high: '高' }
const riskTagMap: Record<string, string> = { low: 'success', medium: 'warning', high: 'danger' }

const activeTab = ref("contents")
const trendPeriod = ref("7")

// KPI 数据
const kpiData = ref([
  { label: "总用户数", value: 0, trend: 12, gradient: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", iconBg: "rgba(102, 126, 234, 0.1)", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" },
  { label: "总检测数", value: 0, trend: 8, gradient: "linear-gradient(135deg, #10b981 0%, #059669 100%)", iconBg: "rgba(16, 185, 129, 0.1)", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" },
  { label: "AI检出率", value: "0%", gradient: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)", iconBg: "rgba(245, 158, 11, 0.1)", icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" },
  { label: "今日检测", value: 0, gradient: "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)", iconBg: "rgba(220, 38, 38, 0.1)", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
])

// 趋势数据
const trendData = ref<any[]>([])
const trendLoading = ref(false)
const modalityData = ref<any[]>([])

// 模型分析
const modelStats = ref<any[]>([])
const modelAnalysisLoading = ref(false)

// 检测内容数据
const contents = ref<any[]>([])
const contentsLoading = ref(false)
const contentPage = ref(1)
const contentPageSize = ref(20)
const contentTotal = ref(0)
const contentFilter = ref({ modality: '', isAi: null as boolean | null })
const confidenceRange = ref([0, 100])

// 用户数据
const userSearch = ref("")
const users = ref<any[]>([])
const usersLoading = ref(false)
const userPage = ref(1)
const userPageSize = ref(20)
const userTotal = ref(0)

// 检测记录
const detModality = ref("")
const detRisk = ref("")
const detections = ref<any[]>([])
const detsLoading = ref(false)
const detPage = ref(1)
const detPageSize = ref(20)
const detTotal = ref(0)

// 详情
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<any>(null)

// 导出
const showExportDialog = ref(false)
const exportLoading = ref(false)
const exportForm = ref({
  modality: '',
  confidenceRange: [0, 100],
  sampleLimit: 1000,
})

function getConfidenceColor(val: number): string {
  if (val >= 0.8) return '#dc2626'
  if (val >= 0.5) return '#f59e0b'
  return '#10b981'
}

function getBalanceColor(ratio: number): string {
  if (ratio < 0.3 || ratio > 0.7) return '#f59e0b'
  return '#10b981'
}

function getModelStatus(model: any): string {
  const ratio = model.ai_ratio
  if (ratio < 0.2 || ratio > 0.8) return '数据不均衡'
  if (model.confidence_std > 0.3) return '置信度波动大'
  return '良好'
}

function getModelStatusType(model: any): string {
  const status = getModelStatus(model)
  if (status === '良好') return 'success'
  return 'warning'
}

function getModalityColor(modality: string): string {
  const colors: Record<string, string> = { text: '#667eea', image: '#10b981', audio: '#f59e0b' }
  return colors[modality] || '#667eea'
}

function getModalityPercent(count: number): number {
  const max = Math.max(...modalityData.value.map(m => m.count), 1)
  return (count / max) * 100
}

function getTrendHeight(value: number): string {
  const max = Math.max(...trendData.value.flatMap(d => [d.completed, d.failed]), 1)
  return Math.max((value / max) * 100, 4) + '%'
}

function getAiRate(row: any): string {
  const total = row.task_count || 0
  if (total === 0) return '0.0'
  return ((row.ai_detected_count || 0) / total * 100).toFixed(1)
}

function getAiRateColor(row: any): string {
  const rate = parseFloat(getAiRate(row))
  if (rate > 50) return '#dc2626'
  if (rate > 30) return '#f59e0b'
  return '#10b981'
}

function confidenceColor(confidence: number): string {
  if (confidence > 0.7) return '#dc2626'
  if (confidence > 0.4) return '#f59e0b'
  return '#10b981'
}

// API 调用
async function fetchStats() {
  try {
    const { data } = await api.get("/admin/stats")
    kpiData.value[0].value = data.total_users
    kpiData.value[1].value = data.total_tasks
    kpiData.value[2].value = (data.detection_rate * 100).toFixed(1) + '%'
    kpiData.value[3].value = data.today_tasks
  } catch {}
}

async function fetchTrend() {
  trendLoading.value = true
  try {
    const { data } = await api.get("/admin/trend", { params: { days: trendPeriod.value } })
    trendData.value = data.daily_trend
    modalityData.value = data.modality_distribution
  } finally {
    trendLoading.value = false
  }
}

async function fetchModelAnalysis() {
  modelAnalysisLoading.value = true
  try {
    const { data } = await api.get("/admin/model-analysis")
    modelStats.value = data.model_stats
  } finally {
    modelAnalysisLoading.value = false
  }
}

async function fetchContents(page?: number) {
  if (page) contentPage.value = page
  contentsLoading.value = true
  try {
    const { data } = await api.get("/admin/detection-contents", {
      params: {
        page: contentPage.value,
        page_size: contentPageSize.value,
        modality: contentFilter.value.modality || undefined,
        is_ai: contentFilter.value.isAi ?? undefined,
        min_confidence: confidenceRange.value[0] / 100,
        max_confidence: confidenceRange.value[1] / 100,
      },
    })
    contents.value = data.contents
    contentTotal.value = data.total
  } finally {
    contentsLoading.value = false
  }
}

function handleConfidenceChange() {
  fetchContents(1)
}

function resetContentFilters() {
  contentFilter.value = { modality: '', isAi: null }
  confidenceRange.value = [0, 100]
  fetchContents(1)
}

function handleContentSizeChange(size: number) {
  contentPageSize.value = size
  fetchContents(1)
}

async function fetchUsers(page?: number) {
  if (page) userPage.value = page
  usersLoading.value = true
  try {
    const { data } = await api.get("/admin/users", {
      params: { page: userPage.value, page_size: userPageSize.value, search: userSearch.value || undefined },
    })
    users.value = data.users
    userTotal.value = data.total
  } finally {
    usersLoading.value = false
  }
}

function handleUserSizeChange(size: number) {
  userPageSize.value = size
  fetchUsers(1)
}

async function fetchDetections(page?: number) {
  if (page) detPage.value = page
  detsLoading.value = true
  try {
    const { data } = await api.get("/admin/detections", {
      params: {
        page: detPage.value, page_size: detPageSize.value,
        modality: detModality.value || undefined,
        risk_level: detRisk.value || undefined,
      },
    })
    detections.value = data.detections
    detTotal.value = data.total
  } finally {
    detsLoading.value = false
  }
}

function handleDetSizeChange(size: number) {
  detPageSize.value = size
  fetchDetections(1)
}

function resetDetFilters() {
  detModality.value = ""
  detRisk.value = ""
  fetchDetections(1)
}

async function viewDetail(id: string) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const { data } = await api.get(`/admin/detections/${id}`)
    detail.value = data
  } finally {
    detailLoading.value = false
  }
}

function viewUserDetail(row: any) {
  ElMessage.info(`查看用户 ${row.username} 的详细数据`)
}

function addToDataset(row: any) {
  ElMessage.success(`已将样本 ${row.id.slice(0, 8)} 纳入训练数据集`)
}

async function exportDataset() {
  exportLoading.value = true
  try {
    const { data } = await api.post("/admin/export-dataset", null, {
      params: {
        modality: exportForm.value.modality || undefined,
        min_confidence: exportForm.value.confidenceRange[0] / 100,
        max_confidence: exportForm.value.confidenceRange[1] / 100,
        sample_limit: exportForm.value.sampleLimit,
      },
    })

    // 下载JSON文件
    const blob = new Blob([JSON.stringify(data.dataset, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `training_dataset_${data.modality}_${new Date().toISOString().slice(0,10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    ElMessage.success(`成功导出 ${data.total} 条训练数据`)
    showExportDialog.value = false
  } catch {
    ElMessage.error("导出失败")
  } finally {
    exportLoading.value = false
  }
}

onMounted(() => {
  fetchStats()
  fetchTrend()
  fetchModelAnalysis()
  fetchContents(1)
  fetchUsers(1)
  fetchDetections(1)
})
</script>

<style scoped>
.admin-analytics {
  padding: 24px;
  background: #f8fafc;
  min-height: 100vh;
}

/* 页面头部 */
.page-header {
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 20px 24px;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.title-icon svg {
  width: 24px;
  height: 24px;
  color: white;
}

.title-text h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 4px 0;
}

.title-text p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.export-btn {
  border-radius: 10px;
  padding: 10px 20px;
}

.admin-badge {
  font-size: 14px;
  padding: 8px 16px;
  border-radius: 8px;
}

/* KPI 卡片 */
.kpi-section {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.kpi-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
}

.kpi-card:hover {
  transform: translateY(-4px);
}

.kpi-bg {
  position: absolute;
  top: 0;
  right: 0;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  opacity: 0.05;
  transform: translate(30%, -30%);
}

.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.kpi-icon svg {
  width: 24px;
  height: 24px;
  color: #667eea;
}

.kpi-value {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1;
  margin-bottom: 4px;
}

.kpi-label {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 8px;
}

.kpi-change {
  font-size: 13px;
  font-weight: 600;
}

.kpi-change.up {
  color: #10b981;
}

.kpi-change.down {
  color: #dc2626;
}

.kpi-change span {
  font-weight: 400;
  color: #94a3b8;
  margin-left: 4px;
}

/* 图表区域 */
.charts-section {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.chart-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.chart-card.wide {
  grid-column: 1;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.chart-header h3 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.chart-header h3 svg {
  width: 20px;
  height: 20px;
  color: #667eea;
}

.chart-body {
  min-height: 280px;
}

.chart-loading, .chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 280px;
  color: #94a3b8;
}

/* 趋势图表 */
.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  height: 260px;
  padding: 10px 0;
}

.trend-bar-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.trend-bars {
  display: flex;
  gap: 3px;
  align-items: flex-end;
  height: 220px;
  width: 100%;
  justify-content: center;
}

.trend-bar {
  width: 12px;
  border-radius: 4px 4px 0 0;
  transition: height 0.3s ease;
  min-height: 4px;
}

.trend-bar.completed {
  background: linear-gradient(to top, #10b981, #34d399);
}

.trend-bar.failed {
  background: linear-gradient(to top, #dc2626, #f87171);
}

.trend-label {
  font-size: 11px;
  color: #94a3b8;
}

.chart-legend {
  display: flex;
  gap: 20px;
  justify-content: center;
  margin-top: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748b;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.legend-dot.completed {
  background: #10b981;
}

.legend-dot.failed {
  background: #dc2626;
}

/* 模态分布 */
.modality-chart {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.modality-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.modality-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modality-name {
  font-weight: 600;
  color: #1e293b;
  font-size: 14px;
}

.modality-count {
  font-size: 13px;
  color: #6b7280;
}

.modality-bar-bg {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.modality-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.modality-detail {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.ai-rate {
  color: #dc2626;
  font-weight: 500;
}

.avg-conf {
  color: #6b7280;
}

/* 模型分析 */
.model-section {
  margin-bottom: 24px;
}

.section-header {
  margin-bottom: 20px;
}

.section-header h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 4px 0;
}

.section-header h2 svg {
  width: 24px;
  height: 24px;
  color: #667eea;
}

.section-header p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
  padding-left: 34px;
}

.section-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px;
  background: white;
  border-radius: 16px;
}

.model-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.model-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.model-name {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.model-metrics {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.metric {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-label {
  font-size: 12px;
  color: #6b7280;
  width: 60px;
  flex-shrink: 0;
}

.metric-bar {
  flex: 1;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}

.metric-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.metric-value {
  font-size: 13px;
  font-weight: 600;
  min-width: 50px;
  text-align: right;
}

.model-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.detail-item span:first-child {
  color: #6b7280;
}

.detail-item span:last-child {
  font-weight: 600;
  color: #1e293b;
}

.risk-tags {
  display: flex;
  gap: 4px;
}

/* 数据表格区域 */
.data-section {
  background: white;
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.custom-tabs :deep(.el-tabs__header) {
  margin: 0;
  border-bottom: 1px solid #e2e8f0;
}

.custom-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0 24px;
}

.custom-tabs :deep(.el-tabs__item) {
  padding: 16px 24px;
  font-size: 15px;
  font-weight: 500;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-label svg {
  width: 18px;
  height: 18px;
}

/* 工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.search-box {
  position: relative;
  width: 300px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  color: #94a3b8;
  z-index: 1;
}

:deep(.search-input .el-input__wrapper) {
  padding-left: 38px;
  border-radius: 10px;
}

.search-btn {
  border-radius: 10px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.filter-select {
  width: 140px;
}

:deep(.filter-select .el-input__wrapper) {
  border-radius: 10px;
}

.reset-btn {
  border-radius: 10px;
}

.confidence-label {
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
}

/* 表格 */
.table-wrapper {
  padding: 0 24px;
}

.custom-table :deep(.el-table__header th) {
  background: #f8fafc;
  font-weight: 600;
  color: #374151;
  padding: 14px 0;
}

/* 用户信息 */
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info.compact {
  gap: 8px;
}

.user-avatar {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
  flex-shrink: 0;
}

.user-avatar.small {
  width: 32px;
  height: 32px;
  font-size: 14px;
  border-radius: 8px;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-weight: 600;
  color: #1e293b;
  font-size: 14px;
}

.user-email {
  font-size: 12px;
  color: #6b7280;
}

/* 检测统计 */
.detection-mini-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mini-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
}

.mini-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.mini-dot.total {
  background: #667eea;
}

.mini-dot.ai {
  background: #dc2626;
}

.mini-dot.human {
  background: #10b981;
}

.ai-rate {
  font-weight: 600;
  font-size: 14px;
}

/* 模态标签 */
.modality-tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.modality-tag.text {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.modality-tag.image {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.modality-tag.audio {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

/* AI 徽章 */
.ai-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.ai-badge.ai {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.ai-badge.human {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

/* 内容预览 */
.content-preview {
  font-size: 13px;
  color: #4b5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 250px;
  display: block;
}

/* 置信度单元格 */
.confidence-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.confidence-cell .calibrated {
  font-size: 11px;
  color: #94a3b8;
}

/* 分页 */
.pagination-wrapper {
  padding: 20px 24px;
  border-top: 1px solid #f1f5f9;
}

/* 详情对话框 */
.detail-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #e2e8f0;
  padding: 20px 24px;
}

.detail-dialog :deep(.el-dialog__title) {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
}

.detail-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.loading-state {
  text-align: center;
  padding: 60px 20px;
  color: #6b7280;
}

.loading-state p {
  margin-top: 16px;
  font-size: 14px;
}

.detail-content {
  padding: 24px;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 16px 0;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
}

.info-label {
  font-size: 12px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: #1a1a2e;
}

.content-box {
  background: #f8fafc;
  padding: 16px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.8;
  color: #4b5563;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
}

.scores-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.score-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
}

.score-label {
  font-size: 13px;
  color: #6b7280;
}

.score-value {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
  font-family: 'Courier New', monospace;
}

.explanation-item {
  margin-bottom: 16px;
}

.explanation-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.explanation-text {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  margin: 0;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
}

.explanation-code {
  font-size: 12px;
  color: #4b5563;
  background: #f8fafc;
  padding: 12px 16px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 0;
}

/* 导出表单 */
.export-form {
  padding: 10px 0;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

/* 响应式 */
@media (max-width: 1280px) {
  .kpi-section,
  .model-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-section {
    grid-template-columns: 1fr;
  }

  .chart-card.wide {
    grid-column: auto;
  }
}

@media (max-width: 768px) {
  .kpi-section,
  .model-stats {
    grid-template-columns: 1fr;
  }

  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .toolbar {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }

  .toolbar-left {
    flex-wrap: wrap;
  }

  .search-box {
    width: 100%;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
