#!/bin/bash
# Gemma API 流式测试（必须 -N，不要 pipe 到 json.tool）
# 用法: ./scripts/stream_chat.sh
set -e
API="${GEMMA_API:-http://127.0.0.1:6006}"

echo ">>> 流式请求 ${API}/api/v1/text/summarize"
echo ">>> 按 Ctrl+C 中断"
echo ""

curl -N --no-buffer -X POST "${API}/api/v1/text/summarize" \
  -H "Content-Type: application/json" \
  --max-time 600 \
  -d '{
    "prompt": "如果你对这个问题不是很确定，可以使用联网搜索。",
    "text": "张雪峰和巧乐兹的关系是什么？",
    "enable_search": true,
    "include_thinking": true,
    "stream": true
  }' 2>&1 | while IFS= read -r line; do
  case "$line" in
    data:*)
      payload="${line#data: }"
      event=$(echo "$payload" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('event','?'))" 2>/dev/null || echo "?")
      case "$event" in
        status)
          phase=$(echo "$payload" | python3 -c "import sys,json; print(json.load(sys.stdin).get('phase',''))")
          msg=$(echo "$payload" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message',''))")
          echo "[状态/$phase] $msg"
          ;;
        tool_call)
          echo "[工具] $(echo "$payload" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',d.get('tool','')))")"
          ;;
        token)
          text=$(echo "$payload" | python3 -c "import sys,json; print(json.load(sys.stdin).get('text',''), end='')")
          phase=$(echo "$payload" | python3 -c "import sys,json; print(json.load(sys.stdin).get('phase',''))")
          if [ "$phase" = "answer" ]; then
            printf "%s" "$text"
          else
            echo -n "[思考] $text"
          fi
          ;;
        done)
          echo ""
          echo ""
          echo "======== 完成 ========"
          echo "$payload" | python3 -m json.tool 2>/dev/null | head -40
          ;;
        *)
          echo "$line"
          ;;
      esac
      ;;
    *)
      [ -n "$line" ] && echo "$line"
      ;;
  esac
done
