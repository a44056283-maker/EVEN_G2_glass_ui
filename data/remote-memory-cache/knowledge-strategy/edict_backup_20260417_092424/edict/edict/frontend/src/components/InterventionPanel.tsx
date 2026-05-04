import { useEffect, useState, useCallback } from 'react';
import { api } from '../api';

// ── Types ──────────────────────────────────────────────────────────

interface MarketSymbol {
  price: number; change_pct: number; high_24h: number; low_24h: number;
  atr_pct: number; adx: number; rsi: number; bb_width: number;
  vwap: number; vol_ratio: number; obi: number; spread_pct: number;
  ema50: number; ema200: number; funding_rate: number; funding_rate_e8: number;
  bid: number; ask: number;
}
interface MarketData {
  collected_at: string;
  symbols: { BTC?: MarketSymbol; ETH?: { price: number; change_pct: number } };
  sentiment: { fear_greed: number; fg_label: string; btc_dominance: number };
  positions: unknown[];
}
interface TriggeredRule {
  rule_id: string; layer: string; level: string; severity: string;
  urgency: number; triggered: boolean; title: string; reason: string;
  current_value: string; threshold: string; action: string;
}
interface Proposal {
  id: string; rule_id: string; layer: string; level: string;
  severity: string; urgency: number; title: string; reason: string;
  current_value: string; threshold: string; action: string;
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'expired';
  created_at: string; decided_at?: string; decided_by?: string;
  market_data?: { btc_price?: number; fear_greed?: number; fg_label?: string; rsi?: number };
}
interface IvConfig {
  sentiment_levels: Record<string, { label: string; trigger: string; action: string; urgency: number }>;
  black_swan: { fg_threshold: number; urgency_threshold: number; cooldown_hours: number; rejected_cooldown_hours: number };
  risk_params: { liquidation_alert_pct: number; var_95_threshold_pct: number; atr_volatility_multiplier: number; freeze_cooldown_minutes: number; var_lookback_period: number; var_confidence: number };
  action_rules: Record<string, { label: string; color: string; requires_approval: boolean; description: string }>;
  card_colors: Record<string, { header: string; button: string; light_bg: string }>;
  proposal_expiry_minutes: number; fetch_time: string;
}

// ── Utility ──────────────────────────────────────────────────────
function fmtPrice(n: number): string {
  if (!n) return '—';
  return '$' + n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmt(n: number, d = 2): string {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Number(n).toFixed(d);
}
function timeAgo(ts: string): string {
  if (!ts) return '';
  const d = new Date(ts.includes('T') ? ts : ts.replace(' ', 'T') + 'Z');
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return mins + '分钟前';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + '小时前';
  return Math.floor(hrs / 24) + '天前';
}

// ── ALL RULES ─────────────────────────────────────────────────────
const ALL_RULES = [
  { id:'R001', layer:'risk',    title:'单日亏损熔断',       threshold:'≤ -5%',    action:'freeze' },
  { id:'R002', layer:'risk',    title:'单周亏损暂停',       threshold:'≤ -15%',   action:'pause_trading' },
  { id:'R003', layer:'risk',    title:'最大持仓超时',       threshold:'> 48h',    action:'force_close' },
  { id:'R004', layer:'risk',    title:'拖尾止损',           threshold:'> 24h & -2%', action:'force_stop_loss' },
  { id:'M001', layer:'market',  title:'ATR波动率过滤',     threshold:'< 1.5%',   action:'block_entry' },
  { id:'M002', layer:'market',  title:'ADX趋势强度',       threshold:'< 25',     action:'block_entry' },
  { id:'M003', layer:'market',  title:'VWAP偏离过滤',      threshold:'> ±1%',   action:'block_entry' },
  { id:'M004', layer:'market',  title:'EMA50方向信号',     threshold:'顺势',    action:'direction_bias' },
  { id:'F001', layer:'flow',    title:'BTC.Dominance',    threshold:'> 52%',   action:'direction_bias' },
  { id:'F002', layer:'flow',    title:'资金费率预警',      threshold:'> ±0.05%', action:'block_entry' },
  { id:'T001', layer:'tech',    title:'RSI极值',          threshold:'< 30 / > 70', action:'signal_boost' },
  { id:'T002', layer:'tech',    title:'布林带收口',       threshold:'< 80%',    action:'watch_breakout' },
  { id:'T003', layer:'tech',    title:'量能爆发',         threshold:'> 3x',      action:'confirm_breakout' },
  { id:'S001', layer:'sentiment', title:'FG极度恐慌逆向',  threshold:'≤ 10',    action:'reverse_signal' },
  { id:'S002', layer:'sentiment', title:'FG恐惧禁止做空',  threshold:'< 25',    action:'block_short' },
  { id:'S003', layer:'sentiment', title:'FG贪婪禁止做多',  threshold:'> 75',    action:'block_long' },
  { id:'E001', layer:'event',    title:'ETF到期周',        threshold:'每月第四周五', action:'reduce_position' },
];

const LAYER_NAMES: Record<string, string> = {
  risk:'P0 · 风控层', market:'P1 · 市场结构', flow:'P1 · 资金流',
  tech:'P2 · 技术指标', sentiment:'P2 · 市场情绪', event:'P3 · 事件驱动',
};

// ── Icons ────────────────────────────────────────────────────────
function sevIcon(s: string): string {
  return s === 'critical' ? '🚨' : s === 'high' ? '⚠️' : s === 'medium' ? '🟡' : '🟢';
}
function sevColor(s: string): string {
  return s === 'critical' ? 'var(--red)' : s === 'high' ? 'var(--warn)' : s === 'medium' ? 'var(--warn)' : 'var(--green)';
}
function statusBadge(s: string): string {
  const m: Record<string, string> = { pending:'待审批', approved:'已批准', rejected:'已否决', expired:'已过期', executed:'已执行' };
  return `<span class="iv-badge iv-badge-${s === 'approved' || s === 'executed' ? 'approve' : s === 'rejected' ? 'reject' : s === 'pending' ? 'pending' : 'success'}">${m[s] || s}</span>`;
}

// ── Sub-components ────────────────────────────────────────────────

function Icat({ id, title, subtitle, children }: { id: string; title: string; subtitle?: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="icat" id={`icat-${id}`}>
      <div className="icat-hdr" onClick={() => setOpen(!open)} style={{ cursor: 'pointer' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 700 }}>{title}</span>
          {subtitle && <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>{subtitle}</span>}
        </div>
        <span style={{ fontSize: 10, color: 'var(--muted)', transition: 'transform 0.2s', transform: open ? 'rotate(90deg)' : 'none' }}>▶</span>
      </div>
      {open && <div className="icat-body">{children}</div>}
    </div>
  );
}

function ParamRow({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="param-row">
      <span className="param-key">{k}</span>
      <span>{v}</span>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────
export default function InterventionPanel() {
  const [tab, setTab] = useState<'market' | 'signals' | 'config' | 'proposals'>('market');
  const [md, setMd] = useState<MarketData | null>(null);
  const [triggers, setTriggers] = useState<TriggeredRule[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [ivCfg, setIvCfg] = useState<IvConfig | null>(null);
  const [ivHistory, setIvHistory] = useState<unknown[]>([]);
  const [pending, setPending] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState('');
  const [countdown, setCountdown] = useState(30);
  const [runLoading, setRunLoading] = useState(false);
  const [resultMsg, setResultMsg] = useState('');

  const fetchAll = useCallback(async () => {
    try {
      const [mdData, ivData, ivHistData] = await Promise.all([
        api.getInterventionConfig().catch(() => null),
        fetch('/api/qintianjian/market-data', { cache: 'no-store' }).then(r => r.json()).catch(() => null),
        fetch('/api/qintianjian/rules', { cache: 'no-store' }).then(r => r.json()).catch(() => null),
      ]);

      let propData: Proposal[] = [];
      try { propData = await fetch('/api/qintianjian/proposals', { cache: 'no-store' }).then(r => r.json()); }
      catch { propData = []; }

      // 合并两套 proposals
      let allProposals = propData;
      if (ivHistData && Array.isArray(ivHistData)) {
        const ivProposals = (ivHistData as unknown[]).map((p: any) => ({
          id: p.id || p.code || String(Math.random()),
          rule_id: p.action || 'manual',
          layer: 'manual',
          level: 'P0',
          severity: 'high',
          urgency: 7,
          title: p.action || '手动干预',
          reason: p.reason || '',
          current_value: '—',
          threshold: '—',
          action: p.action || 'manual',
          status: (p.result === 'success' ? 'approved' : p.result === 'failed' ? 'rejected' : 'pending') as any,
          created_at: p.timestamp || '',
          market_data: {},
        }));
        allProposals = [...ivProposals, ...allProposals];
      }

      if (mdData) setIvCfg(mdData as IvConfig);
      if (ivData && typeof ivData === 'object' && 'symbols' in ivData) {
        setMd(ivData as MarketData);
      }
      if (ivHistData && typeof ivHistData === 'object' && 'triggered' in ivHistData) {
        setTriggers((ivHistData as any).triggered || []);
      }

      const pendingProps = allProposals.filter((p: Proposal) => p.status === 'pending');
      setProposals(allProposals);
      setPending(pendingProps);
      setLastFetch(new Date().toLocaleTimeString('zh-CN'));
    } catch (e) {
      console.error('Failed to load data', e);
    } finally {
      setLoading(false);
    }
  }, []);

  // Countdown + auto-refresh
  useEffect(() => {
    fetchAll();
    const interval = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { fetchAll(); return 30; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // Manual run (触发规则引擎，发送飞书)
  const handleRun = async () => {
    setRunLoading(true);
    setResultMsg('');
    try {
      const r = await fetch('/api/qintianjian/run', { method: 'POST', cache: 'no-store' });
      const d = await r.json();
      if (d.ok) {
        setResultMsg(`✅ 已提交 ${d.triggered} 条规则至飞书审批`);
        setTimeout(fetchAll, 2000);
      } else {
        setResultMsg('❌ 提交失败: ' + (d.error || '未知错误'));
      }
    } catch (e: any) {
      setResultMsg('❌ 网络错误: ' + e.message);
    } finally {
      setRunLoading(false);
    }
  };

  const handleApprove = async (id: string) => {
    if (!confirm('确认批准此提案？')) return;
    try {
      const r = await fetch(`/qintianjian/approve/${id}`, { method: 'POST', cache: 'no-store' });
      const d = await r.json();
      if (d.ok) {
        setResultMsg(`✅ 提案 ${id} 已批准`);
        setTimeout(fetchAll, 2000);
      } else {
        setResultMsg('❌ 失败: ' + (d.error || '未知错误'));
      }
    } catch (e: any) { setResultMsg('❌ ' + e.message); }
  };

  const handleReject = async (id: string) => {
    try {
      const r = await fetch(`/qintianjian/reject/${id}`, { method: 'POST', cache: 'no-store' });
      const d = await r.json();
      if (d.ok) {
        setResultMsg(`❌ 提案 ${id} 已否决`);
        setTimeout(fetchAll, 2000);
      } else {
        setResultMsg('❌ 失败: ' + (d.error || '未知错误'));
      }
    } catch (e: any) { setResultMsg('❌ ' + e.message); }
  };

  // ── Data ──
  const btc = md?.symbols?.BTC;
  const sentiment = md?.sentiment || { fear_greed: 50, fg_label: 'Neutral', btc_dominance: 50 };
  const fg = sentiment.fear_greed;
  const btcD = sentiment.btc_dominance;
  const triggeredIds = new Set(triggers.map(t => t.rule_id));
  const pendingProps = proposals.filter(p => p.status === 'pending');

  // ── Render ──
  if (loading) return <div style={{ color: 'var(--muted)', padding: 40, textAlign: 'center' }}>⏳ 加载中…</div>;

  const layerOrder = ['risk', 'market', 'flow', 'tech', 'sentiment', 'event'];

  return (
    <div>
      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>⚡ 动态干预中心</span>
          {pendingProps.length > 0 && (
            <span style={{ fontSize: 11, background: '#ff525222', color: 'var(--red)', border: '1px solid var(--red)', borderRadius: 20, padding: '2px 8px', fontWeight: 700 }}>
              {pendingProps.length} 条待审批
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>⟳ {countdown}s</span>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>更新: {lastFetch}</span>
          <button className="btn-refresh" onClick={fetchAll}>🔄 刷新</button>
          <button className="btn-refresh" style={{ borderColor: '#ffd700', color: '#ffd700' }} onClick={handleRun} disabled={runLoading}>
            {runLoading ? '⏳ 运行中…' : '🚀 触发规则引擎'}
          </button>
        </div>
      </div>

      {resultMsg && (
        <div style={{ background: 'var(--panel2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 14px', marginBottom: 12, fontSize: 12 }}>
          {resultMsg}
        </div>
      )}

      {/* ── Alert Banner ── */}
      {pendingProps.length > 0 && (
        <div style={{ background: '#ff525215', border: '1px solid var(--red)', borderRadius: 8, padding: '10px 16px', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 20 }}>🚨</span>
          <span style={{ flex: 1, fontSize: 13 }}>有 <strong style={{ color: 'var(--red)' }}>{pendingProps.length}</strong> 条提案待审批，请及时处理</span>
          <button className="btn-refresh" style={{ borderColor: 'var(--red)', color: 'var(--red)' }} onClick={() => setTab('proposals')}>
            去审批 →
          </button>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="tabs">
        {(['market', 'signals', 'config', 'proposals'] as const).map(t => (
          <div key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t === 'market' && '📊 行情数据'}
            {t === 'signals' && '📡 决策信号'}{triggers.length > 0 && <span style={{ marginLeft: 4, fontSize: 10, background: 'var(--red)', color: '#fff', padding: '1px 5px', borderRadius: 8 }}>{triggers.length}</span>}
            {t === 'config' && '⚙️ 干预配置'}
            {t === 'proposals' && '📋 审批历史'}{pendingProps.length > 0 && <span style={{ marginLeft: 4, fontSize: 10, background: 'var(--warn)', color: '#000', padding: '1px 5px', borderRadius: 8 }}>{pendingProps.length}</span>}
          </div>
        ))}
      </div>

      {/* ── Tab: 行情数据 ── */}
      {tab === 'market' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
          {/* BTC价格 */}
          <div className="stat-card gold">
            <div className="slabel">BTC 价格</div>
            <div className="svalue">{fmtPrice(btc?.price || 0)}</div>
            <div className="ssub">{(btc?.change_pct || 0) >= 0 ? '+' : ''}{fmt(btc?.change_pct || 0)}% · 24h</div>
          </div>
          {/* FG */}
          <div className={`stat-card ${fg <= 25 ? 'red' : fg >= 75 ? 'red' : 'blue'}`}>
            <div className="slabel">Fear &amp; Greed</div>
            <div className="svalue">{fg || '—'}</div>
            <div className="ssub">{sentiment.fg_label || '—'}</div>
          </div>
          {/* RSI */}
          <div className={`stat-card ${(btc?.rsi || 50) < 30 || (btc?.rsi || 50) > 70 ? 'red' : (btc?.rsi || 50) < 40 || (btc?.rsi || 50) > 60 ? 'orange' : 'green'}`}>
            <div className="slabel">RSI 14</div>
            <div className="svalue">{fmt(btc?.rsi || 0, 1)}</div>
            <div className="ssub">{(btc?.rsi || 50) < 30 ? '超卖' : (btc?.rsi || 50) > 70 ? '超买' : '中性'}</div>
          </div>
          {/* ATR% */}
          <div className={`stat-card ${(btc?.atr_pct || 0) < 1.5 ? 'red' : 'orange'}`}>
            <div className="slabel">ATR%</div>
            <div className="svalue">{fmt(btc?.atr_pct || 0, 2)}%</div>
            <div className="ssub">{(btc?.atr_pct || 0) < 1.5 ? '⚠低波动' : '正常'}</div>
          </div>
          {/* BTC.D */}
          <div className="stat-card purple">
            <div className="slabel">BTC.Dominance</div>
            <div className="svalue">{fmt(btcD || 0, 1)}%</div>
            <div className="ssub">{btcD > 52 ? 'BTC强势' : '山寨活跃'}</div>
          </div>
          {/* ADX */}
          <div className="stat-card blue">
            <div className="slabel">ADX 趋势强度</div>
            <div className="svalue">{fmt(btc?.adx || 0, 1)}</div>
            <div className="ssub">{(btc?.adx || 0) < 25 ? '震荡' : (btc?.adx || 0) > 40 ? '强趋势' : '弱趋势'}</div>
          </div>
          {/* Funding */}
          <div className="stat-card">
            <div className="slabel">资金费率 (8h)</div>
            <div className="svalue" style={{ color: Math.abs((btc?.funding_rate_e8 || 0) / 1e8 * 100) > 0.05 ? 'var(--red)' : 'var(--text)' }}>
              {fmt((btc?.funding_rate_e8 || 0) / 1e8 * 100 || 0, 3)}%
            </div>
            <div className="ssub">Gate.io 永续</div>
          </div>
          {/* 持仓 */}
          <div className="stat-card">
            <div className="slabel">当前持仓</div>
            <div className="svalue">{(md?.positions || []).length}</div>
            <div className="ssub">4个Bot汇总</div>
          </div>
        </div>
      )}

      {/* ── Tab: 行情数据 详细面板 ── */}
      {tab === 'market' && btc && (
        <div style={{ marginTop: 16 }}>
          <Icat id="market-detail" title="📊 BTC 详细行情" subtitle={md?.collected_at || ''}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 0 }}>
              {[
                ['24h高', fmtPrice(btc.high_24h), 'up'],
                ['24h低', fmtPrice(btc.low_24h), 'down'],
                ['EMA50', fmtPrice(btc.ema50), btc.price > btc.ema50 ? 'up' : 'down'],
                ['EMA200', fmtPrice(btc.ema200), btc.price > btc.ema200 ? 'up' : 'down'],
                ['VWAP', fmtPrice(btc.vwap), Math.abs(btc.price - btc.vwap) / btc.vwap > 0.01 ? 'warn' : 'neutral'],
                ['布林带宽', fmt(btc.bb_width, 1) + '%', btc.bb_width < 80 ? 'warn' : 'neutral'],
                ['量比', fmt(btc.vol_ratio, 1) + 'x', btc.vol_ratio > 3 ? 'up' : btc.vol_ratio < 0.5 ? 'down' : 'neutral'],
                ['OBI', fmt(btc.obi, 3), btc.obi > 0.2 ? 'up' : btc.obi < -0.2 ? 'down' : 'neutral'],
                ['买卖价差', fmt(btc.spread_pct, 3) + '%', 'neutral'],
                ['买一价', fmtPrice(btc.bid), 'neutral'],
                ['卖一价', fmtPrice(btc.ask), 'neutral'],
              ].map(([label, val, cls]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--line)', fontSize: 12 }}>
                  <span style={{ color: 'var(--muted)' }}>{label}</span>
                  <span style={{
                    fontWeight: 600, fontFamily: 'monospace',
                    color: cls === 'up' ? 'var(--green)' : cls === 'down' ? 'var(--red)' : cls === 'warn' ? 'var(--warn)' : 'var(--text)'
                  }}>{val}</span>
                </div>
              ))}
            </div>
          </Icat>

          {/* 6层信号总览 */}
          <Icat id="layer-summary" title="6层信号状态">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {layerOrder.map(layer => {
                const ltriggers = triggers.filter(r => r.layer === layer);
                const worst = [...ltriggers].sort((a, b) => b.urgency - a.urgency)[0];
                if (!worst) return (
                  <span key={layer} style={{ fontSize: 11, padding: '3px 10px', borderRadius: 20, background: 'var(--panel3)', color: 'var(--muted)', border: '1px solid var(--line)' }}>
                    ✅ {LAYER_NAMES[layer]}
                  </span>
                );
                return (
                  <span key={layer} style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 20, fontWeight: 700,
                    background: worst.severity === 'critical' ? '#ff525222' : worst.severity === 'high' ? '#ff980022' : '#f5c84222',
                    color: sevColor(worst.severity), border: `1px solid ${sevColor(worst.severity)}44`
                  }}>
                    {sevIcon(worst.severity)} {LAYER_NAMES[layer]} U:{worst.urgency}
                  </span>
                );
              })}
            </div>
          </Icat>
        </div>
      )}

      {/* ── Tab: 决策信号 ── */}
      {tab === 'signals' && (
        <div style={{ marginTop: 16 }}>
          {/* 当前触发 */}
          {triggers.length > 0 && (
            <Icat id="triggered" title={`🚨 当前触发 (${triggers.length}条)`} subtitle="按紧急度排序">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[...triggers].sort((a, b) => b.urgency - a.urgency).map(r => (
                  <div key={r.rule_id} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '8px 0', borderBottom: '1px solid var(--line)' }}>
                    <span style={{ fontSize: 18, flexShrink: 0 }}>{sevIcon(r.severity)}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: 13 }}>{r.title}</div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>[{r.level}] {r.rule_id} · {r.layer.toUpperCase()}层</div>
                      <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 4, lineHeight: 1.5 }}>{r.reason}</div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>当前: {r.current_value} | 阈值: {r.threshold}</div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: sevColor(r.severity) }}>U:{r.urgency}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Icat>
          )}

          {triggers.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)' }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
              暂无触发规则，市场状态正常
            </div>
          )}

          {/* 全部规则 */}
          {layerOrder.map(layer => {
            const layerRules = ALL_RULES.filter(r => r.layer === layer);
            const layerTriggers = triggers.filter(r => r.layer === layer);
            return (
              <Icat key={layer} id={`rules-${layer}`} title={LAYER_NAMES[layer]}
                subtitle={`${layerTriggers.length}/${layerRules.length} 触发`}>
                {layerRules.map(rule => {
                  const trig = layerTriggers.find(t => t.rule_id === rule.id);
                  return (
                    <div key={rule.id} style={{ display: 'flex', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--line)', alignItems: 'center' }}>
                      <span style={{ fontSize: 14, width: 20, textAlign: 'center', flexShrink: 0 }}>
                        {trig ? sevIcon(trig.severity) : '✅'}
                      </span>
                      <div style={{ flex: 1 }}>
                        <span style={{ fontWeight: 600, fontSize: 12, color: trig ? 'var(--red)' : 'var(--text)' }}>{rule.title}</span>
                        <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 8 }}>阈值: {rule.threshold}</span>
                        {trig && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{trig.reason}</div>}
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        {trig ? (
                          <span style={{ fontSize: 11, fontWeight: 700, color: sevColor(trig.severity) }}>U:{trig.urgency}</span>
                        ) : (
                          <span style={{ fontSize: 11, color: 'var(--green)' }}>正常</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </Icat>
            );
          })}
        </div>
      )}

      {/* ── Tab: 干预配置 ── */}
      {tab === 'config' && ivCfg && (
        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* 左侧：情绪等级 + 黑天鹅 + 风控 */}
          <div>
            <Icat id="sent-levels" title="📊 L1~L6 干预等级阈值">
              {Object.entries(ivCfg.sentiment_levels).map(([k, v]) => (
                <ParamRow key={k} k={`${k} · ${v.label}`}
                  v={<span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{v.trigger}</span>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 20,
                        background: v.urgency >= 7 ? '#ff525222' : v.urgency >= 4 ? '#f5c84222' : '#3fb95022',
                        color: v.urgency >= 7 ? 'var(--red)' : v.urgency >= 4 ? 'var(--warn)' : 'var(--green)',
                        border: `1px solid ${v.urgency >= 7 ? 'var(--red)' : v.urgency >= 4 ? 'var(--warn)' : 'var(--green)'}55`
                      }}>U{v.urgency}</span>
                    </span>}
                />
              ))}
            </Icat>

            <Icat id="bs-rules" title="🚨 黑天鹅规则">
              <ParamRow k="FG 恐慌阈值" v={<span style={{ fontWeight: 700, color: 'var(--red)' }}>≤ {ivCfg.black_swan.fg_threshold}</span>} />
              <ParamRow k="紧急度触发" v={<span style={{ fontWeight: 700, color: 'var(--warn)' }}>≥ {ivCfg.black_swan.urgency_threshold}</span>} />
              <ParamRow k="黑天鹅冷却" v={<span>{ivCfg.black_swan.cooldown_hours} 小时</span>} />
              <ParamRow k="拒绝冷却" v={<span>{ivCfg.black_swan.rejected_cooldown_hours} 小时</span>} />
            </Icat>

            <Icat id="risk-params" title="🛡️ 风控阈值">
              <ParamRow k="强平报警距离" v={<span style={{ color: 'var(--warn)', fontWeight: 700 }}>{ivCfg.risk_params.liquidation_alert_pct}%</span>} />
              <ParamRow k="VaR 95% 阈值" v={<span>{ivCfg.risk_params.var_95_threshold_pct}%</span>} />
              <ParamRow k="ATR 波动乘数" v={<span>× {ivCfg.risk_params.atr_volatility_multiplier}</span>} />
              <ParamRow k="VaR 回望期" v={<span>{ivCfg.risk_params.var_lookback_period} 天</span>} />
              <ParamRow k="VaR 置信度" v={<span>{((ivCfg.risk_params.var_confidence || 0.95) * 100).toFixed(0)}%</span>} />
              <ParamRow k="冻结冷却" v={<span>{ivCfg.risk_params.freeze_cooldown_minutes} 分钟</span>} />
            </Icat>
          </div>

          {/* 右侧：动作规则 + 卡片样式 */}
          <div>
            <Icat id="action-rules" title="⚡ 干预动作规则" subtitle={`${Object.keys(ivCfg.action_rules || {}).length} 种动作`}>
              {Object.entries(ivCfg.action_rules || {}).map(([k, v]) => (
                <ParamRow key={k} k={v.label || k}
                  v={<span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 10, color: 'var(--muted)' }}>{v.description}</span>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 20,
                        background: '#f5c84222', color: 'var(--warn)', border: '1px solid #f5c84255'
                      }}>{v.requires_approval ? '需审批' : '直接执行'}</span>
                    </span>}
                />
              ))}
            </Icat>

            <Icat id="card-colors" title="🎨 飞书卡片样式" subtitle={`审批有效期 ${ivCfg.proposal_expiry_minutes} 分钟`}>
              <ParamRow k="审批有效期" v={<span>{ivCfg.proposal_expiry_minutes} 分钟</span>} />
              {Object.entries(ivCfg.card_colors || {}).map(([k, v]) => (
                <ParamRow key={k} k={k}
                  v={<span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ display: 'inline-block', width: 14, height: 14, borderRadius: 3, background: v.light_bg, border: `1px solid ${v.header === 'red' ? '#C62828' : v.header === 'green' ? '#2E7D32' : v.header === 'blue' ? '#1565C0' : '#E65100'}` }} />
                      <span style={{ fontSize: 10, color: 'var(--muted)' }}>{v.header}</span>
                    </span>}
                />
              ))}
            </Icat>
          </div>
        </div>
      )}

      {/* ── Tab: 审批历史 ── */}
      {tab === 'proposals' && (
        <div style={{ marginTop: 16 }}>
          {pendingProps.length > 0 && (
            <Icat id="pending-props" title={`📋 待审批提案 (${pendingProps.length}条)`} subtitle="尚书省审批">
              {pendingProps.map(p => (
                <div key={p.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--line)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 700 }}>{p.title}</span>
                    <span className="iv-badge iv-badge-pending">待审</span>
                    <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 'auto' }}>{p.id}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
                    当前: <span style={{ color: 'var(--text)' }}>{p.current_value}</span> | 阈值: {p.threshold}
                  </div>
                  {p.reason && <div style={{ fontSize: 12, color: 'var(--text)', marginBottom: 4 }}>{p.reason}</div>}
                  {p.market_data?.btc_price && (
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 6 }}>
                      BTC: {fmtPrice(p.market_data.btc_price)} | FG: {p.market_data.fear_greed || '—'}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    <button className="btn-refresh" style={{ borderColor: 'var(--green)', color: 'var(--green)' }} onClick={() => handleApprove(p.id)}>
                      ✅ 批准
                    </button>
                    <button className="btn-refresh" style={{ borderColor: 'var(--red)', color: 'var(--red)' }} onClick={() => handleReject(p.id)}>
                      ❌ 否决
                    </button>
                  </div>
                </div>
              ))}
            </Icat>
          )}

          {proposals.length === 0 && pendingProps.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)' }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>📋</div>
              暂无审批记录
            </div>
          )}

          {proposals.filter(p => p.status !== 'pending').length > 0 && (
            <Icat id="decided-props" title="📜 历史记录">
              {proposals.filter(p => p.status !== 'pending').slice(0, 30).map(p => (
                <div key={p.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--line)', opacity: p.status === 'rejected' ? 0.6 : 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{p.title}</span>
                    <span dangerouslySetInnerHTML={{ __html: statusBadge(p.status) }} />
                    <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 'auto' }}>{p.id}</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                    [{p.rule_id}] {p.created_at} → {p.decided_at || '—'} {p.decided_by || ''}
                  </div>
                </div>
              ))}
            </Icat>
          )}
        </div>
      )}
    </div>
  );
}
