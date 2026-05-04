# GPT_REVIEW_TEMPLATE

文件名：
GPT_REVIEW_YYYYMMDD_HHMM_<task_name>.md

## 1. 审批结论

状态：APPROVED / NEEDS_FIX / BLOCKED

## 2. 本轮通过项

- 
- 
- 

## 3. 阻塞问题

- 
- 
- 

## 4. 必须整改

### 整改 1

文件：

要求：

验收：

### 整改 2

文件：

要求：

验收：

## 5. 禁止修改

- 不要改手机网页 UI，除非本轮 review 明确要求
- 不要改 Glass UI，除非本轮 review 明确要求
- 不要改视觉/语音/交易业务逻辑，除非本轮 review 明确要求
- 不要输出 .env、API key、token、密码、交易密钥、私钥

## 6. Claude 下一步执行口径

请读取本 GPT_REVIEW，逐条整改，不要扩大范围。
完成后重新运行 typecheck/build/pack:g2，并生成新的 test report 和 review bundle。
