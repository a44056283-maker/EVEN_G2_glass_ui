# Even Terminal 连接记录

日期：2026-05-01

## 用途

Even Terminal 是让手机 Even App 连接电脑终端代理的工具。截图里的“主机设置”页面对应的是这个功能，不是 `.ehpk` 插件安装页。

## 当前电脑端服务

电脑端已安装：

```bash
npm install -g @evenrealities/even-terminal
```

当前启动命令：

```bash
export PATH="/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/.tools/node-current/bin:$PATH"
even-terminal
```

## 手机页面填写

主机：

```text
192.168.13.104:3456
```

验证权杖：

```text
8122014a59cba73ea981de93dcec196b
```

也可以使用 Even Terminal 输出的二维码或完整 URL：

```text
http://192.168.13.104:3456?token=8122014a59cba73ea981de93dcec196b
```

## 注意

- 手机和电脑必须在同一个 Wi-Fi 或局域网。
- `even-terminal` 进程必须保持运行。
- 如果重启 `even-terminal` 后 token 改变，手机端要重新填写。
- 截图中显示“当前仅支持 Claude Code”，所以它主要是 Claude Code 代理入口；我们的 G2 Vision Voice 插件仍然走 `.ehpk` 或本地调试地址。
