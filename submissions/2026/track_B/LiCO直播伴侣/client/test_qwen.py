# -*- coding: utf-8 -*-
"""
测试 Qwen API 集成
使用前请先在 data/config.ini 中配置 [qwen] 部分
"""
import os
import asyncio
from openai import AsyncOpenAI


async def test_qwen_api():
    """测试 Qwen API 调用"""
    
    # 从环境变量或直接设置 API Key
    api_key = os.getenv("DASHSCOPE_API_KEY", "sk-crazy-thursday-viwo50")
    
    if not api_key:
        print("错误：未设置 DASHSCOPE_API_KEY 环境变量")
        print("请设置环境变量或在 data/config.ini 中配置")
        return
    
    # 创建客户端
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://u1027991-ab00-48a182a5.westb.seetacloud.com:8443/v1",
    )
    
    print("正在调用 Gemma 4 API...")
    
    try:
        # 调用 API
        completion = await client.chat.completions.create(
            model="gemma4-31b-mm",
            messages=[
                {'role': 'user', 'content': '你是谁'}
            ]
        )
        
        # 输出结果
        response = completion.choices[0].message.content
        print(f"\n[Success] API 调用成功！\n")
        print(f"回复：{response}\n")
        
    except Exception as e:
        print(f"\n[Error] API 调用失败：{e}\n")


if __name__ == "__main__":
    asyncio.run(test_qwen_api())

