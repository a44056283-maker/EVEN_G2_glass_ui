# GPT 审核响应目录

## 目录结构

```
04_GPT_REVIEW_RESPONSES/
├── README.md          # 本文件
├── pending/           # GPT 审核意见放这里
├── applied/           # Claude 执行完后移到这里
└── archive/           # 历史归档
```

## 工作流程

1. **GPT 审核意见** → 放入 `pending/GPT_REVIEW_xxx.md`
2. **Claude 读取** → `pending/GPT_REVIEW_xxx.md`
3. **执行整改** → 完成后复制到 `applied/`
4. **历史归档** → `archive/`

## 安全规则

**禁止放入以下内容**：
- `.env`
- API keys
- tokens
- 交易密钥
- 私钥
- 助记词
- 任何敏感凭证

## 文件命名规范

```
GPT_REVIEW_YYYYMMDD_HHMM_<task_name>.md
```

例如：
```
GPT_REVIEW_20260504_1200_day1_sprint.md
```