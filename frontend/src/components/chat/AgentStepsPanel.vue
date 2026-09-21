<template>
  <div class="agent-steps-panel">
    <!-- 面板头部（折叠交互与"执行过程"风格一致） -->
    <div class="panel-header" @click="expanded = !expanded">
      <el-icon class="arrow-icon" :class="{ rotated: expanded }"><ArrowRight /></el-icon>
      <el-icon class="panel-icon"><Cpu /></el-icon>
      <span class="panel-title">智能体执行</span>
      <span class="panel-count">{{ steps.length }} 次调用</span>
      <el-tag v-if="reflections.length" size="small" type="warning" effect="light" class="reflect-badge">
        {{ reflections.length }} 次反思
      </el-tag>
      <span class="panel-action">{{ expanded ? '收起' : '展开' }}</span>
    </div>

    <div v-show="expanded" class="panel-content">
      <!-- 执行计划概要（plan事件） -->
      <div v-if="plan" class="plan-brief">
        <el-icon><Compass /></el-icon>
        <span class="plan-text">{{ plan.message || '智能体已开始分析问题' }}</span>
        <span class="plan-meta">可用工具 {{ plan.tools.length }} 个 · 最多 {{ plan.maxIterations }} 轮</span>
      </div>

      <!-- P1-1 规划器步骤清单（plan事件升级版：steps + currentStep） -->
      <div v-if="planSteps.length" class="plan-steps">
        <div class="plan-steps-header">
          <el-icon><List /></el-icon>
          <span>任务计划（{{ planSteps.length }} 步）</span>
          <span class="plan-steps-progress">进度 {{ planCurrentStep }}/{{ planSteps.length }}</span>
        </div>
        <div class="plan-steps-body">
          <div
            v-for="(step, idx) in planSteps"
            :key="idx"
            class="plan-step-item"
            :class="{
              done: idx < planCurrentStep,
              current: idx === planCurrentStep,
              pending: idx > planCurrentStep,
            }"
          >
            <span class="plan-step-index">{{ idx + 1 }}</span>
            <span class="plan-step-text">{{ step }}</span>
          </div>
        </div>
      </div>

      <!-- 工具调用步骤时间线（step事件） -->
      <div v-if="steps.length" class="steps-timeline">
        <div v-for="(step, idx) in steps" :key="idx" class="step-item">
          <div class="step-connector">
            <div class="connector-line" :class="{ last: idx === steps.length - 1 }"></div>
            <div class="step-dot" :class="step.status">
              <el-icon v-if="step.status === 'executing'" class="spin"><Loading /></el-icon>
              <el-icon v-else-if="step.status === 'success'"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
            </div>
          </div>
          <div class="step-content">
            <div class="step-title">
              第{{ step.iteration }}轮 · {{ step.tool }}
              <span class="status-label" :class="step.status">{{ statusLabel(step.status) }}</span>
            </div>
            <div v-if="step.detail" class="step-desc">{{ step.detail }}</div>
          </div>
        </div>
      </div>
      <div v-else class="steps-empty">尚未发起工具调用</div>

      <!-- 反思记录（reflect事件：R1重试/R2知识兜底/R3熔断） -->
      <div v-if="reflections.length" class="reflections-box">
        <div v-for="(r, idx) in reflections" :key="idx" class="reflection-item">
          <el-icon class="reflect-icon"><Warning /></el-icon>
          <span class="reflect-rule">{{ ruleLabel(r.rule) }}</span>
          <span class="reflect-detail">{{ r.detail }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowRight, Cpu, Compass, List, Loading, CircleCheck, CircleClose, Warning } from '@element-plus/icons-vue'

// 步骤条数据结构（与 stores/chat.ts 中 AgentStep/AgentReflection 对齐）
interface AgentStep {
  iteration: number
  tool: string
  status: 'executing' | 'success' | 'failed'
  detail?: string
}

interface AgentReflection {
  rule: string
  tool: string
  iteration: number
  outcome: string
  detail: string
}

const props = withDefaults(defineProps<{
  plan?: {
    tools: string[]
    maxIterations: number
    message?: string
    steps?: string[]      // P1-1 planner 步骤清单
    currentStep?: number  // P1-1 当前执行步索引
  } | null
  steps?: AgentStep[]
  reflections?: AgentReflection[]
}>(), {
  plan: null,
  steps: () => [],
  reflections: () => [],
})

const expanded = ref(true)

// P1-1 规划步骤清单（空清单时不渲染该区域）
const planSteps = computed(() => props.plan?.steps || [])
const planCurrentStep = computed(() => props.plan?.currentStep ?? 0)

/** 步骤状态中文标签 */
function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    executing: '执行中',
    success: '成功',
    failed: '失败',
  }
  return labels[status] || status
}

/** 反思规则中文标签（与后端 agent_reflector 规则对应） */
function ruleLabel(rule: string): string {
  const labels: Record<string, string> = {
    retry: '失败重试',
    knowledge_fallback: '知识兜底',
    circuit_break: '循环熔断',
  }
  return labels[rule] || rule
}
</script>

<style scoped lang="scss">
.agent-steps-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 12px;
  background: #fff;

  .panel-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    background: #f8fafc;
    transition: background-color 0.2s;

    &:hover {
      background: #f1f5f9;
    }

    .arrow-icon {
      font-size: 12px;
      color: #94a3b8;
      transition: transform 0.2s;

      &.rotated {
        transform: rotate(90deg);
      }
    }

    .panel-icon {
      font-size: 14px;
      color: #6366f1;
    }

    .panel-title {
      font-size: 13px;
      font-weight: 600;
      color: #475569;
    }

    .panel-count {
      font-size: 12px;
      color: #94a3b8;
      padding: 2px 8px;
      background: #e2e8f0;
      border-radius: 10px;
    }

    .reflect-badge {
      border-radius: 10px;
    }

    .panel-action {
      font-size: 12px;
      color: #64748b;
      margin-left: auto;
    }
  }

  .panel-content {
    padding: 10px 12px;
    border-top: 1px solid #e2e8f0;
  }

  // 执行计划概要
  .plan-brief {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding: 6px 10px;
    margin-bottom: 10px;
    background: #eef2ff;
    border-radius: 6px;

    .el-icon {
      font-size: 14px;
      color: #6366f1;
    }

    .plan-text {
      font-size: 12px;
      color: #4338ca;
    }

    .plan-meta {
      font-size: 11px;
      color: #818cf8;
      margin-left: auto;
    }
  }

  // P1-1 规划器步骤清单
  .plan-steps {
    margin-bottom: 10px;
    border: 1px solid #e0e7ff;
    border-radius: 6px;
    overflow: hidden;
  }

  .plan-steps-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: #eef2ff;
    font-size: 12px;
    font-weight: 600;
    color: #4338ca;

    .el-icon {
      font-size: 14px;
      color: #6366f1;
    }
  }

  .plan-steps-progress {
    margin-left: auto;
    font-size: 11px;
    font-weight: 400;
    color: #818cf8;
  }

  .plan-steps-body {
    padding: 6px 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .plan-step-item {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: 12px;
    line-height: 18px;

    .plan-step-index {
      flex-shrink: 0;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      transform: translateY(2px);
      background: #e2e8f0;
      color: #94a3b8;
    }

    .plan-step-text {
      color: #94a3b8;
      word-break: break-word;
    }

    &.done {
      .plan-step-index {
        background: #10b981;
        color: #fff;
      }

      .plan-step-text {
        color: #64748b;
      }
    }

    &.current {
      .plan-step-index {
        background: #6366f1;
        color: #fff;
      }

      .plan-step-text {
        color: #1e293b;
        font-weight: 500;
      }
    }
  }

  // 步骤时间线（与执行过程时间线视觉一致）
  .steps-timeline {
    position: relative;
  }

  .step-item {
    position: relative;
    display: flex;
    gap: 10px;
    padding: 8px 0 8px 24px;
    min-height: 36px;
  }

  .step-connector {
    position: absolute;
    left: 0;
    top: 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 24px;
    height: calc(100% - 16px);
  }

  .connector-line {
    position: absolute;
    left: 50%;
    top: 20px;
    transform: translateX(-50%);
    width: 2px;
    height: calc(100% - 20px);
    background: #e2e8f0;

    &.last {
      background: transparent;
    }
  }

  .step-dot {
    position: relative;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    background: #e2e8f0;
    z-index: 1;
    flex-shrink: 0;

    &.executing {
      background: #3b82f6;
    }

    &.success {
      background: #10b981;
    }

    &.failed {
      background: #ef4444;
    }

    .el-icon {
      font-size: 12px;
    }

    .spin {
      animation: agent-spin 1.2s linear infinite;
    }
  }

  .step-content {
    flex: 1;
    padding-left: 4px;
    padding-bottom: 4px;
  }

  .step-title {
    font-size: 13px;
    font-weight: 500;
    color: #1e293b;
    line-height: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;

    .status-label {
      font-size: 11px;
      padding: 1px 6px;
      border-radius: 8px;

      &.executing {
        color: #3b82f6;
        background: #eff6ff;
      }

      &.success {
        color: #10b981;
        background: #ecfdf5;
      }

      &.failed {
        color: #ef4444;
        background: #fef2f2;
      }
    }
  }

  .step-desc {
    font-size: 12px;
    color: #64748b;
    margin-top: 2px;
    line-height: 18px;
    word-break: break-word;
    white-space: normal;
  }

  .steps-empty {
    font-size: 12px;
    color: #94a3b8;
    padding: 4px 0;
  }

  // 反思记录
  .reflections-box {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .reflection-item {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 12px;
    line-height: 18px;

    .reflect-icon {
      font-size: 13px;
      color: #f59e0b;
      flex-shrink: 0;
      transform: translateY(1px);
    }

    .reflect-rule {
      color: #b45309;
      font-weight: 600;
      flex-shrink: 0;
    }

    .reflect-detail {
      color: #92400e;
      word-break: break-word;
    }
  }
}

@keyframes agent-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
