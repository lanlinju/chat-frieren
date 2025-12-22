# Chat Frieren

一个基于 DeepSeek API 的交互式 AI 聊天应用，以《葬送的芙莉莲》中的精灵魔法使芙莉莲的角色进行对话。

## 功能特性

- **角色扮演**：AI 以芙莉莲的身份进行对话，具有内敛的性格和独特的时间感知
- **流式响应**：实时显示 AI 生成的回复，支持实时流式输出
- **对话管理**：
  - 自动保存对话历史到 JSON 文件
  - 支持对话内容智能总结（使用 `/s` 命令压缩 3/4 的对话以避免上下文过长）
  - 自动备份历史对话数据
- **持久化存储**：对话历史可在应用重启后继续访问

## 前置要求

- Python 3.7+
- DeepSeek API 密钥

## 安装

1. **克隆或下载项目**
```bash
cd chat-frieren
```

2. **安装依赖**
```bash
pip install requests
```

3. **配置 API 密钥**
设置环境变量 `DEEPSEEK_API_KEY`：

```bash
export DEEPSEEK_API_KEY="your-api-key-here"
```

## 使用方法

### 启动应用

```bash
./chat.py
```

或者

```bash
python3 chat.py
```

### 命令列表

| 命令 | 功能 |
|------|------|
| 任意文本 | 与芙莉莲进行对话 |
| `/s` | 总结对话内容（保留最新 1/4 的对话） |
| `exit` | 保存对话历史并退出程序 |
| `Ctrl+C` | 中断程序（自动保存对话历史） |

## 运行示例

```bash
➜  chat-frieren git:(main) ✗ ./chat.py
DeepSeek 聊天客户端 (输入 'exit' 退出, '/s' 总结对话)

You: hi

Frieren: （轻轻点头）你好。这个时间对人类来说应该很晚了。

You:
```

## 项目结构

```
chat-frieren/
├── chat.py              # 主程序文件
├── chat_history.json    # 对话历史（自动生成）
├── backup/              # 对话历史备份目录（自动生成）
└── README.md            # 项目文档
```

## 文件说明

### chat_history.json

存储对话历史的 JSON 文件，包含：
- 系统角色设定
- 用户消息和 AI 回复
- 对话日期和时间戳
- 对话总结（在执行总结命令后）

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | ✓ |

## 常见问题

### 如何重新开始对话？

删除 `chat_history.json` 文件，重新启动程序即可。

### 对话历史如何备份？

执行 `/s` 命令时会自动备份历史对话到 `backup/` 目录，文件名格式为 `chat_history.json.backup.YYYYMMdd_HHMMSS`。

### API 调用失败怎么办？

1. 检查 `DEEPSEEK_API_KEY` 环境变量是否正确设置
2. 确保网络连接正常
3. 检查 API 密钥是否有效且未过期
