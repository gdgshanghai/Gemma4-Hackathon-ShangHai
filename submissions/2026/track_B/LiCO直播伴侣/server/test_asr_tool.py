import os
import wave
import struct
import math
import base64
import httpx
import asyncio

# 1. Generate a dummy 1-second sine wave audio file
def generate_dummy_audio():
    filename = 'dummy.wav'
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        for i in range(16000):
            value = int(10000.0 * math.sin(2.0 * math.pi * 440.0 * i / 16000.0))
            f.writeframes(struct.pack('<h', value))
    return filename

async def main():
    print("Generating dummy audio...")
    audio_file = generate_dummy_audio()
    
    with open(audio_file, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    url = "http://127.0.0.1:6006/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-crazy-thursday-viwo50"
    }
    
    # Simulate client request targeting 31B model with audio
    payload = {
        "model": "gemma4-31b-mm",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "这是一段直播语音，请帮我分析里面说了什么。"
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": f"data:audio/wav;base64,{audio_b64}",
                            "format": "wav"
                        }
                    }
                ]
            }
        ],
        "stream": False
    }
    
    print("Sending request to API...")
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        import json
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
