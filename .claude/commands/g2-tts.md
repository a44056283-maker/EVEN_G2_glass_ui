---
description: 恢复天禄萝莉音 female-shaonv，避免退回机械系统音
---

请读取 CLAUDE.md。

任务：恢复萝莉音朗读。

要求：
1. 默认 voiceId = female-shaonv
2. 设置页默认也是 female-shaonv
3. 优先播放 /tts 返回音频
4. 明确显示当前朗读来源：MiniMax TTS / 系统 fallback
5. 增加试听当前声音按钮
6. 不改视觉/语音/交易业务逻辑

执行 typecheck/build/pack:g2，并写报告。
