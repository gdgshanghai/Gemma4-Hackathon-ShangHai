curl -N --no-buffer -X POST "http://127.0.0.1:6006/api/v1/text/summarize" \
  -H "Content-Type: application/json" --max-time 600 \
  -d '{ 
    "prompt": "如果你对这个问题不是很确定，可以使用联网搜索。请按【结论】【依据】【参考链接】格式回答；若证据不足必须说无法确认。", 
    "text": "雪人三项 梗 是什么？", 
    "enable_search": true, 
    "include_thinking": true, 
    "stream": true 
  }'
