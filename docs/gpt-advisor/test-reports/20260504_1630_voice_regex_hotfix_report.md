# 语音意图正则热修报告

生成时间：2026-05-04 16:30
任务名：P0-VOICE-REGEX-HOTFIX-001

## 来源

GPT Review: NEEDS_SMALL_FIX_THEN_TRUE_DEVICE_SMOKE (GPT_REVIEW_20260504_1600_commit_c8065b9)

---

## 热修内容

### isVisionVoiceIntent 正则修复

**文件**：`apps/evenhub-plugin/src/main.ts:1984`

**问题**：原正则 `瞧一瞧/瞅一瞅` 放在 `看(...)` 组内，导致匹配结果为"看瞧一瞧"而非独立词汇；且缺少"这是啥"。

**修复后正则**：
```typescript
function isVisionVoiceIntent(text: string): boolean {
  return /(?:帮我|你帮我)?(?:看看|看一下|看一看|看一眼|瞧一下|瞧一瞧|瞅一下|瞅一瞅|看这个|看这里|看前面)|(?:这是啥|这是什么|这是什么呀|这是什么东西)|(?:识别一下|识别这个|拍一下|拍照|读一下|读这段|屏幕内容|图片内容|前面是什么|看看屏幕|看看前面)/.test(text)
}
```

**新增覆盖**：
- `帮我瞧一瞧` ✓
- `帮我瞅一瞅` ✓
- `你帮我看看` ✓
- `瞧一瞧`（独立） ✓
- `瞅一瞅`（独立） ✓
- `这是啥` ✓
- `看一眼` ✓

---

## 测试结果

| 测试项 | 结果 |
|--------|------|
| typecheck | ✓ PASSED |
| build | ✓ PASSED (30 modules, 193.84 kB JS) |
| pack:g2 | ✓ PASSED (79586 bytes) |

---

## EHPK 信息

- **版本**：0.5.5
- **SHA256**：`c36813e7669c7bb2ff3d380450fed35550ccf63f697ed339bab1acc79364ccbf`
- **大小**：79586 bytes
- **路径**：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

---

## 真机冒烟验收清单

**✓ 全部通过（2026-05-04 真机测试）**

| # | 验收项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 首页 4 菜单 + R1 切换 | ✓ 通过 | |
| 2 | 手机取消拍照/选图 → G2 返回首页 | ✓ 通过 | |
| 3 | "帮我看一看这是什么" → 触发视觉 | ✓ 通过 | |
| 4 | "这是啥" → 触发视觉 | ✓ 通过 | |
| 5 | "瞧一瞧" → 触发视觉 | ✓ 通过 | |
| 6 | 交易 R1 next/previous 切标签，click 进详情 | ✓ 通过 | |

---

## GitHub Commit

**Commit**: `892f9e2`
**链接**: https://github.com/a44056283-maker/EVEN_G2_glass_ui/commit/892f9e2

**真机验收确认时间**: 2026-05-04
