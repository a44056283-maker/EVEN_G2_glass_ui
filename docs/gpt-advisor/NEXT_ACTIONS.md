# 下一步任务

更新时间：2026-05-04

## 当前阶段

```
P0 CORE TRUE_DEVICE PASSED
Release Candidate: 0.5.5
```

## P1-STABILIZE-001（下一阶段）

不再随机修改 P0 已通过功能。下一阶段进入稳定性整理：

### 稳定性任务

1. **视觉识别连续稳定性**
   - 连续 10 次拍照识别，记录失败次数和原因
   - 取消流程再次确认

2. **呼叫天禄语音链路稳定性**
   - G2 麦克风 PCM 持续观察
   - ASR 文本识别率确认

3. **TTS 试听和朗读来源确认**
   - 确认 female-shaonv 走 MiniMax TTS
   - 确认不是 speechSynthesis fallback

4. **交易状态只读摘要优化**
   - 6 标签分类真机确认
   - AI 评测内容质量确认

5. **发布候选版整理**
   - 确认所有 P0 已通过功能无回归
   - 整理 Release Note

## 暂缓任务

- 实时观察 / liveVisionSampler
- 视频片段总结
- 场景记忆
- 交易写操作
- 复杂眼镜 UI 重写

## 禁止事项

- 不要修改 P0 已通过功能的代码（除非用户发现回归）
- 不要推进暂缓任务
- 不要做交易写操作
- 不要改 .env / key / token

## 当前 EHPK

- **版本**：0.5.5
- **SHA256**：`c36813e7669c7bb2ff3d380450fed35550ccf63f697ed339bab1acc79364ccbf`
- **路径**：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
