import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { api, type BotInfo, type BotPosition } from '../api';

const BOTS: BotInfo[] = [
  { port: 9090, label: 'Gate-17656685222', exchange: 'Gate.io', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
  { port: 9091, label: 'Gate-85363904550', exchange: 'Gate.io', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
  { port: 9092, label: 'Gate-15637798222', exchange: 'Gate.io', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
  { port: 9093, label: 'OKX-15637798222', exchange: 'OKX', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
  { port: 9094, label: 'OKX-BOT85363904550', exchange: 'OKX', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
  { port: 9095, label: 'OKX-BOTa44056283', exchange: 'OKX', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
  { port: 9096, label: 'OKX-BHB16638759999', exchange: 'OKX', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
  { port: 9097, label: 'OKX-17656685222', exchange: 'OKX', total: 0, starting_capital: 0, profit: 0, profit_pct: 0, online: false },
];

const TRADING_PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'BNB_USDT', 'XRP_USDT', 'DOGE_USDT', 'ADA_USDT', 'AVAX_USDT'];

// ── 排行榜渲染函数（同步9099监控台格式） ──
function renderRankPanel(
  title: string,
  accentColor: string,
  sorted: BotInfo[],
  valueKey: (b: BotInfo) => number,
  unit: string
) {
  const max = sorted.reduce((m, b) => Math.max(m, Math.abs(valueKey(b))), 0) || 1;

  return (
    <div style={panel}>
      <div style={{ ...panelTitle, color: accentColor, display: 'flex', alignItems: 'center', gap: 4 }}>
        {title}
      </div>
      {sorted.length === 0 ? (
        <div style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center', padding: '16px 0' }}>暂无数据</div>
      ) : sorted.map((b, i) => {
        const val = valueKey(b);
        const absVal = Math.abs(val);
        const isPos = val >= 0;
        const medal = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '';
        const rkClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : '';
        const exColor = b.exchange === 'Gate.io' ? '#a29bfe' : '#74b9ff';
        const shortName = (b.label.split('-')[1] || b.label);
        const barColor = unit === '%' ? (isPos ? '#3fb950' : '#f85149') : '#ffc107';
        const valColor = unit === '%' ? (isPos ? '#3fb950' : '#f85149') : 'var(--text)';
        const displayVal = unit === '%' ? `${isPos ? '+' : '-'}${absVal.toFixed(2)}%`
          : `${isPos && val > 0 ? '+' : ''}$${absVal.toFixed(0)}`;

        return (
          <div key={b.port} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 0', borderBottom: '1px solid #1c2128', fontSize: 11,
          }}>
            <span style={{
              width: 20, textAlign: 'center', fontSize: medal ? 13 : 11,
              color: rkClass === 'gold' ? '#ffc107' : rkClass === 'silver' ? '#adb5bd' : rkClass === 'bronze' ? '#cd7f32' : '#555',
            }}>
              {medal || (i + 1)}
            </span>
            <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text)', fontWeight: 600 }} title={b.label}>
              {shortName}
              <span style={{ fontSize: 8, color: exColor, marginLeft: 3 }}>{b.exchange}</span>
            </span>
            <div style={{ flex: '0 0 40px', height: 3, background: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: `${(absVal / max * 100).toFixed(0)}%`, height: '100%', background: barColor, borderRadius: 2, opacity: 0.75 }} />
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: valColor, flexShrink: 0 }}>
              {displayVal}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function fmt(n: number) { return isNaN(n) ? '—' : '$' + n.toFixed(2); }
function pct(n: number) { return (n >= 0 ? '+' : '') + (isNaN(n) ? '—' : n.toFixed(2) + '%'); }

export default function TradingBotPanel() {
  const botsData = useStore((s) => s.botsData);
  const botsPositions = useStore((s) => s.botsPositions);
  const loadBots = useStore((s) => s.loadBots);
  const toast = useStore((s) => s.toast);

  const [group, setGroup] = useState<'all' | 'gate' | 'okx'>('all');
  const [selBot, setSelBot] = useState(9090);
  const [selPair, setSelPair] = useState('BTC_USDT');
  const [selSide, setSelSide] = useState('long');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadBots();
    const id = setInterval(loadBots, 30_000);
    return () => clearInterval(id);
  }, [loadBots]);

  // Merge API data into static bots list
  const bots: BotInfo[] = BOTS.map(b => {
    const d = botsData?.bots?.find(x => x.port === b.port);
    return d ? { ...b, ...d } : b;
  });

  // Sort by port
  const sortedBots = [...bots].sort((a, b) => a.port - b.port);

  const filtered = sortedBots.filter(b => {
    if (group === 'gate') return b.exchange === 'Gate.io';
    if (group === 'okx') return b.exchange === 'OKX';
    return true;
  });

  const positions: BotPosition[] = botsPositions?.positions ?? [];
  const totalEquity = bots.reduce((s, b) => s + b.total, 0);
  const totalProfit = bots.reduce((s, b) => s + b.profit, 0);
  const totalStart = bots.reduce((s, b) => s + b.starting_capital, 0);
  const overallPct = totalStart > 0 ? (totalProfit / totalStart * 100) : 0;

  const handleForceEntry = async () => {
    setLoading(true);
    try {
      const res = await api.botsForceEntry(selBot, selPair, selSide);
      if (res.ok) {
        toast(`${selPair} ${selSide === 'long' ? '做多' : '做空'} 开仓成功`, 'ok');
        setTimeout(loadBots, 2000);
      } else {
        toast('开仓失败: ' + (res.error || '未知'), 'err');
      }
    } catch (e) {
      toast('请求失败', 'err');
    } finally {
      setLoading(false);
    }
  };

  const handleForceExit = async (port: number, tradeId: string) => {
    try {
      const res = await api.botsForceExit(port, tradeId);
      if (res.ok) {
        toast('平仓成功', 'ok');
        setTimeout(loadBots, 2000);
      } else {
        toast('平仓失败: ' + (res.error || '未知'), 'err');
      }
    } catch {
      toast('请求失败', 'err');
    }
  };

  return (
    <div>
      {/* ── Manual Trading ── */}
      <div style={{ ...panel, marginBottom: 14 }}>
        <div style={panelTitle}>⚡ 手动干预</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>账户</span>
          <select value={selBot} onChange={e => setSelBot(Number(e.target.value))} style={sel}>
            <optgroup label="Gate.io">
              <option value={9090}>Gate-17656685222 (:9090)</option>
              <option value={9091}>Gate-85363904550 (:9091)</option>
              <option value={9092}>Gate-15637798222 (:9092)</option>
            </optgroup>
            <optgroup label="OKX">
              <option value={9093}>OKX-15637798222 (:9093)</option>
              <option value={9094}>OKX-BOT85363904550 (:9094)</option>
              <option value={9095}>OKX-BOTa44056283 (:9095)</option>
              <option value={9096}>OKX-BHB16638759999 (:9096)</option>
              <option value={9097}>OKX-17656685222 (:9097)</option>
            </optgroup>
          </select>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>交易对</span>
          <select value={selPair} onChange={e => setSelPair(e.target.value)} style={sel}>
            {TRADING_PAIRS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>方向</span>
          <select value={selSide} onChange={e => setSelSide(e.target.value)} style={sel}>
            <option value="long">做多 ↗</option>
            <option value="short">做空 ↘</option>
          </select>
          <button onClick={handleForceEntry} disabled={loading}
            style={loading ? { ...goBtn, opacity: 0.5 } : goBtn}>
            {loading ? '执行中…' : '▶ 执行开仓'}
          </button>
        </div>
      </div>

      {/* ── Positions Table ── */}
      <div style={panel}>
        <div style={panelTitle}>
          🤖 实时持仓 ({positions.length} 笔) &nbsp;
          <span style={{ color: 'var(--ok)', fontWeight: 600 }}>
            {fmt(botsPositions?.total_pnl ?? 0)}
          </span>
        </div>
        {positions.length === 0 ? (
          <div style={{ color: 'var(--muted)', fontSize: 12, padding: '12px 0' }}>暂无持仓</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--line)' }}>
                  {['账户', '交易对', '方向', '杠杆', '数量', '开仓价', '当前价', '强平价', '未实现盈亏', '操作'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--muted)', fontWeight: 500, fontSize: 10, textTransform: 'uppercase', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map(pos => (
                  <tr key={`${pos.port}-${pos.trade_id}`} style={{ borderBottom: '1px solid #0f1219' }}>
                    <td style={{ padding: '7px 8px' }}>
                      <span style={{
                        fontSize: 9, padding: '2px 6px', borderRadius: 10,
                        background: pos.exchange === 'Gate.io' ? 'rgba(108,92,231,0.2)' : 'rgba(9,132,227,0.2)',
                        color: pos.exchange === 'Gate.io' ? '#a29bfe' : '#74b9ff',
                      }}>
                        {pos.exchange}
                      </span>
                    </td>
                    <td style={{ padding: '7px 8px', fontWeight: 700 }}>{pos.pair}</td>
                    <td style={{ padding: '7px 8px', color: pos.side === 'LONG' ? 'var(--ok)' : 'var(--danger)', fontWeight: 600 }}>
                      {pos.side === 'LONG' ? '↗ 多' : '↘ 空'}
                    </td>
                    <td style={{ padding: '7px 8px' }}>{pos.leverage}x</td>
                    <td style={{ padding: '7px 8px' }}>{pos.amount.toFixed(4)}</td>
                    <td style={{ padding: '7px 8px' }}>{fmt(pos.entry_price)}</td>
                    <td style={{ padding: '7px 8px' }}>{fmt(pos.current_price)}</td>
                    <td style={{ padding: '7px 8px', color: 'var(--muted)' }}>{fmt(pos.liquidation_price)}</td>
                    <td style={{ padding: '7px 8px', fontWeight: 700, color: pos.unrealized_pnl >= 0 ? 'var(--ok)' : 'var(--danger)' }}>
                      {pos.unrealized_pnl >= 0 ? '+' : ''}{fmt(pos.unrealized_pnl)}
                      <span style={{ fontSize: 10, marginLeft: 4 }}>({pct(pos.profit_pct)})</span>
                    </td>
                    <td style={{ padding: '7px 8px' }}>
                      <button onClick={() => handleForceExit(pos.port, pos.trade_id)} style={closeBtn}>
                        平仓
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Top Stats ── */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14, marginBottom: 14 }}>
        <div style={statCard}>
          <div style={statLabel}>总净值</div>
          <div style={{ ...statValue, color: 'var(--text)' }}>{fmt(totalEquity)}</div>
        </div>
        <div style={statCard}>
          <div style={statLabel}>总收益</div>
          <div style={{ ...statValue, color: totalProfit >= 0 ? 'var(--ok)' : 'var(--danger)' }}>
            {totalProfit >= 0 ? '+' : ''}{fmt(totalProfit)}
          </div>
        </div>
        <div style={statCard}>
          <div style={statLabel}>收益率</div>
          <div style={{ ...statValue, color: overallPct >= 0 ? 'var(--ok)' : 'var(--danger)' }}>
            {pct(overallPct)}
          </div>
        </div>
        <div style={statCard}>
          <div style={statLabel}>持仓</div>
          <div style={{ ...statValue, color: positions.length > 0 ? 'var(--warn)' : 'var(--muted)' }}>
            {positions.length} 笔
          </div>
        </div>
        <div style={{ ...statCard, marginLeft: 'auto' }}>
          <div style={statLabel}>在线</div>
          <div style={{ ...statValue, color: 'var(--ok)' }}>
            {bots.filter(b => b.online).length}/8
          </div>
        </div>
      </div>

      {/* ── Group Tabs ── */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12, alignItems: 'center' }}>
        {([['all','全部'],['gate','Gate.io'],['okx','OKX']] as const).map(([g, l]) => (
          <button key={g} onClick={() => setGroup(g)}
            style={{ ...tabBtn, ...(group === g ? tabBtnActive : {}) }}>
            {l}
          </button>
        ))}
        <button className="btn-refresh" onClick={() => loadBots()} style={{ marginLeft: 8 }}>
          🔄 刷新
        </button>
      </div>

      {/* ── Bot Cards Grid (sorted by port) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8, marginBottom: 14 }}>
        {filtered.map(b => (
          <div key={b.port} style={botCard(b)}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 700 }}>
                {(b.label.split('-')[1] || b.label)} &nbsp;
                <span style={{ fontSize: 9, color: 'var(--muted)' }}>:{b.port}</span>
              </div>
              <div style={{
                fontSize: 9, padding: '2px 6px', borderRadius: 10,
                background: b.exchange === 'Gate.io' ? 'rgba(108,92,231,0.2)' : 'rgba(9,132,227,0.2)',
                color: b.exchange === 'Gate.io' ? '#a29bfe' : '#74b9ff',
              }}>{b.exchange}</div>
            </div>
            <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text)' }}>{fmt(b.total)}</div>
            <div style={{ fontSize: 11, color: b.profit >= 0 ? 'var(--ok)' : 'var(--danger)', fontWeight: 600 }}>
              {b.profit >= 0 ? '+' : ''}{fmt(b.profit)} &nbsp; {pct(b.profit_pct)}
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>
              起始 {fmt(b.starting_capital)}
            </div>
            <div style={{ fontSize: 10, color: b.online ? 'var(--ok)' : 'var(--danger)', marginTop: 2 }}>
              {b.online ? '🟢 在线' : '🔴 离线'}
            </div>
          </div>
        ))}
      </div>

      {/* ── Rankings (同步9099监控台格式) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        {renderRankPanel(
          '📈 盈利率排行',
          'var(--ok)',
          [...bots].filter(b => b.online).sort((a, b) => (b.profit_pct || 0) - (a.profit_pct || 0)),
          b => b.profit_pct || 0,
          '%'
        )}
        {renderRankPanel(
          '🏆 净值排行',
          '#ffc107',
          [...bots].sort((a, b) => (b.total || 0) - (a.total || 0)),
          b => b.total || 0,
          ''
        )}
        {renderRankPanel(
          '💎 浮盈排行',
          'var(--acc)',
          [...bots].sort((a, b) => (b.profit || 0) - (a.profit || 0)),
          b => b.profit || 0,
          ''
        )}
      </div>
    </div>
  );
}

// ── Styles ──

const statCard: React.CSSProperties = {
  background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8,
  padding: '8px 14px', minWidth: 100, flex: 1,
};
const statLabel: React.CSSProperties = {
  fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1,
};
const statValue: React.CSSProperties = {
  fontSize: 17, fontWeight: 800, marginTop: 2,
};

const panel: React.CSSProperties = {
  background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10, padding: 12,
};
const panelTitle: React.CSSProperties = {
  fontSize: 10, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase',
  letterSpacing: 1, marginBottom: 10,
};

const tabBtn: React.CSSProperties = {
  padding: '3px 10px', borderRadius: 6, border: '1px solid var(--line)',
  background: 'transparent', color: 'var(--muted)', fontSize: 11, cursor: 'pointer',
};
const tabBtnActive: React.CSSProperties = {
  background: 'rgba(106,158,255,0.15)', color: 'var(--acc)', borderColor: 'var(--acc)',
};

function botCard(b: BotInfo): React.CSSProperties {
  return {
    background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 10,
    padding: '10px 12px',
    borderColor: b.online ? (b.profit >= 0 ? '#2ecc8a22' : '#ff527022') : 'var(--line)',
    boxShadow: b.online && b.profit > 0 ? '0 0 12px rgba(46,204,138,0.08)' : 'none',
  };
}

const closeBtn: React.CSSProperties = {
  background: '#ff527033', color: 'var(--danger)', border: '1px solid #ff527066',
  borderRadius: 5, fontSize: 10, padding: '2px 8px', cursor: 'pointer',
};
const goBtn: React.CSSProperties = {
  background: 'var(--acc)', color: '#fff', border: 'none',
  borderRadius: 6, fontSize: 11, padding: '5px 14px', cursor: 'pointer', fontWeight: 700,
};
const sel: React.CSSProperties = {
  padding: '4px 8px', borderRadius: 6, border: '1px solid var(--line)',
  background: 'var(--panel2)', color: 'var(--text)', fontSize: 11,
};
