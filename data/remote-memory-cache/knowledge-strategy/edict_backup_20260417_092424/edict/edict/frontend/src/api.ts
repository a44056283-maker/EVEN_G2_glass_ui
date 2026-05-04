/**
 * API 层 — 对接 dashboard/server.py
 * 生产环境从同源 (port 7891) 请求，开发环境可通过 VITE_API_URL 指定
 */

const API_BASE = import.meta.env.VITE_API_URL || '';

// ── 通用请求 ──

async function fetchJ<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

async function postJ<T>(url: string, data: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ── API 接口 ──

export const api = {
  // 核心数据
  liveStatus: () => fetchJ<LiveStatus>(`${API_BASE}/api/live-status`),
  agentConfig: () => fetchJ<AgentConfig>(`${API_BASE}/api/agent-config`),
  modelChangeLog: () => fetchJ<ChangeLogEntry[]>(`${API_BASE}/api/model-change-log`).catch(() => []),
  officialsStats: () => fetchJ<OfficialsData>(`${API_BASE}/api/officials-stats`),
  morningBrief: () => fetchJ<MorningBrief>(`${API_BASE}/api/morning-brief`),
  morningConfig: () => fetchJ<SubConfig>(`${API_BASE}/api/morning-config`),
  agentReports: () => fetchJ<AgentReport[]>(`${API_BASE}/api/agent-reports`),
  agentsStatus: () => fetchJ<AgentsStatusData>(`${API_BASE}/api/agents-status`),

  // 任务实时动态
  taskActivity: (id: string) =>
    fetchJ<TaskActivityData>(`${API_BASE}/api/task-activity/${encodeURIComponent(id)}`),
  schedulerState: (id: string) =>
    fetchJ<SchedulerStateData>(`${API_BASE}/api/scheduler-state/${encodeURIComponent(id)}`),

  // 技能内容
  skillContent: (agentId: string, skillName: string) =>
    fetchJ<SkillContentResult>(
      `${API_BASE}/api/skill-content/${encodeURIComponent(agentId)}/${encodeURIComponent(skillName)}`
    ),

  // 操作类
  setModel: (agentId: string, model: string) =>
    postJ<ActionResult>(`${API_BASE}/api/set-model`, { agentId, model }),
  setDispatchChannel: (channel: string) =>
    postJ<ActionResult>(`${API_BASE}/api/set-dispatch-channel`, { channel }),
  agentWake: (agentId: string) =>
    postJ<ActionResult>(`${API_BASE}/api/agent-wake`, { agentId }),
  taskAction: (taskId: string, action: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/task-action`, { taskId, action, reason }),
  reviewAction: (taskId: string, action: string, comment: string) =>
    postJ<ActionResult>(`${API_BASE}/api/review-action`, { taskId, action, comment }),
  advanceState: (taskId: string, comment: string) =>
    postJ<ActionResult>(`${API_BASE}/api/advance-state`, { taskId, comment }),
  archiveTask: (taskId: string, archived: boolean) =>
    postJ<ActionResult>(`${API_BASE}/api/archive-task`, { taskId, archived }),
  archiveAllDone: () =>
    postJ<ActionResult & { count?: number }>(`${API_BASE}/api/archive-task`, { archiveAllDone: true }),
  schedulerScan: (thresholdSec = 180) =>
    postJ<ActionResult & { count?: number; actions?: ScanAction[]; checkedAt?: string }>(
      `${API_BASE}/api/scheduler-scan`,
      { thresholdSec }
    ),
  schedulerRetry: (taskId: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/scheduler-retry`, { taskId, reason }),
  schedulerEscalate: (taskId: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/scheduler-escalate`, { taskId, reason }),
  schedulerRollback: (taskId: string, reason: string) =>
    postJ<ActionResult>(`${API_BASE}/api/scheduler-rollback`, { taskId, reason }),
  refreshMorning: () =>
    postJ<ActionResult>(`${API_BASE}/api/morning-brief/refresh`, {}),
  saveMorningConfig: (config: SubConfig) =>
    postJ<ActionResult>(`${API_BASE}/api/morning-config`, config),
  addSkill: (agentId: string, skillName: string, description: string, trigger: string) =>
    postJ<ActionResult>(`${API_BASE}/api/add-skill`, { agentId, skillName, description, trigger }),

  // 远程 Skills 管理
  addRemoteSkill: (agentId: string, skillName: string, sourceUrl: string, description?: string) =>
    postJ<ActionResult & { skillName?: string; agentId?: string; source?: string; localPath?: string; size?: number; addedAt?: string }>(
      `${API_BASE}/api/add-remote-skill`, { agentId, skillName, sourceUrl, description: description || '' }
    ),
  remoteSkillsList: () =>
    fetchJ<RemoteSkillsListResult>(`${API_BASE}/api/remote-skills-list`),
  updateRemoteSkill: (agentId: string, skillName: string) =>
    postJ<ActionResult>(`${API_BASE}/api/update-remote-skill`, { agentId, skillName }),
  removeRemoteSkill: (agentId: string, skillName: string) =>
    postJ<ActionResult>(`${API_BASE}/api/remove-remote-skill`, { agentId, skillName }),

  createTask: (data: CreateTaskPayload) =>
    postJ<ActionResult & { taskId?: string }>(`${API_BASE}/api/create-task`, data),

  // ── 动态干预 ──
  getInterventionConfig: () =>
    fetchJ<InterventionConfig>(`${API_BASE}/api/intervention/config`),
  getInterventionHistory: () =>
    fetchJ<InterventionHistoryResult>(`${API_BASE}/api/bingbu/intervention_history`),
  getBingbuProposals: () =>
    fetchJ<BingbuProposalsResult>(`${API_BASE}/api/bingbu/proposals`),
  bingbuAction: (path: string) =>
    fetchJ<{ ok: boolean; [key: string]: unknown }>(`${API_BASE}${path}`).catch(() => ({ ok: false })),

  // ── 子代理任务（旨意看板） ──
  agentTaskCreate: (data: { title: string; dept?: string; official?: string; description?: string; priority?: string }) =>
    postJ<ActionResult & { taskId?: string; message?: string }>(`${API_BASE}/api/agent-task/create`, data),
  agentTaskUpdate: (data: { task_id: string; state?: string; output?: string; now?: string; remark?: string }) =>
    postJ<ActionResult>(`${API_BASE}/api/agent-task/update`, data),

  // ── 朝堂议政 ──
  courtDiscussStart: (topic: string, officials: string[], taskId?: string) =>
    postJ<CourtDiscussResult>(`${API_BASE}/api/court-discuss/start`, { topic, officials, taskId }),
  courtDiscussAdvance: (sessionId: string, userMessage?: string, decree?: string) =>
    postJ<CourtDiscussResult>(`${API_BASE}/api/court-discuss/advance`, { sessionId, userMessage, decree }),
  courtDiscussConclude: (sessionId: string) =>
    postJ<ActionResult & { summary?: string }>(`${API_BASE}/api/court-discuss/conclude`, { sessionId }),
  courtDiscussDestroy: (sessionId: string) =>
    postJ<ActionResult>(`${API_BASE}/api/court-discuss/destroy`, { sessionId }),
  courtDiscussFate: () =>
    fetchJ<{ ok: boolean; event: string }>(`${API_BASE}/api/court-discuss/fate`),

  // ── 机器人监控 ──
  botsBalances: () =>
    fetchJ<BotsBalancesResult>(`${API_BASE}/api/bots/balances`),
  botsPositions: () =>
    fetchJ<BotsPositionsResult>(`${API_BASE}/api/bots/positions`),
  botsForceEntry: (port: number, pair: string, side: string) =>
    postJ<{ ok: boolean; trade_id?: number; msg?: string; error?: string }>(
      `${API_BASE}/api/bots/force_entry`, { port, pair, side }
    ),
  botsForceExit: (port: number, trade_id: string) =>
    postJ<{ ok: boolean; msg?: string; error?: string }>(
      `${API_BASE}/api/bots/force_exit`, { port, trade_id }
    ),
};

// ── Types ──

export interface ActionResult {
  ok: boolean;
  message?: string;
  error?: string;
}

export interface FlowEntry {
  at: string;
  from: string;
  to: string;
  remark: string;
}

export interface TodoItem {
  id: string | number;
  title: string;
  status: 'not-started' | 'in-progress' | 'completed';
  detail?: string;
}

export interface Heartbeat {
  status: 'active' | 'warn' | 'stalled' | 'unknown' | 'idle';
  label: string;
}

export interface Task {
  id: string;
  title: string;
  state: string;
  org: string;
  now: string;
  eta: string;
  block: string;
  ac: string;
  output: string;
  heartbeat: Heartbeat;
  flow_log: FlowEntry[];
  todos: TodoItem[];
  review_round: number;
  archived: boolean;
  archivedAt?: string;
  updatedAt?: string;
  sourceMeta?: Record<string, unknown>;
  activity?: ActivityEntry[];
  _prev_state?: string;
}

export interface SyncStatus {
  ok: boolean;
  [key: string]: unknown;
}

export interface LiveStatus {
  tasks: Task[];
  syncStatus: SyncStatus;
}

export interface AgentInfo {
  id: string;
  label: string;
  emoji: string;
  role: string;
  model: string;
  skills: SkillInfo[];
}

export interface SkillInfo {
  name: string;
  description: string;
  path: string;
}

export interface KnownModel {
  id: string;
  label: string;
  provider: string;
}

export interface AgentConfig {
  agents: AgentInfo[];
  knownModels?: KnownModel[];
  dispatchChannel?: string;
}

export interface ChangeLogEntry {
  at: string;
  agentId: string;
  oldModel: string;
  newModel: string;
  rolledBack?: boolean;
}

export interface OfficialInfo {
  id: string;
  label: string;
  emoji: string;
  role: string;
  rank: string;
  model: string;
  model_short: string;
  tokens_in: number;
  tokens_out: number;
  cache_read: number;
  cache_write: number;
  cost_cny: number;
  cost_usd: number;
  sessions: number;
  messages: number;
  tasks_done: number;
  tasks_active: number;
  flow_participations: number;
  merit_score: number;
  merit_rank: number;
  last_active: string;
  heartbeat: Heartbeat;
  participated_edicts: { id: string; title: string; state: string }[];
}

export interface OfficialsData {
  officials: OfficialInfo[];
  totals: { tasks_done: number; cost_cny: number };
  top_official: string;
}

export interface AgentStatusInfo {
  id: string;
  label: string;
  emoji: string;
  role: string;
  status: 'running' | 'idle' | 'offline' | 'unconfigured';
  statusLabel: string;
  lastActive?: string;
}

export interface GatewayStatus {
  alive: boolean;
  probe: boolean;
  status: string;
}

export interface AgentsStatusData {
  ok: boolean;
  gateway: GatewayStatus;
  agents: AgentStatusInfo[];
  checkedAt: string;
}

export interface MorningNewsItem {
  title: string;
  summary?: string;
  desc?: string;
  link: string;
  source: string;
  image?: string;
  pub_date?: string;
}

export interface MorningBrief {
  date?: string;
  generated_at?: string;
  categories: Record<string, MorningNewsItem[]>;
}

export interface SubCategoryConfig {
  name: string;
  enabled: boolean;
}

export interface CustomFeed {
  name: string;
  url: string;
  category: string;
}

export interface AgentReport {
  agent: string;
  dept: string;
  label: string;
  icon: string;
  file: string;
  title: string;
  summary: string;
  mtime: string;
  content: string;
}

export interface SubConfig {
  categories: SubCategoryConfig[];
  keywords: string[];
  custom_feeds: CustomFeed[];
  feishu_webhook: string;
}

export interface ActivityEntry {
  kind: string;
  at?: number | string;
  text?: string;
  thinking?: string;
  agent?: string;
  from?: string;
  to?: string;
  remark?: string;
  tools?: { name: string; input_preview?: string }[];
  tool?: string;
  output?: string;
  exitCode?: number | null;
  items?: TodoItem[];
  diff?: {
    changed?: { id: string; from: string; to: string }[];
    added?: { id: string; title: string }[];
    removed?: { id: string; title: string }[];
  };
}

export interface PhaseDuration {
  phase: string;
  durationSec: number;
  durationText: string;
  ongoing?: boolean;
}

export interface TodosSummary {
  total: number;
  completed: number;
  inProgress: number;
  notStarted: number;
  percent: number;
}

export interface ResourceSummary {
  totalTokens?: number;
  totalCost?: number;
  totalElapsedSec?: number;
}

export interface TaskActivityData {
  ok: boolean;
  message?: string;
  error?: string;
  activity?: ActivityEntry[];
  relatedAgents?: string[];
  agentLabel?: string;
  lastActive?: string;
  phaseDurations?: PhaseDuration[];
  totalDuration?: string;
  todosSummary?: TodosSummary;
  resourceSummary?: ResourceSummary;
}

export interface SchedulerInfo {
  retryCount?: number;
  escalationLevel?: number;
  lastDispatchStatus?: string;
  stallThresholdSec?: number;
  enabled?: boolean;
  lastProgressAt?: string;
  lastDispatchAt?: string;
  lastDispatchAgent?: string;
  autoRollback?: boolean;
}

export interface SchedulerStateData {
  ok: boolean;
  error?: string;
  scheduler?: SchedulerInfo;
  stalledSec?: number;
}

export interface SkillContentResult {
  ok: boolean;
  name?: string;
  agent?: string;
  content?: string;
  path?: string;
  error?: string;
}

export interface ScanAction {
  taskId: string;
  action: string;
  to?: string;
  toState?: string;
  stalledSec?: number;
}

export interface CreateTaskPayload {
  title: string;
  org: string;
  targetDept?: string;
  priority?: string;
  templateId?: string;
  params?: Record<string, string>;
}

export interface RemoteSkillItem {
  skillName: string;
  agentId: string;
  sourceUrl: string;
  description: string;
  localPath: string;
  addedAt: string;
  lastUpdated: string;
  status: 'valid' | 'not-found' | string;
}

export interface RemoteSkillsListResult {
  ok: boolean;
  remoteSkills?: RemoteSkillItem[];
  count?: number;
  listedAt?: string;
  error?: string;
}

// ── 动态干预 ──
export interface InterventionConfig {
  sentiment_levels: Record<string, { label: string; trigger: string; action: string; urgency: number }>;
  black_swan: { fg_threshold: number; urgency_threshold: number; cooldown_hours: number; rejected_cooldown_hours: number };
  risk_params: { liquidation_alert_pct: number; var_95_threshold_pct: number; atr_volatility_multiplier: number; freeze_cooldown_minutes: number; var_lookback_period: number; var_confidence: number };
  action_rules: Record<string, { label: string; color: string; requires_approval: boolean; description: string }>;
  card_colors: Record<string, { header: string; button: string; light_bg: string }>;
  proposal_expiry_minutes: number;
  fetch_time: string;
}

export interface InterventionHistoryResult {
  interventions: Array<{
    id: number; timestamp: string; action: string; reason: string; result: string;
    sentiment?: { direction: string; confidence: number; urgency: number; fear_greed?: number; fear_greed_value?: number };
    targets?: unknown[];
  }>;
  intervention_count: number;
}

export interface BingbuProposalsResult {
  proposals: Array<{ id: string; code: string; action: string; reason: string; status: string; expires_at: string }>;
  count: number;
}

// ── 朝堂议政 ──

export interface CourtDiscussResult {
  ok: boolean;
  session_id?: string;
  topic?: string;
  round?: number;
  new_messages?: Array<{
    official_id: string;
    name: string;
    content: string;
    emotion?: string;
    action?: string;
  }>;
  scene_note?: string;
  total_messages?: number;
  error?: string;
}

// ── 机器人监控 ──
export interface BotInfo {
  port: number;
  label: string;
  exchange: string;
  total: number;
  starting_capital: number;
  profit: number;
  profit_pct: number;
  online: boolean;
}

export interface BotsBalancesResult {
  bots: BotInfo[];
  total: number;
  total_profit: number;
}

export interface BotPosition {
  bot: string;
  port: number;
  exchange: string;
  pair: string;
  side: 'LONG' | 'SHORT';
  amount: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  profit_pct: number;
  liquidation_price: number;
  leverage: number;
  trade_id: string;
}

export interface BotsPositionsResult {
  positions: BotPosition[];
  count: number;
  total_pnl: number;
}
