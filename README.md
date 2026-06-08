# Gemma大赛2026作品提交指南

**Gemma 4 开发者大赛｜2026 - 技术作品提交指南**

欢迎各位极客利用 Google 最新的 **Gemma 4** 模型家族构建改变世界的 AI 应用。为了确保评审团能顺利评估您的作品，请务必遵循以下提交规范。

**1️⃣ 提交核心要求**

本次大赛基于 **Gemma 4**（2B/4B/26B MoE/31B Dense）进行开发，提交内容必须包含：

- **核心代码**：必须包含 Gemma 4 的调用逻辑，重点展示**原生函数调用（Native Function Calling）**、多模态（Multimodal）**处理或**端侧（Edge）部署代码。
    
- **演示视频**：时长严格控制在 **5分钟以内**，需展示核心功能及解决的真实痛点。
    
- **技术报告**：阐述模型选型理由（为何选择 Gemma 4 的特定规格）及架构设计。
    

**2️⃣ 代码提交方式（二选一）**

考虑到部分团队涉及边缘硬件（Edge AI）或隐私数据，我们提供灵活的提交渠道：

**方式 A：官方仓库 Fork & PR（推荐）**

适用于纯软件/Web 应用团队。

1. **Fork 仓库**：访问[https://github.com/gdgshanghai/Gemma4-Hackathon-ShangHai](https://github.com/gdgshanghai/Gemma4-Hackathon-ShangHai)，Fork 至您的账户。
    
2. **目录规范**：请在 /submissions/2026/[赛道字母]/[项目名称]/ 目录下提交。
    
    1. _赛道字母参考：A(Agent), B(Multimodal), C(Edge), D(SocialGood)_
        
3. **提交内容**：包含 README.md（含环境安装步骤）、requirements.txt 及核心源码。
    
4. **PR 合并**：向官方仓库发起 Pull Request，标题格式：[赛道A] 项目名称 - 队伍名。

5. 提交完毕后，**队长**需要在[Gemma 4 开发者大赛-现场赛材料提交](https://hackathon.googdg.cn/onsite-submit)填写现场赛材料表单。
    

**方式 B：私有仓库授权（适合含敏感数据或硬件项目）**

适用于 **赛道 C (Edge AI)** 或涉及隐私数据的项目。

1. 创建私仓：在 GitHub/GitLab/Gitee 创建私有仓库。

2. 添加协作者：
    - 协作账号：[@gdgreview](https://github.com/gdgreview)
    - 权限级别：Read (只读)

3. 提交链接：在赛事报名系统中填写该私有仓库的 Clone 链接。

4. **注意事项**：评审将以截止时间前最后一次 commit 记录为准，截止后任何 commit 将视为无效修改。 

5. 提交完毕后，**队长**需要在[Gemma 4 开发者大赛-现场赛材料提交](https://hackathon.googdg.cn/onsite-submit)填写现场赛材料表单。
    

**3️⃣ 针对性赛道的特殊说明**

根据您选择的赛道，请特别注意以下细节：

|   |   |   |
|---|---|---|
|赛道|关键技术点|提交注意事项|
|**赛道 A: AI Agent**|原生函数调用、多步规划|代码中需清晰展示 Agent 的 **Memory** 和 **Tool Calling** 逻辑，建议提供运行日志截图。|
|**赛道 B: Multimodal**|视觉/音频/文本融合|请在仓库中包含 **Sample Data**（测试素材），以便评审复现多模态效果。|
|**赛道 C: Edge AI**|离线部署、硬件适配|**必须提供硬件演示视频**。若代码涉及底层驱动，请在 README 中详细说明编译环境（如树莓派 OS 版本）。|
|**赛道 D: Social Good**|数据合规、影响力|需在文档中说明 **数据来源的合规性**及 **隐私保护措施**。|

**4️⃣ 评审标准对齐**

为了获得更高的技术分（25%权重），请确保您的提交符合以下标准：

- **架构设计**：代码结构清晰，模块化良好。
    
- **Gemma 4 特性利用**：深度利用了 Gemma 4 的 **原生函数调用** 能力，而非简单的 Prompt 工程。
    
- **文档完善度**：README 需包含一键启动脚本或详细的 Docker 部署指南。
    

**5️⃣ 截止时间与联系方式**

- **最终提交截止**：**2026年6月8日 23:59**
    
- **联系支持**：
    
    - 微信群：GDG Shanghai Gemma 4 交流群 

![扫码入群](https://raw.githubusercontent.com/gdgshanghai/Gemma4-Hackathon-ShangHai/main/assets/qrcode.png)

    
        

最后提醒：请提前准备好开发环境，锁定最强队友，我们在总决赛（Google I/O Connect 中国站）见！
