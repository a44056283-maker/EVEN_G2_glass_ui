# GPT Advisor Folder

本目录是 GPT 桌面版、Codex 与用户协作完成 `天禄 G2 运维助手` 的固定工作台。

以后所有 GPT 建议、审核问题、Codex 提示词、审计报告、模块整改任务、交接记录、测试报告，都统一放在这里，避免信息散落在聊天记录和临时文件里。

## 目录用途

| 路径 | 用途 |
| --- | --- |
| `CURRENT_STATUS.md` | 当前项目状态、已完成内容、关键阻塞 |
| `NEXT_ACTIONS.md` | 下一步任务队列，Codex 按此执行 |
| `ISSUE_REGISTER.md` | 所有已知问题、严重程度、状态 |
| `DECISION_LOG.md` | 架构与产品决策记录 |
| `MODULE_MAP.md` | 模块划分、代码路径、责任边界 |
| `prompts/` | GPT 给 Codex 的执行提示词 |
| `audits/` | GPT 或 Codex 的整体审计报告 |
| `module-reviews/` | 单模块专项评估 |
| `patch-requests/` | 具体整改任务 |
| `handoffs/` | Codex/GPT/用户之间的交接记录 |
| `test-reports/` | 测试结果、EHPK、SHA256、真机反馈 |
| `screenshots/` | 截图、真机画面、问题图片说明 |

## 协作规则

1. GPT 新建议放入 `prompts/`。
2. 具体整改任务放入 `patch-requests/`。
3. 审计结论放入 `audits/`。
4. 模块专项评估放入 `module-reviews/`。
5. 交接记录放入 `handoffs/`。
6. 测试结果、包路径、SHA256 放入 `test-reports/`。
7. 所有问题必须同步登记到 `ISSUE_REGISTER.md`。
8. 下一步只看 `NEXT_ACTIONS.md`，避免多线混修。
9. 不在本目录写入 API Key、Token、密码、私钥等敏感信息。

## 当前原则

- 手机网页 UI 与 G2 眼镜端 UI 必须分离。
- G2 眼镜端按 576 x 288 固定画布设计。
- G2 端优先使用单 `TextContainerProperty` 保证稳定显示。
- R1 目标控制：菜单切换、拍照、发送、取消。
- G2 麦克风主链路：`audioControl(true)` -> `audioEvent.audioPcm` -> WebSocket -> 后端。
- 浏览器麦克风只能做可选兜底，不能作为 G2 主链路。
- 当前 ASR 未真实配置，不能假装成功。
- OpenCLAW 问答可能超时，必须有本地 fallback。
- 交易相关第一版只读，不执行下单、平仓、改策略、改杠杆等真实动作。

