#!/usr/bin/env python3
"""三项多模态需求端到端验证（调用本地 6006 API）。"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:6006"


def post_json(path: str, body: dict, timeout: int = 600) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def post_multipart(path: str, fields: dict, file_field: str, file_path: Path, timeout: int = 600) -> dict:
    import mimetypes

    boundary = "----gemma4demo"
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        )
    parts.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
            f'filename="{file_path.name}"\r\nContent-Type: {mime}\r\n\r\n'
        ).encode()
    )
    parts.append(file_path.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    payload = b"".join(parts)
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    print("=" * 60)
    print("Gemma4 多模态三项需求验证")
    print("API:", BASE)
    print("=" * 60)

    # 需求1：文字总结
    print("\n[1] 文字 + prompt 总结 (gemma4-31b-mm)")
    r1 = post_json(
        "/api/v1/text/summarize",
        {
            "prompt": "用三条要点中文总结，保留关键信息。",
            "text": (
                "Gemma 4 是 Google 发布的开源多模态模型家族。"
                "31B 密集版支持文本与图像，边缘版 E4B 额外支持原生音频。"
                "当需要最新新闻时，系统应能联网搜索。"
            ),
            "enable_search": False,
        },
    )
    print("  model:", r1.get("model"))
    print("  answer:", (r1.get("answer") or "")[:300])
    print("  used_search:", r1.get("used_search"))

    # 需求3：图像（先生成测试图）
    print("\n[3] 图像识别 + 总结 (gemma4-31b-mm vision)")
    try:
        from PIL import Image, ImageDraw

        img_path = Path("/tmp/gemma_demo.png")
        img = Image.new("RGB", (320, 160), (40, 120, 200))
        d = ImageDraw.Draw(img)
        d.text((20, 60), "Gemma4 多模态测试", fill=(255, 255, 0))
        img.save(img_path)
        r3 = post_multipart(
            "/api/v1/image/analyze",
            {"prompt": "描述图中文字与场景，并一句话总结。", "enable_search": "false"},
            "file",
            img_path,
        )
        print("  model:", r3.get("model"))
        print("  answer:", (r3.get("answer") or "")[:300])
        print("  meta:", r3.get("meta", {}).get("backend"))
    except Exception as e:
        print("  SKIP:", e)

    # 需求2：语音（需真实语音；纯音调会被模型判定为「未提供音频」）
    print("\n[2] 原生语音理解 + 总结 (gemma4-e4b-mm)")
    wav = Path(__file__).resolve().parent / "examples" / "zh_weather_sample.wav"
    if not wav.exists():
        wav = Path("/tmp/gemma_demo_speech.wav")
        if not wav.exists():
            import subprocess

            text = "今天重庆天气晴朗，最高气温三十度。"
            subprocess.run(
                ["espeak-ng", "-v", "zh", "-s", "140", "-w", str(wav), text],
                check=False,
                capture_output=True,
            )
            if not wav.exists():
                wav = Path("/tmp/zh_espeak.wav")
    try:
        r2 = post_multipart(
            "/api/v1/audio/summarize",
            {"prompt": "转写并总结这段音频。", "enable_search": "false"},
            "file",
            wav,
        )
        print("  model:", r2.get("model"))
        print("  answer:", (r2.get("answer") or "")[:300])
        print("  transcript:", (r2.get("transcript") or "")[:120])
    except Exception as e:
        print("  SKIP:", e)

    print("\n全部完成。对外访问: http://<服务器IP>:6006/docs")


if __name__ == "__main__":
    main()
