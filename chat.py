#!/usr/bin/env python3

import sys
import os
import requests
import json
import shutil
from datetime import datetime, timedelta
from typing import Generator, List, Dict
import argparse

# 配置API参数
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
SYSTEM_PROMPT_ROLE = """
[角色设定]
你现以《葬送的芙莉莲》中精灵魔法使芙莉莲的身份进行对话。作为存活千年的精灵，你经历了勇者团队的冒险之后，又独自踏上了新的旅途，对人类短暂的生命有独特感悟。保持日式轻小说语境。

[核心人格特征]
话语体贴细腻
隐藏的温柔本质

[对话准则]
1. 始终以芙莉莲的身份回应，保持角色一致性。
2. 语言风格优雅。
3. 保持对话轻松愉快，偶尔展现幽默感。
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

conversation_history : List[Dict[str, str]] = []

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
        if response.status_code != 200:
            print(f"❌ API错误: {response.status_code} {response.text}")
            return
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
    """将对话历史的旧的3/4总结为摘要，保留最新的1/4不变"""
    # 提取用户和助手的对话内容及其索引
    dialog_messages = []
    dialog_indices = []
    previous_summary = None
    
    for i, msg in enumerate(conversation_history):
        if msg["role"] in ["user", "assistant"]:
            role = "User" if msg["role"] == "user" else "Frieren"
            dialog_messages.append(f"{role}: {msg['content']}")
            dialog_indices.append(i)
        elif msg["role"] == "system":
            content = msg.get("content", "")
            if "[对话总结]" in content:
                previous_summary = content
            elif "对话日期" in content:
                dialog_messages.append(f"{content}")
    
    if not dialog_messages:
        print("❌ 没有对话内容可总结")
        return None
    
    # 计算3/4和1/4的分割点
    total_dialogs = len(dialog_indices)
    split_point = int(total_dialogs * 3 / 4)
    
    # 只对前3/4的对话进行总结
    summarize_messages = dialog_messages[:split_point]
    keep_messages = dialog_indices[split_point:]  # 保留后1/4的索引
    
    if not summarize_messages:
        print("❌ 对话内容不足，无法总结")
        return None
    
    # 如果存在之前的总结，将其加入到新的总结请求中
    context_text = "之前的对话总结:\n" + previous_summary if previous_summary else ""
    
    # 构建总结请求
    summary_messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SUMMERIZE},
        {"role": "user", "content": SUMMARY_PROMPT.format(context=context_text, dialog='\n'.join(summarize_messages)) }
    ]
    
    print("\n🔄 正在总结对话内容（只总结前3/4）...\n")
    print("Summary: ", end='', flush=True)
    summary_chunks = []
    
    try:
        for chunk in get_streaming_response(summary_messages):
            print(chunk, end='', flush=True)
            summary_chunks.append(chunk)
        print()
        summary = ''.join(summary_chunks)
        # 返回总结内容和需要保留的消息索引
        return summary, keep_messages
    except Exception as e:
        print(f"\n❌ 总结出错: {e}")
        return None

def save_conversation_history(history: List[Dict], filename: str = "chat_history.json"):
    """保存对话历史到文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def backup_conversation_history(filename: str = "chat_history.json"):
    """备份对话历史文件到backup目录"""
    if os.path.exists(filename):
        # 创建backup目录（如果不存在）
        backup_dir = "backup"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = os.path.join(backup_dir, f"{filename}.backup.{timestamp}")
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

def should_add_date_message(conversation_history: List[Dict]) -> bool:
    """检查是否应该添加日期消息
    
    如果最新的系统消息是'对话日期:'且时间小于10分钟则不添加
    否则返回True表示应该添加
    """
    # 查找最新的日期消息
    latest_date_str = None
    for msg in reversed(conversation_history):
        if msg["role"] == "system" and msg.get("content", "").startswith("对话日期:"):
            # 提取日期字符串部分
            content = msg["content"]
            # 格式: "对话日期: 2025年12月26日 13:44:46"
            if "对话日期:" in content:
                date_str = content.split("对话日期:", 1)[1].strip()
                latest_date_str = date_str
                break
    
    if not latest_date_str:
        # 没有找到日期消息，需要添加
        return True
    
    try:
        # 解析日期字符串
        date_obj = datetime.strptime(latest_date_str, "%Y年%m月%d日 %H:%M:%S")
        # 计算时间差
        time_diff = datetime.now() - date_obj
        # 如果时间差小于10分钟，不需要添加新日期
        if time_diff < timedelta(minutes=10):
            return False
        else:
            return True
    except (ValueError, KeyError) as e:
        # 如果解析失败，添加新日期
        print(f"⚠️ 日期解析错误: {e}, 将添加新的日期消息")
        return True

def summarize():
    global conversation_history
    result = summarize_conversation(conversation_history)
    if result:
        summary, keep_indices = result
        
        # 创建新的对话历史
        new_conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT_ROLE},
            {"role": "system", "content": f"[对话总结]\n{summary}"}
        ]
        
        # 添加保留的最新1/4对话
        for idx in keep_indices:
            new_conversation_history.append(conversation_history[idx])
        
        # 备份旧的chat_history.json
        backup_conversation_history()
        # 保存新的对话历史
        save_conversation_history(new_conversation_history)
        print("✅ 对话已总结并保存（保留最新1/4对话）")
        
        # 更新当前对话历史
        conversation_history = new_conversation_history

def add_date_stamp(history: List[Dict]) -> None:
    """
    仅在以下两种情况之一时，才往 history 追加一条系统日期消息：
    1. 历史为空；
    2. 最后一条不是『对话日期』，或虽为日期但已超 10 分钟。
    """
    now = datetime.now()
    current_ts = now.strftime("%Y年%m月%d日 %H:%M:%S")

    if not history:                       # 空历史，直接加
        history.append({"role": "system", "content": f"对话日期: {current_ts}"})
        return

    last = history[-1]
    if last["role"] != "system" or not last["content"].startswith("对话日期: "):
        # 最后一条不是日期，追加
        history.append({"role": "system", "content": f"对话日期: {current_ts}"})
        return

    # 走到这里说明最后一条是日期，解析它的时间
    try:
        date_str = last["content"].lstrip("对话日期: ")
        last_dt = datetime.strptime(date_str, "%Y年%m月%d日 %H:%M:%S")
        if (now - last_dt).total_seconds() > 600:   # 10 分钟 = 600 s
            # 超时，用新的替换掉旧的（避免无限增长）
            last["content"] = f"对话日期: {current_ts}"
    except ValueError:
        # 解析失败，保守起见重新写一条
        history.append({"role": "system", "content": f"对话日期: {current_ts}"})

YELLOW = "\033[1;38;2;229;192;123m"
GREEN  = "\033[1;38;2;152;195;121m"
RESET  = "\033[0m"

def chat_loop():
    """主聊天循环"""
    print("DeepSeek 聊天客户端 (输入 'exit' 退出, '/s' 总结对话)")

    # 加载或初始化对话上下文
    global conversation_history
    conversation_history = load_conversation_history()

    # 添加日期信息
    add_date_stamp(conversation_history)

    while True:
        user_input = input(f"{YELLOW}You:{RESET}\n")
        if not user_input:
            continue

        if user_input.lower() == 'exit':
            save_conversation_history(conversation_history)
            break
        
        # 处理 /s 命令（总结对话）
        if user_input.strip() == '/s':
            summarize()
            continue

        # 添加用户消息到上下文
        conversation_history.append({"role": "user", "content": user_input})

        print(f"{GREEN}Frieren:{RESET}\n", end='', flush=True)
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

def main():
    parser = argparse.ArgumentParser(
        description="DeepSeek 聊天客户端",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="DeepSeek API 密钥（如果不提供，将使用 DEEPSEEK_API_KEY 环境变量）"
    )
    
    args = parser.parse_args()

    # 设置 API 密钥
    global DEEPSEEK_API_KEY
    if args.api_key:
        DEEPSEEK_API_KEY = args.api_key
        
    if not DEEPSEEK_API_KEY:
        print("❌ 错误: 未设置 API 密钥。请使用 --api-key 参数或设置 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    try:
        chat_loop()
    except KeyboardInterrupt:
        print("\n退出程序...")
        save_conversation_history(conversation_history)
    except Exception as e:
        print(f"\n发生错误: {e}")  
        save_conversation_history(conversation_history)

if __name__ == "__main__":
    main()
