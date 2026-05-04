import { useEffect, useState } from 'react';
import { useStore } from '../store';
import type { Task } from '../api';

// 扩展Task类型（兼容backend字段）
interface ExtTask extends Omit<Task, 'heartbeat' | 'flow_log'> {
  official?: string;
  heartbeat?: { status: string; label: string };
  flow_log?: Array<{ at: string; from: string; to: string; remark: string }>;
  priority?: string;
  description?: string;
  sourceAgent?: string;
}

// ── 原始风格常量（来自 MemorialPanel / OfficialPanel）──────────────────────────
const API_BASE = 'http://127.0.0.1:7891';
const PIPE = ['尚书省', '门下省', '中书省', '太子'];
const STATE_LABEL: Record<string, string> = {
  Doing: '🔄 执行中', Review: '🔍 审批中', Assigned: '📌 已分配',
  Menxia: '🚪 门下省', Zhongshu: '🏛️ 中书省', Taizi: '👑 太子',
  Inbox: '📥 待处理', Blocked: '🚫 已阻塞', Next: '⏭️ 待启动',
  Done: '✅ 完成', Cancelled: '❌ 取消',
};
const DEPT_COLOR: Record<string, string> = {
  '尚书省': '#7c6af7', '户部': '#4ade80', '兵部': '#f97316',
  '刑部': '#94a3b8', '钦天监': '#a78bfa', '工部': '#fb923c', '中书省': '#facc15',
};

function deptColor(org: string) { return DEPT_COLOR[org] || '#94a3b8'; }
function isArchived(t: ExtTask) { return t.state === 'Cancelled'; }
function isEdict(t: ExtTask) { return t.id.startsWith('JJC-'); }

const FLOW_STAGES = ['尚书省', '门下省', '中书省', '太子'];

function flowIdx(state: string) {
  if (['Assigned', 'Inbox'].includes(state)) return 0;
  if (state === 'Doing') return 1;
  if (state === 'Menxia') return 2;
  if (['Zhongshu', 'Taizi', 'Review'].includes(state)) return 3;
  return -1;
}

// ── 原始风格FlowPipeline ───────────────────────────────────────────────────────
function FlowPipeline({ task }: { task: ExtTask }) {
  const idx = flowIdx(task.state);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap', marginBottom: 6 }}>
      {FLOW_STAGES.map((stage, i) => {
        const done = idx >= i + 1;
        const active = idx === i;
        return (
          <span key={stage} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              padding: '1px 7px', borderRadius: 20, fontSize: 11, fontWeight: 700,
              background: done ? 'var(--acc)' : active ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.05)',
              color: done || active ? '#fff' : 'var(--muted)',
              border: `1px solid ${done ? 'var(--acc)' : active ? 'rgba(255,255,255,0.3)' : 'var(--line)'}`,
            }}>
              {stage}
            </div>
            {i < FLOW_STAGES.length - 1 && (
              <span style={{ color: 'var(--line)', margin: '0 1px', fontSize: 12 }}>›</span>
            )}
          </span>
        );
      })}
    </div>
  );
}

// ── 原始风格TaskCard（来自MemorialPanel） ─────────────────────────────────────
function TaskCard({ task, onClick }: { task: ExtTask; onClick?: () => void }) {
  const stateColors: Record<string, string> = {
    Doing: '#22c55e', Review: '#8b5cf6', Menxia: '#06b6d4', Zhongshu: '#3b82f6',
    Taizi: '#eab308', Blocked: '#ef4444', Next: '#64748b', Assigned: '#6b7280',
    Inbox: '#6b7280', Done: '#10b981', Cancelled: '#ef4444',
  };
  const stCls = task.state || '';
  const clr = stateColors[stCls] || 'var(--muted)';
  const todos = task.todos || [];
  const todoDone = todos.filter((x: { status: string }) => x.status === 'completed').length;

  return (
    <div
      onClick={onClick}
      style={{
        padding: '10px 14px', background: 'var(--panel2)', border: '1px solid var(--line)',
        borderLeft: `3px solid ${clr}`, borderRadius: 8, marginBottom: 6, cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderLeftColor = 'var(--acc)')}
      onMouseLeave={e => (e.currentTarget.style.borderLeftColor = clr)}
    >
      <FlowPipeline task={task} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 3, fontFamily: 'monospace' }}>
            {task.id}
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {task.title || '(无标题)'}
          </div>
          {task.official && (
            <div style={{ fontSize: 11, color: '#d4a017', marginTop: 2 }}>
              {task.official}
            </div>
          )}
          {task.now && task.now !== '-' && (
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, lineHeight: 1.5 }}>
              {task.now.substring(0, 70)}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
          <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 20, fontWeight: 700, background: `${clr}22`, color: clr, border: `1px solid ${clr}44` }}>
            {STATE_LABEL[stCls] || stCls}
          </span>
          {todoDone > 0 && (
            <span style={{ fontSize: 10, color: 'var(--muted)' }}>📋 {todoDone}/{todos.length}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 原始风格输入框（来自OfficialPanel） ──────────────────────────────────────
function OfficialInput({ value, onChange, placeholder }: {
  value: string; onChange: (v: string) => void; placeholder: string;
}) {
  return (
    <input
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%', padding: '7px 12px', borderRadius: 8, border: '1px solid var(--line)',
        background: 'var(--panel2)', color: 'var(--text)', fontSize: 13, outline: 'none',
        boxSizing: 'border-box', fontFamily: 'inherit',
      }}
    />
  );
}

// ── 1. 活跃归档切换栏（原版风格） ──────────────────────────────────────────────
function ArchiveBar({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  const tabs = [
    { key: 'active', label: '🔄 活跃', color: '#22c55e' },
    { key: 'done', label: '✅ 已完成', color: '#10b981' },
    { key: 'all', label: '📦 全部', color: '#6b7280' },
  ];
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center' }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 700, marginRight: 4 }}>归档:</div>
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => onTab(t.key)}
          style={{
            padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 700,
            border: `1px solid ${tab === t.key ? t.color : 'var(--line)'}`,
            background: tab === t.key ? `${t.color}22` : 'transparent',
            color: tab === t.key ? t.color : 'var(--muted)',
            cursor: 'pointer',
          }}
        >
          {t.label}
        </button>
      ))}
      <button
        onClick={async () => {
          try {
            await fetch(`${API_BASE}/api/tasks/archive-all-done`, { method: 'POST' });
          } catch {}
        }}
        style={{
          marginLeft: 'auto', padding: '4px 12px', borderRadius: 20, fontSize: 11,
          border: '1px solid var(--line)', background: 'transparent',
          color: 'var(--muted)', cursor: 'pointer',
        }}
      >
        一键归档
      </button>
    </div>
  );
}

// ── 2. 各省部实时状态看板（新增，但风格同步） ──────────────────────────────────
function DeptStatusSection({ tasks }: { tasks: Task[] }) {
  const DEPT_LIST = ['尚书省', '户部', '兵部', '刑部', '钦天监', '工部', '中书省'];
  const DEPT_ICON: Record<string, string> = {
    '尚书省': '📜', '户部': '💰', '兵部': '⚔️', '刑部': '⚖️',
    '钦天监': '🔭', '工部': '🏗️', '中书省': '🦁',
  };
  const active = tasks.filter(t => !isArchived(t) && !isEdict(t));

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="panel-title">🏛️ 各省部实时状态</div>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
        gap: 8, padding: '12px', background: 'var(--panel2)', border: '1px solid var(--line)',
        borderRadius: 10, marginBottom: 14,
      }}>
        {DEPT_LIST.map(dept => {
          const deptTasks = active.filter(t => t.org === dept);
          const doing = deptTasks.filter(t => t.state === 'Doing');
          const review = deptTasks.filter(t => ['Menxia', 'Zhongshu', 'Taizi', 'Review'].includes(t.state));
          const clr = deptColor(dept);
          return (
            <div key={dept} style={{
              padding: '10px 12px', background: 'var(--panel)', borderRadius: 8,
              border: `1px solid ${doing.length > 0 ? clr + '66' : 'var(--line)'}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 15 }}>{DEPT_ICON[dept]}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: clr }}>{dept}</span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: doing.length > 0 ? clr : 'var(--text)' }}>
                {doing.length}
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)' }}>
                执行中{review.length > 0 ? ` · ${review.length}待批` : ''}
              </div>
              {doing.length > 0 && (
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {doing[0].title}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 3. 审批入口（新增，风格同步） ──────────────────────────────────────────────
function ApprovalSection({ tasks, onRefresh }: { tasks: Task[]; onRefresh: () => void }) {
  const [loading, setLoading] = useState<string | null>(null);
  const approval = tasks.filter(t =>
    ['Menxia', 'Zhongshu', 'Taizi', 'Review'].includes(t.state) && !isArchived(t) && !isEdict(t)
  );

  const handle = async (task: ExtTask, action: string, reason = '批准') => {
    if (action === 'reject') {
      const r = window.prompt('驳回原因：');
      if (!r) return;
      reason = r;
    }
    setLoading(task.id);
    try {
      await fetch(`${API_BASE}/api/task/${task.id}/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      });
      onRefresh();
    } finally { setLoading(null); }
  };

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="panel-title">📋 待审批 <span style={{ color: 'var(--acc)' }}>({approval.length})</span></div>
      {approval.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--muted)', fontSize: 12 }}>暂无待审批</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {approval.map(t => (
            <div key={t.id} style={{
              padding: '10px 14px', background: 'var(--panel2)', border: '1px solid var(--line)',
              borderRadius: 8, display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 3 }}>
                  <span style={{ fontSize: 11, color: deptColor(t.org), fontWeight: 700 }}>{t.org}</span>
                  <span style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'monospace' }}>{t.id}</span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {t.title}
                </div>
                {t.now && t.now !== '-' && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{t.now.substring(0, 60)}</div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button
                  className="btn-mint"
                  onClick={() => handle(t, 'approve')}
                  disabled={loading === t.id}
                  style={{ padding: '5px 12px', fontSize: 11, opacity: loading === t.id ? 0.5 : 1 }}
                >✅ 批准</button>
                <button
                  className="btn-mint btn-red"
                  onClick={() => handle(t, 'reject')}
                  disabled={loading === t.id}
                  style={{ padding: '5px 12px', fontSize: 11, opacity: loading === t.id ? 0.5 : 1 }}
                >🚫 驳回</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 4. 指挥下发（新增，风格同步OfficialPanel） ─────────────────────────────────
function DispatchSection({ onCreated }: { onCreated: () => void }) {
  const [title, setTitle] = useState('');
  const [dept, setDept] = useState('尚书省');
  const [official, setOfficial] = useState('尚书令');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('normal');
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState('');
  const DEPT_LIST = ['尚书省', '户部', '兵部', '刑部', '钦天监', '工部', '中书省'];

  const handleSubmit = async () => {
    if (!title.trim() || title.trim().length < 4) { setMsg('❌ 标题至少4字'); return; }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/agent-task/create`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), dept, official, description: description.trim(), priority }),
      });
      const r = await res.json();
      if (r.ok) { setMsg('🎯 旨意已下发：' + r.message); setTitle(''); setDescription(''); onCreated(); }
      else setMsg('❌ ' + (r.error || '下发失败'));
    } catch { setMsg('❌ 服务器连接失败'); }
    setSubmitting(false);
  };

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="panel-title">🎯 指挥下发</div>
      <div style={{ padding: '14px', background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 10 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, marginBottom: 8 }}>
          <OfficialInput value={title} onChange={setTitle} placeholder="📌 旨意标题（必填，至少4字）" />
          <select
            value={priority}
            onChange={e => setPriority(e.target.value)}
            style={{
              padding: '7px 10px', borderRadius: 8, border: '1px solid var(--line)',
              background: 'var(--panel2)', color: 'var(--text)', fontSize: 12, outline: 'none',
            }}
          >
            <option value="low">🟢 低</option>
            <option value="normal">🟡 普通</option>
            <option value="high">🔴 高</option>
            <option value="urgent">🚨 紧急</option>
          </select>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 8 }}>
          <select
            value={dept} onChange={e => setDept(e.target.value)}
            style={{ padding: '7px 10px', borderRadius: 8, border: '1px solid var(--line)', background: 'var(--panel2)', color: 'var(--text)', fontSize: 12, outline: 'none' }}
          >
            {DEPT_LIST.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          <OfficialInput value={official} onChange={setOfficial} placeholder="负责官员" />
          <OfficialInput value={description} onChange={setDescription} placeholder="任务详情（选填）" />
        </div>
        {msg && <div style={{ fontSize: 12, color: msg.startsWith('🎯') ? '#4ade80' : '#f87171', marginBottom: 8 }}>{msg}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            className="btn-mint"
            onClick={handleSubmit}
            disabled={submitting}
            style={{ padding: '7px 20px', fontSize: 13, opacity: submitting ? 0.6 : 1 }}
          >
            {submitting ? '下发中…' : '🎯 下发旨意'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 5. 执行反馈（新增） ────────────────────────────────────────────────────────
function FeedbackSection({ tasks, onRefresh }: { tasks: Task[]; onRefresh: () => void }) {
  const [updating, setUpdating] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, string>>({});
  const doing = tasks.filter(t => t.state === 'Doing' && !isArchived(t) && !isEdict(t));

  const update = async (task: ExtTask, state: string, remark: string) => {
    setUpdating(task.id);
    try {
      await fetch(`${API_BASE}/api/agent-task/update`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: task.id, state, now: `📌 ${remark}`, remark }),
      });
      onRefresh();
    } finally { setUpdating(null); }
  };

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="panel-title">⚙️ 执行反馈 <span style={{ color: 'var(--acc)' }}>({doing.length})</span></div>
      {doing.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--muted)', fontSize: 12 }}>暂无执行中任务</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {doing.map(t => (
            <div key={t.id} style={{
              padding: '10px 14px', background: 'var(--panel2)', border: '1px solid var(--line)', borderRadius: 8,
            }}>
              <div style={{ marginBottom: 6 }}>
                <span style={{ fontSize: 10, color: deptColor(t.org), fontWeight: 700 }}>{t.org}</span>
                <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 8, fontFamily: 'monospace' }}>{t.id}</span>
                <span style={{ fontSize: 12, fontWeight: 600, marginLeft: 8 }}>{t.title}</span>
              </div>
              {t.now && t.now !== '-' && (
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>{t.now.substring(0, 70)}</div>
              )}
              <textarea
                value={result[t.id] || ''}
                onChange={e => setResult(p => ({ ...p, [t.id]: e.target.value }))}
                placeholder="📝 执行结果或进度备注…"
                rows={2}
                style={{
                  width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--line)',
                  background: 'var(--panel)', color: 'var(--text)', fontSize: 12, outline: 'none',
                  resize: 'none', boxSizing: 'border-box', fontFamily: 'inherit', marginBottom: 8,
                }}
              />
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn-mint" onClick={() => update(t, 'Done', '执行完成')} disabled={updating === t.id || !result[t.id]?.trim()}>
                  ✅ 完成提交
                </button>
                <button className="btn-mint" onClick={() => update(t, 'Review', '提交审批')} disabled={updating === t.id}>
                  📮 提交审批
                </button>
                <button className="btn-mint btn-red" onClick={() => update(t, 'Blocked', '遇到阻塞')} disabled={updating === t.id}>
                  🚫 遇到阻塞
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 主组件 ──────────────────────────────────────────────────────────────────────
export default function EdictBoard() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'active' | 'done' | 'all'>('active');
  const [showNewFeatures, setShowNewFeatures] = useState(true);
  const setModalTaskId = useStore(s => s.setModalTaskId);

  const load = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tasks`);
      const data = await res.json();
      setTasks(Array.isArray(data) ? data : (data.tasks || []));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const getFiltered = () => {
    const base = tasks.filter(t => !isArchived(t));
    if (tab === 'active') return base.filter(t => !['Done', 'Cancelled'].includes(t.state));
    if (tab === 'done') return base.filter(t => ['Done', 'Cancelled'].includes(t.state));
    return base;
  };

  const filtered = getFiltered();
  const allDepts = ['尚书省', '户部', '兵部', '刑部', '钦天监', '工部', '中书省'];

  return (
    <div>
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 16, fontWeight: 800 }}>📜 旨意看板</div>
        <button
          onClick={() => setShowNewFeatures(v => !v)}
          style={{
            padding: '5px 14px', borderRadius: 20, fontSize: 11, fontWeight: 700,
            border: `1px solid ${showNewFeatures ? 'var(--acc)' : 'var(--line)'}`,
            background: showNewFeatures ? 'var(--acc)' : 'transparent',
            color: showNewFeatures ? '#fff' : 'var(--text)', cursor: 'pointer',
          }}
        >
          {showNewFeatures ? '🔼 收起新功能' : '🔽 更多功能'}
        </button>
      </div>

      {/* ── 新增功能区（可折叠） ── */}
      {showNewFeatures && (
        <div style={{ marginBottom: 20 }}>
          <DeptStatusSection tasks={tasks} />
          <ApprovalSection tasks={tasks} onRefresh={load} />
          <DispatchSection onCreated={load} />
          <FeedbackSection tasks={tasks} onRefresh={load} />
        </div>
      )}

      {/* ── 原版活跃/归档栏 ── */}
      <ArchiveBar tab={tab} onTab={t => setTab(t as typeof tab)} />

      {/* ── 原版任务列表 ── */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--muted)', fontSize: 13 }}>加载中…</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--muted)', fontSize: 13 }}>暂无任务</div>
      ) : (
        <div>
          {filtered.map(t => (
            <TaskCard
              key={t.id}
              task={t}
              onClick={() => setModalTaskId(t.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
