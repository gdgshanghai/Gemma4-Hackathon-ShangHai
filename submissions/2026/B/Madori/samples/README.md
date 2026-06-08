# Sample Data — 评审复现素材

赛道 B（Multimodal）测试素材。这些是 Madori 读图分析的输入样例，供评审复现多模态效果。**所有素材均为自制或公开授权数据，来源与许可如下。**

| 文件 | 内容 | 来源 | 许可 |
|---|---|---|---|
| `floorplan.png` | 干净的示例間取り图（卧室/厨房/居間 LDK） | **自制**（由 `floorplan.html` 渲染） | 本项目原创，可自由使用 |
| `floorplan.html` | 上面那张图的 HTML 源 | 自制 | 本项目原创 |
| `madorizu.png` | 标准日本两层住宅間取り图（含 1階/2階） | 维基百科「間取り」条目 `Sample_of_Madorizu.png` | Wikimedia Commons 公开授权 |
| `madorizu_1f.png` | 上图裁出的 **1階**（Madori 主演示用） | 衍生自 `madorizu.png` | 同上 |
| `central_house.png` | 美式中央走廊住宅平面图（Hall/Parlor） | Wikimedia Commons `Central_Passage_House_Floorplan.png` | CC BY-SA 3.0 |
| `hk_greenview.jpg` | 香港綠悠雅苑样板房两房户型图（拍照展板） | Wikimedia Commons `HK CSW Greenview Villa ... floorplan` | CC BY-SA 3.0 |

> 这些样例**刻意覆盖了不同难度**：`floorplan.png`（干净理想图）、`madorizu_1f.png`（标准挂牌图）、`central_house.png`（无尺寸标注）、`hk_greenview.jpg`（拍照畸变 + 密集标注）——用于展示 Madori 在不同图质下的表现与**置信度自动降级**机制。

## 复现（最小步骤）

```bash
# 前置：本机装好 Ollama 并拉取 Gemma 4
ollama serve &
ollama pull gemma4:e4b

# 读一张户型图 → 终端打印五镜头解读 + 生成四视图网页
python pipeline/plan_read.py samples/madorizu_1f.png

# 浏览器打开生成的 web/madori.html，看四个视图（解读/采光/动线/无障碍）
python -m http.server 8000 --directory web   # 访问 http://localhost:8000/madori.html
```

主推演示图：**`madorizu_1f.png`**（标准日本間取り图，Madori 在它上面读得最准）。
