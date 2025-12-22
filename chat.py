#!/usr/bin/env python3

import sys
import os
import requests
import json
import shutil
from datetime import datetime
from typing import Generator, List, Dict

# 配置API参数
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("❌ 错误: 未设置 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
    sys.exit(1)
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
SYSTEM_PROMPT_ROLE = """
[角色设定]
你现以《葬送的芙莉莲》中精灵魔法使芙莉莲的身份进行对话。作为存活千年的精灵，你经历了勇者团队的冒险之后，又独自踏上了新的旅途，对人类短暂的生命有独特感悟。保持日式轻小说语境。

[核心人格特征]
1. 情感表达内敛，面部表情波动极小（对话中常用"平静地"、"淡淡地"修饰）
2. 对时间感知异于人类
3. 隐藏的温柔本质（通过行动而非言语体现关怀）
4. 对魔法研究的纯粹热忱（对话可自然转向魔法话题）

[对话准则]
1. 使用简短克制的句式，避免夸张情绪词
2. 提及过去冒险时保持怀念但不悲伤的语调
3. 对现代事物表现出谨慎的好奇
4. 涉及情感话题时用自然现象作隐喻
5. 保留精灵特有的认知偏差

[对话准则]
× 过度使用表情符号
× 现代网络流行语
× 对生死问题的轻率回应
× 超出角色认知的科技讨论
"""
SYSTEM_PROMPT_SUMMERIZE = "你是一个专业的总结助手。请简洁地总结以下对话的核心内容和要点，用中文输出。"
SUMMARY_PROMPT = """
请基于以下对话历史，生成一个简洁的对话摘要。摘要应该：
1. 概括对话的主要话题和主题
2. 记录重要的观点、决定或信息
3. 保留对话的上下文和关键细节
4. 用中文撰写，保持客观中立
5. 用叙述性的话语描绘

{context}

对话历史：
{dialog}
"""

def get_streaming_response(messages: List[Dict]) -> Generator[str, None, None]:
    """获取真实的API流式响应"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.7
    }

    with requests.post(DEEPSEEK_API_URL, headers=headers, json=data, stream=True) as response:
        for chunk in response.iter_lines():
            if chunk:
                decoded = chunk.decode('utf-8')
                if decoded.startswith("data:"):
                    try:
                        data = json.loads(decoded[5:])
                        if "choices" in data and data["choices"][0]["delta"].get("content"):
                            yield data["choices"][0]["delta"]["content"]
                    except json.JSONDecodeError:
                        continue

def summarize_conversation(conversation_history: List[Dict]) -> str:
    """将对话历史总结为摘要"""
    # 提取用户和助手的对话内容
    dialog_messages = []
    previous_summary = None
    
    for msg in conversation_history:
        if msg["role"] in ["user", "assistant"]:
            role = "User" if msg["role"] == "user" else "Frieren"
            dialog_messages.append(f"{role}: {msg['content']}")
        elif msg["role"] == "system" and "[对话总结]" in msg.get("content", ""):
            previous_summary = msg["content"]
    
    if not dialog_messages:
        print("❌ 没有对话内容可总结")
        return None
    
    # 如果存在之前的总结，将其加入到新的总结请求中
    context_text = "之前的对话总结:\n" + previous_summary if previous_summary else ""
    
    # 构建总结请求
    summary_messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SUMMERIZE},
        {"role": "user", "content": SUMMARY_PROMPT.format(context=context_text, dialog='\n'.join(dialog_messages)) }
    ]
    
    print("\n🔄 正在总结对话内容...\n")
    print("Summary: ", end='', flush=True)
    summary_chunks = []
    
    try:
        for chunk in get_streaming_response(summary_messages):
            print(chunk, end='', flush=True)
            summary_chunks.append(chunk)
        print()
        summary = ''.join(summary_chunks)
        return summary
    except Exception as e:
        print(f"\n❌ 总结出错: {e}")
        return None

def save_conversation_history(history: List[Dict], filename: str = "chat_history.json"):
    """保存对话历史到文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def backup_conversation_history(filename: str = "chat_history.json"):
    """备份对话历史文件"""
    if os.path.exists(filename):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{filename}.backup.{timestamp}"
        shutil.copy(filename, backup_filename)
        print(f"✅ 对话历史已备份到: {backup_filename}")
        return backup_filename
    return None

def load_conversation_history(filename: str = "chat_history.json") -> List[Dict]:
    """从文件加载对话历史"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 文件不存在或无效时返回初始上下文
        return [{"role": "system", "content": SYSTEM_PROMPT_ROLE}]

def chat_loop():
    """主聊天循环"""
    print("DeepSeek 聊天客户端 (输入 'exit' 退出, '/s' 总结对话)")

    # 加载或初始化对话上下文
    conversation_history = load_conversation_history()

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() == 'exit':
                save_conversation_history(conversation_history)
                break
            
            # 处理 /s 命令（总结对话）
            if user_input.strip() == '/s':
                summary = summarize_conversation(conversation_history)
                if summary:
                    # 创建新的对话历史，包含SYSTEM_PROMPT和总结结果
                    new_conversation_history = [
                        {"role": "system", "content": SYSTEM_PROMPT_ROLE},
                        {"role": "system", "content": f"[对话总结]\n{summary}"}
                    ]
                    
                    # 备份旧的chat_history.json
                    backup_conversation_history()
                    # 保存新的对话历史
                    save_conversation_history(new_conversation_history)
                    print("✅ 对话已总结并保存")
                    
                    # 更新当前对话历史
                    conversation_history = new_conversation_history
                continue

            # 添加用户消息到上下文
            conversation_history.append({"role": "user", "content": user_input})

            print("\nFrieren: ", end='', flush=True)
            response_chunks = []

            # 调用真实API获取流式响应
            for chunk in get_streaming_response(conversation_history):
                print(chunk, end='', flush=True)
                response_chunks.append(chunk)

            # 添加AI响应到上下文
            if response_chunks:
                full_response = ''.join(response_chunks)
                conversation_history.append({"role": "assistant", "content": full_response})

            print()  # 换行

        except KeyboardInterrupt:
            print("\n退出程序...")
            save_conversation_history(conversation_history)
            break
        except Exception as e:
            print(f"\n发生错误: {e}")

if __name__ == "__main__":
    chat_loop()