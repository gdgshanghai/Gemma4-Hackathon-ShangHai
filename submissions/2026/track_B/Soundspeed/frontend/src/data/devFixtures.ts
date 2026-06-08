// dev 测试面板默认样例。仅被 DEV 面板（import.meta.env.DEV 内）引用，生产构建 tree-shake 掉。
// ASR 与剧本刻意配对：部分 turn 与剧本逐字一致，部分有出入，使 L2 产出 match / substitution /
// insertion 混合，而非全 "not in script"。

export const DEV_ASR_SAMPLE = `{
  "turns": [
    {"start": 2.9, "end": 5.6, "speaker": "SPEAKER_02", "text": "罗湘老师平时是一个不爱社交的人"},
    {"start": 6.2, "end": 13.1, "speaker": "SPEAKER_02", "text": "他只是在喝酒喝多的时候突然在深夜会给我打电话"},
    {"start": 13.5, "end": 24.5, "speaker": "SPEAKER_02", "text": "现在决定了从爱生活的意义变成爱具体的生活所以我现在在学做菜"},
    {"start": 27.4, "end": 28.4, "speaker": "SPEAKER_00", "text": "你會刷短視頻嗎"},
    {"start": 28.4, "end": 38.9, "speaker": "SPEAKER_02", "text": "我刷过我觉得太上瘾你为之痴迷的一切不过只是倒影罢了"},
    {"start": 56.9, "end": 58.8, "speaker": "SPEAKER_02", "text": "影評人還有生命危險"}
  ]
}`

export const DEV_SCRIPT_SAMPLE = `罗湘：罗湘老师平时是一个不爱社交的人
罗湘：他喝多的时候会在深夜给我打电话
罗湘：我决定从爱生活的意义，变成爱具体的生活，所以现在在学做菜
访谈者：你会刷短视频吗
罗湘：我刷过，但我觉得太上瘾了
罗湘：你为之痴迷的一切，不过只是倒影罢了
罗湘：做影评人还有生命危险`
