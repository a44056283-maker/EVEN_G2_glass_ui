import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api } from '../api';
import type { AgentReport } from '../api';

const ALL_DEPTS = ['尚书省', '户部', '兵部', '刑部', '钦天监', '工部', '中书省'];
const DEPT_ICON: Record<string, string> = {
  '尚书省': '📜', '户部': '💰', '兵部': '⚔️', '刑部': '⚖️',
  '钦天监': '🔭', '工部': '🏗️', '中书省': '🦁',
};

export default function MorningPanel() {
  const agentReports = useStore((s) => s.agentReports);
  const loadAgentReports = useStore((s) => s.loadAgentReports);

  const [filterDept, setFilterDept] = useState<string>('全部');
  const [filterDate, setFilterDate] = useState<string>('');
  const [reportModal, setReportModal] = useState<AgentReport | null>(null);

  useEffect(() => { loadAgentReports(); }, [loadAgentReports]);

  // 过滤
  const filtered = agentReports.filter((r) => {
    if (filterDept !== '全部' && r.dept !== filterDept) return false;
    if (filterDate && !r.mtime.startsWith(filterDate)) return false;
    return true;
  });

  // 按日期+部门分组，生成统计
  const stats = ALL_DEPTS.map((dept) => {
    const deptReports = agentReports.filter((r) => r.dept === dept);
    const dates = [...new Set(deptReports.map((r) => r.mtime.slice(0, 10)))];
    return { dept, icon: DEPT_ICON[dept] || '📋', count: deptReports.length, days: dates.length };
  });

  // 各部门最新一条
  const latestByDept = ALL_DEPTS.map((dept) => {
    const found = agentReports.filter((r) => r.dept === dept)[0];
    return found || null;
  }).filter(Boolean) as AgentReport[];

  return (
    <div>
      {/* Header */}
      <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 16 }}>📋 六部汇报中心</div>

      {/* ── 中央看板 ── */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 2 }}>各部状态</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 10 }}>
          {stats.map((s) => (
            <div
              key={s.dept}
              onClick={() => setFilterDept(filterDept === s.dept ? '全部' : s.dept)}
              style={{
                padding: '12px 14px',
                background: filterDept === s.dept ? 'var(--acc)' : 'var(--panel2)',
                border: `1px solid ${filterDept === s.dept ? 'var(--acc)' : 'var(--line)'}`,
                borderRadius: 12,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: 18, marginBottom: 4 }}>{s.icon}</div>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 2 }}>{s.dept}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: filterDept === s.dept ? '#fff' : 'var(--text)' }}>{s.count}</div>
              <div style={{ fontSize: 10, color: filterDept === s.dept ? 'rgba(255,255,255,0.7)' : 'var(--muted)' }}>{s.days} 天有汇报</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── 筛选栏 ── */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => setFilterDept('全部')}
            style={{
              padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
              border: `1px solid ${filterDept === '全部' ? 'var(--acc)' : 'var(--line)'}`,
              background: filterDept === '全部' ? 'var(--acc)' : 'transparent',
              color: filterDept === '全部' ? '#fff' : 'var(--text)',
              cursor: 'pointer',
            }}
          >全部部门</button>
          {ALL_DEPTS.map((d) => (
            <button
              key={d}
              onClick={() => setFilterDept(filterDept === d ? '全部' : d)}
              style={{
                padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                border: `1px solid ${filterDept === d ? 'var(--acc)' : 'var(--line)'}`,
                background: filterDept === d ? 'var(--acc)' : 'transparent',
                color: filterDept === d ? '#fff' : 'var(--text)',
                cursor: 'pointer',
              }}
            >
              {DEPT_ICON[d]} {d}
            </button>
          ))}
        </div>
        <input
          type="date"
          value={filterDate}
          onChange={(e) => setFilterDate(e.target.value)}
          style={{
            padding: '5px 10px', borderRadius: 8, border: '1px solid var(--line)',
            background: 'var(--bg)', color: 'var(--text)', fontSize: 12, outline: 'none',
          }}
        />
        {filterDate && (
          <button
            onClick={() => setFilterDate('')}
            style={{ fontSize: 11, color: 'var(--muted)', cursor: 'pointer', background: 'none', border: 'none' }}
          >
            ✕ 清除日期
          </button>
        )}
        <span style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 'auto' }}>
          共 {filtered.length} 条
        </span>
      </div>

      {/* ── 汇报列表 ── */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--muted)', fontSize: 13 }}>
          暂无汇报记录
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.map((r, i) => (
            <div
              key={i}
              onClick={() => setReportModal(r)}
              style={{
                padding: '14px 16px',
                background: 'var(--panel2)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                cursor: 'pointer',
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--acc)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--line)')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 15 }}>{r.icon}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--acc)' }}>{r.dept}</span>
                  <span style={{ fontSize: 11, color: 'var(--muted)' }}>{r.mtime}</span>
                </div>
                <span style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--panel)', padding: '2px 8px', borderRadius: 4, border: '1px solid var(--line)' }}>
                  查看详情 →
                </span>
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 5, color: 'var(--text)' }}>{r.title}</div>
              {r.summary && (
                <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                  {r.summary}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── 详情弹窗 ── */}
      {reportModal && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: 20,
          }}
          onClick={() => setReportModal(null)}
        >
          <div
            style={{
              background: 'var(--panel)', borderRadius: 16, maxWidth: 760, width: '100%',
              maxHeight: '85vh', overflow: 'auto', padding: 28,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 22 }}>{reportModal.icon}</span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>{reportModal.dept}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{reportModal.mtime} · {reportModal.file}</div>
                </div>
              </div>
              <button
                onClick={() => setReportModal(null)}
                style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--muted)', padding: '4px 8px' }}
              >✕</button>
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 14, color: 'var(--text)', borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
              {reportModal.title}
            </div>
            <pre style={{ fontSize: 12.5, color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: "'Courier New', monospace", margin: 0, background: 'var(--bg)', padding: 16, borderRadius: 10 }}>
              {reportModal.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
