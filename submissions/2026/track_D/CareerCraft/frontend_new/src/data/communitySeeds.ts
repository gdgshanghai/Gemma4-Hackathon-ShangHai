import { EngineerIssue } from '@/types';

export const seededEngineerIssues: EngineerIssue[] = [
  {
    id: 'seed-se-env-path',
    careerId: 'software-engineer',
    authorId: 'seed-student-a',
    authorName: '夜跑同学',
    title: '本地接口正常，提交后鉴权失败，应该先查哪里？',
    content:
      '我在硅屿 API 任务里本地请求是 200，但提交评审后提示鉴权失败。我不确定是环境变量、请求头还是测试用例问题。已经比对过 URL 和请求体，希望了解工程师通常怎样排查这种环境差异。',
    tags: ['接口调试', '环境变量', '测试'],
    status: 'triaged',
    priority: 'high',
    createdAt: '2026-06-05T09:12:00.000Z',
    replies: [
      {
        id: 'seed-reply-se-1',
        issueId: 'seed-se-env-path',
        authorName: '陈工',
        authorRole: '后端工程师',
        content:
          '先完整记录本地与评审环境的 URL、headers、body、状态码和错误体。鉴权问题优先检查 token 来源、过期时间、请求头格式以及环境变量名称是否一致。',
        createdAt: '2026-06-05T09:40:00.000Z',
        helpfulCount: 8,
      },
      {
        id: 'seed-reply-se-2',
        issueId: 'seed-se-env-path',
        authorName: '许砚',
        authorRole: '硅屿工程导师',
        content:
          '把复现步骤和验证命令写进提交说明。这样评审者才能判断你是否定位到了根因，也能让这次排查变成作品集里的工程证据。',
        createdAt: '2026-06-05T10:06:00.000Z',
        helpfulCount: 6,
      },
      {
        id: 'seed-reply-se-3',
        issueId: 'seed-se-env-path',
        authorName: '阿杰',
        authorRole: '社区同学',
        content:
          '之前遇到过类似问题，最后发现是 .env 文件里的变量名写错了一个字母。建议直接打印 process.env 看看实际注入的值。',
        createdAt: '2026-06-05T11:30:00.000Z',
        helpfulCount: 4,
      },
    ],
  },
  {
    id: 'seed-se-test-coverage',
    careerId: 'software-engineer',
    authorId: 'seed-student-e',
    authorName: '代码旅人',
    title: '单元测试覆盖率达标了，但感觉测试没抓到真正的边界情况',
    content:
      '我写的单元测试覆盖率达到了 85%，但遇到真实场景还是会出问题。比如日期处理在月末、空数组输入、异常状态码这些情况。想请教如何设计更有价值的测试用例？',
    tags: ['单元测试', '测试用例', '边界情况'],
    status: 'open',
    priority: 'normal',
    createdAt: '2026-06-05T14:30:00.000Z',
    replies: [
      {
        id: 'seed-reply-se-test-1',
        issueId: 'seed-se-test-coverage',
        authorName: '张测试',
        authorRole: 'QA 工程师',
        content:
          '覆盖率只是底线指标。建议按等价类划分来设计用例：正常路径、边界值（最大/最小/空/超长）、异常输入（null/undefined/类型错误）、特殊场景（节假日/时区切换）。',
        createdAt: '2026-06-05T15:05:00.000Z',
        helpfulCount: 12,
      },
      {
        id: 'seed-reply-se-test-2',
        issueId: 'seed-se-test-coverage',
        authorName: '李架构',
        authorRole: '技术负责人',
        content:
          '可以试试属性测试（Property-based Testing），让测试框架自动生成各种边界值组合。另外，把线上真实报错转化为回归测试用例，能有效提升测试的实际价值。',
        createdAt: '2026-06-05T16:20:00.000Z',
        helpfulCount: 8,
      },
      {
        id: 'seed-reply-se-test-3',
        issueId: 'seed-se-test-coverage',
        authorName: '测试达人',
        authorRole: '社区同学',
        content:
          '分享一个实用技巧：使用边界值分析表格，列出每个输入参数的最小值、略高于最小值、正常值、略低于最大值、最大值。然后用因果图法分析多个条件组合的情况。特别是日期处理，一定要测试月末、年末、闰日这些特殊情况。',
        createdAt: '2026-06-05T17:15:00.000Z',
        helpfulCount: 6,
      },
    ],
  },
  {
    id: 'seed-se-debug-log',
    careerId: 'software-engineer',
    authorId: 'seed-student-f',
    authorName: '深夜 Bug 猎人',
    title: '生产环境日志太多，怎样快速定位问题？',
    content:
      '线上出问题时，面对海量日志不知道从哪里下手。试过 grep 但效率很低，想请教有经验的工程师是怎么快速找到问题根因的？',
    tags: ['日志排查', '调试技巧', '生产环境'],
    status: 'solved',
    priority: 'normal',
    createdAt: '2026-06-04T10:15:00.000Z',
    replies: [
      {
        id: 'seed-reply-se-debug-1',
        issueId: 'seed-se-debug-log',
        authorName: '运维老周',
        authorRole: 'DevOps 工程师',
        content:
          '三步法：1）先通过错误级别过滤（ERROR/WARN）缩小范围；2）按时间戳定位问题发生窗口；3）用请求 ID 串联整个调用链路。推荐学习结构化日志和 APM 工具。',
        createdAt: '2026-06-04T10:45:00.000Z',
        helpfulCount: 15,
      },
      {
        id: 'seed-reply-se-debug-2',
        issueId: 'seed-se-debug-log',
        authorName: '程序媛小美',
        authorRole: '全栈工程师',
        content:
          '记住几个常用命令组合：grep ERROR | head -20 看最新错误；grep "requestId" | jq . 按请求追踪；tail -f 实时监控。另外，给关键业务流程加专门的日志标签很重要。',
        createdAt: '2026-06-04T11:30:00.000Z',
        helpfulCount: 9,
      },
      {
        id: 'seed-reply-se-debug-3',
        issueId: 'seed-se-debug-log',
        authorName: '资深运维',
        authorRole: '社区同学',
        content:
          '推荐几个工具：ELK Stack做日志检索，Jaeger做分布式追踪，Prometheus+Grafana做监控告警。关键是要建立日志规范，确保每个请求都有唯一的traceId，方便追踪。另外，设置合理的日志级别，生产环境别打太多DEBUG日志。',
        createdAt: '2026-06-04T12:00:00.000Z',
        helpfulCount: 11,
      },
    ],
  },
  {
    id: 'seed-da-metric',
    careerId: 'data-analyst',
    authorId: 'seed-student-b',
    authorName: '橙子同学',
    title: '活跃度下降分析里，新用户和老用户应该怎样分层？',
    content:
      '我能画出 DAU 下降趋势，但不知道问题来自新用户减少，还是老用户留不住。想请教适合新手、又能在报告里讲清楚的分层口径。',
    tags: ['指标口径', '分层分析', 'DAU'],
    status: 'open',
    priority: 'normal',
    createdAt: '2026-06-04T14:18:00.000Z',
    replies: [
      {
        id: 'seed-reply-da-1',
        issueId: 'seed-da-metric',
        authorName: '林澈',
        authorRole: '数据分析 Lead',
        content:
          '可以先按注册天数拆成 0-7 天新用户、8-30 天成长用户、30 天以上老用户。分别看访问人数、访问频次和关键互动行为，就能判断下降主要发生在哪一层。',
        createdAt: '2026-06-04T14:42:00.000Z',
        helpfulCount: 11,
      },
      {
        id: 'seed-reply-da-2',
        issueId: 'seed-da-metric',
        authorName: '数据小达人',
        authorRole: '社区同学',
        content:
          '补充一下，还要看留存曲线！如果新用户次日留存跌了，可能是注册流程有问题；如果老用户7日留存跌了，可能是核心功能体验变差了。',
        createdAt: '2026-06-04T15:20:00.000Z',
        helpfulCount: 6,
      },
      {
        id: 'seed-reply-da-3',
        issueId: 'seed-da-metric',
        authorName: '增长分析师',
        authorRole: '社区同学',
        content:
          '再补充一个维度：按用户价值分层。比如按过去30天的消费金额或互动深度分成高、中、低价值用户。有时候问题可能只出现在某个价值层，比如高价值用户流失了但低价值用户还在增长。这样分析更有针对性。',
        createdAt: '2026-06-04T16:00:00.000Z',
        helpfulCount: 8,
      },
    ],
  },
  {
    id: 'seed-da-sql-optimize',
    careerId: 'data-analyst',
    authorId: 'seed-student-g',
    authorName: 'SQL 学习者',
    title: '复杂 SQL 查询跑了半小时还没出结果，怎么优化？',
    content:
      '写了一个多表关联加窗口函数的查询，数据量大概 500 万行，跑了半小时还没完成。EXPLAIN 看不太懂，有没有新手能掌握的优化技巧？',
    tags: ['SQL', '查询优化', '性能'],
    status: 'triaged',
    priority: 'high',
    createdAt: '2026-06-04T09:00:00.000Z',
    replies: [
      {
        id: 'seed-reply-da-sql-1',
        issueId: 'seed-da-sql-optimize',
        authorName: '数仓老王',
        authorRole: '数据仓库工程师',
        content:
          '先查执行计划看全表扫描的部分，优先加索引（特别是 JOIN 字段和 WHERE 条件）。窗口函数可以考虑先聚合再开窗，避免在大表上直接计算。另外，试试 LIMIT 100 看是否逻辑正确，再去掉 LIMIT 跑全量。',
        createdAt: '2026-06-04T09:35:00.000Z',
        helpfulCount: 14,
      },
      {
        id: 'seed-reply-da-sql-2',
        issueId: 'seed-da-sql-optimize',
        authorName: 'BI 分析师',
        authorRole: '商业分析师',
        content:
          '如果数据量太大，可以考虑用临时表分步计算，或者用物化视图。另外，把查询拆分成几个小步骤，每步检查结果是否符合预期，也更容易定位慢的部分。',
        createdAt: '2026-06-04T10:15:00.000Z',
        helpfulCount: 7,
      },
      {
        id: 'seed-reply-da-sql-3',
        issueId: 'seed-da-sql-optimize',
        authorName: 'SQL 高手',
        authorRole: '社区同学',
        content:
          '分享几个实用技巧：1）避免 SELECT *，只选需要的字段；2）WHERE 条件里别用函数（比如 DATE(create_time) = "2024-01-01" 会导致索引失效）；3）注意 JOIN 顺序，小表在前大表在后；4）GROUP BY 和 ORDER BY 的字段尽量有索引。EXPLAIN 重点看 type 列，ALL 就是全表扫描，ref/range 比较好。',
        createdAt: '2026-06-04T11:00:00.000Z',
        helpfulCount: 12,
      },
    ],
  },
  {
    id: 'seed-da-report',
    careerId: 'data-analyst',
    authorId: 'seed-student-h',
    authorName: '报表新手',
    title: '怎样写一份让业务同事看得懂的数据报告？',
    content:
      '每次写报告都被说太技术化，业务同事看不懂。想请教报告的结构应该怎么安排，用什么样的语言风格比较合适？',
    tags: ['报告表达', '数据可视化', '沟通'],
    status: 'solved',
    priority: 'normal',
    createdAt: '2026-06-03T11:25:00.000Z',
    replies: [
      {
        id: 'seed-reply-da-report-1',
        issueId: 'seed-da-report',
        authorName: '产品数据专家',
        authorRole: '数据产品经理',
        content:
          '报告结构建议：1）结论先行（一句话说清楚发现）；2）背景说明（为什么要分析）；3）数据说明（指标口径）；4）分析过程（用图表而不是文字）；5）行动建议（具体做什么）。语言要像聊天一样，避免专业术语堆砌。',
        createdAt: '2026-06-03T12:00:00.000Z',
        helpfulCount: 18,
      },
      {
        id: 'seed-reply-da-report-2',
        issueId: 'seed-da-report',
        authorName: '运营同学',
        authorRole: '社区同学',
        content:
          '加个例子！比如不说"DAU 环比下降 15%"，而是说"这周每天来的用户比上周少了 15%，大概少了 200 人左右"。数字要结合业务场景解读，不然就是干巴巴的数字。',
        createdAt: '2026-06-03T13:30:00.000Z',
        helpfulCount: 12,
      },
    ],
  },
  {
    id: 'seed-pm-scope',
    careerId: 'product-designer',
    authorId: 'seed-student-c',
    authorName: '小满',
    title: '需求太大时，怎样切出一个真正能交付的产品练习？',
    content:
      '我想做学习社区改版，但越写越大，帖子流、私信、积分都想放进去。最后不知道第一版应该交什么，也不知道怎样证明它有效。',
    tags: ['需求拆解', 'MVP', '优先级'],
    status: 'solved',
    priority: 'normal',
    createdAt: '2026-06-03T16:25:00.000Z',
    replies: [
      {
        id: 'seed-reply-pm-1',
        issueId: 'seed-pm-scope',
        authorName: '叶舟',
        authorRole: '产品设计导师',
        content:
          '只保留一个核心用户目标，例如"新同学能在 10 分钟内找到可跟做的练习帖"。第一版围绕发现、筛选、收藏三个动作交付，不要同时做社交和积分。',
        createdAt: '2026-06-03T16:58:00.000Z',
        helpfulCount: 9,
      },
      {
        id: 'seed-reply-pm-2',
        issueId: 'seed-pm-scope',
        authorName: '产品老兵',
        authorRole: '资深产品经理',
        content:
          '用"用户故事地图"来梳理：先写用户的核心旅程，再把功能贴到旅程上，按优先级排序。记住，MVP 不是最小功能集，而是最小可验证的假设集。',
        createdAt: '2026-06-03T17:30:00.000Z',
        helpfulCount: 6,
      },
      {
        id: 'seed-reply-pm-3',
        issueId: 'seed-pm-scope',
        authorName: '敏捷教练',
        authorRole: '社区同学',
        content:
          '推荐用 MoSCoW 方法排优先级：Must have（必须有）、Should have（应该有）、Could have（可以有）、Won\'t have（这次不做）。第一版只做 Must have，把 Should have 放到下一个迭代。另外，每个功能都要问："如果没有这个功能，用户还能用核心功能吗？"',
        createdAt: '2026-06-03T18:15:00.000Z',
        helpfulCount: 7,
      },
    ],
  },
  {
    id: 'seed-pm-user-research',
    careerId: 'product-designer',
    authorId: 'seed-student-i',
    authorName: '用户研究员',
    title: '用户访谈总是问不到真实需求，怎么办？',
    content:
      '我做用户访谈时，用户都说"挺好的"、"没什么意见"，问不出真正的痛点。有没有实用的提问技巧？',
    tags: ['用户研究', '访谈技巧', '需求挖掘'],
    status: 'open',
    priority: 'normal',
    createdAt: '2026-06-02T14:00:00.000Z',
    replies: [
      {
        id: 'seed-reply-pm-research-1',
        issueId: 'seed-pm-user-research',
        authorName: 'UX 设计师',
        authorRole: '用户体验研究员',
        content:
          '别问抽象问题，要让用户讲故事！比如不说"你觉得这个功能好用吗？"，而是说"上次用这个功能时，遇到了什么让你觉得麻烦的事？"。还要学会追问"然后呢？"、"为什么会这样？"',
        createdAt: '2026-06-02T14:40:00.000Z',
        helpfulCount: 13,
      },
      {
        id: 'seed-reply-pm-research-2',
        issueId: 'seed-pm-user-research',
        authorName: '产品新手',
        authorRole: '社区同学',
        content:
          '可以准备一些场景卡片，让用户排序或者打分。比如给用户看几个不同的界面设计，问他们"如果赶时间你会选哪个？为什么？"，比直接问感受更有用。',
        createdAt: '2026-06-02T15:20:00.000Z',
        helpfulCount: 8,
      },
      {
        id: 'seed-reply-pm-research-3',
        issueId: 'seed-pm-user-research',
        authorName: '用户研究专家',
        authorRole: '社区同学',
        content:
          '分享一个方法：沉默法。当用户说完后，不要马上接话，保持几秒钟沉默。很多时候用户会因为尴尬而继续说，往往能说出更真实的想法。另外，可以让用户"边做边说"（think aloud），观察他们的实际操作比听他们说更重要。',
        createdAt: '2026-06-02T16:00:00.000Z',
        helpfulCount: 10,
      },
    ],
  },
  {
    id: 'seed-pm-prototype',
    careerId: 'product-designer',
    authorId: 'seed-student-j',
    authorName: '原型爱好者',
    title: '高保真原型要不要做交互效果？做到什么程度合适？',
    content:
      '现在做原型纠结要不要加交互动画。不加显得太简陋，加太多又费时间。想知道大家平时做原型时，交互细节做到什么程度？',
    tags: ['原型设计', '交互设计', '工具技巧'],
    status: 'triaged',
    priority: 'normal',
    createdAt: '2026-06-01T10:30:00.000Z',
    replies: [
      {
        id: 'seed-reply-pm-prototype-1',
        issueId: 'seed-pm-prototype',
        authorName: '交互设计师',
        authorRole: '高级 UX 设计师',
        content:
          '核心原则：能验证用户能否完成任务即可。关键流程（比如支付、注册）要做完整交互，次要页面可以简化。动画效果只要示意出过渡方向就行，不用太精细。记住原型是用来沟通的，不是用来交付的。',
        createdAt: '2026-06-01T11:15:00.000Z',
        helpfulCount: 16,
      },
      {
        id: 'seed-reply-pm-prototype-2',
        issueId: 'seed-pm-prototype',
        authorName: '产品经理',
        authorRole: '社区同学',
        content:
          '看使用场景！如果是给开发看，简单的跳转示意就够了；如果是给领导汇报或用户测试，需要做得更完整一些。推荐用组件库快速搭建，既能保持一致性又节省时间。另外，记得标注交互说明（比如"点击后弹出模态框"），比做复杂动画更实用。',
        createdAt: '2026-06-01T12:00:00.000Z',
        helpfulCount: 11,
      },
    ],
  },
  {
    id: 'seed-ai-eval',
    careerId: 'ai-researcher',
    authorId: 'seed-student-d',
    authorName: '北塔实验员',
    title: '提示词改了以后，怎样判断任务生成质量真的提升了？',
    content:
      '两版提示词生成的任务看起来都还可以，但我不知道该用哪些指标比较，也担心只挑了几个成功例子。希望有人帮我设计一套小样本评测方法。',
    tags: ['实验设计', '模型评测', '提示工程'],
    status: 'open',
    priority: 'normal',
    createdAt: '2026-06-02T11:20:00.000Z',
    replies: [
      {
        id: 'seed-reply-ai-1',
        issueId: 'seed-ai-eval',
        authorName: '沈栖',
        authorRole: 'AI 研究塔导师',
        content:
          '先定义可执行性、岗位真实性、难度匹配和交付物清晰度四个维度。固定同一批输入，用盲评比较两版输出，并保留失败样本。',
        createdAt: '2026-06-02T12:05:00.000Z',
        helpfulCount: 7,
      },
      {
        id: 'seed-reply-ai-2',
        issueId: 'seed-ai-eval',
        authorName: 'LLM 实践者',
        authorRole: '社区同学',
        content:
          '建议做 AB 测试！找几个真实用户试用两版生成的任务，记录完成时间、错误率和主观满意度。数据比自己瞎猜靠谱多了。',
        createdAt: '2026-06-02T13:45:00.000Z',
        helpfulCount: 5,
      },
      {
        id: 'seed-reply-ai-3',
        issueId: 'seed-ai-eval',
        authorName: '评测专家',
        authorRole: '社区同学',
        content:
          '推荐使用 BLEU 或 ROUGE 指标来量化输出质量，但这些指标有局限性。最好结合人工评估：找 3-5 个评估者按统一标准打分，计算评分者一致性（Cohen\'s kappa）。另外，可以设置"必须满足的条件"（比如不能有事实错误、必须包含某个关键词），不满足的直接打低分。',
        createdAt: '2026-06-02T14:30:00.000Z',
        helpfulCount: 8,
      },
    ],
  },
  {
    id: 'seed-ai-prompt',
    careerId: 'ai-researcher',
    authorId: 'seed-student-k',
    authorName: '提示词工程师',
    title: '怎样写出稳定输出的提示词？总是有时候好有时候差',
    content:
      '我写的提示词经常不稳定，同样的输入有时候输出很好，有时候就很糟糕。试过加温度参数但效果不明显，有没有系统性的方法？',
    tags: ['提示工程', 'LLM', '稳定性'],
    status: 'solved',
    priority: 'high',
    createdAt: '2026-06-01T15:00:00.000Z',
    replies: [
      {
        id: 'seed-reply-ai-prompt-1',
        issueId: 'seed-ai-prompt',
        authorName: 'NLP 研究员',
        authorRole: 'AI 工程师',
        content:
          '提示词工程的黄金法则：1）明确角色（让模型知道它是谁）；2）清晰的任务描述（输入输出格式都要具体）；3）给出示例（至少 2-3 个）；4）设定约束条件；5）迭代优化。另外，固定模型版本和参数，不同版本的行为差异很大。',
        createdAt: '2026-06-01T15:45:00.000Z',
        helpfulCount: 20,
      },
      {
        id: 'seed-reply-ai-prompt-2',
        issueId: 'seed-ai-prompt',
        authorName: '提示词达人',
        authorRole: '社区同学',
        content:
          '分享一个小技巧：把成功的输出作为示例放进提示词里，形成"few-shot learning"。另外，可以加一句"如果不确定答案，请说不知道"来减少幻觉。',
        createdAt: '2026-06-01T16:30:00.000Z',
        helpfulCount: 11,
      },
      {
        id: 'seed-reply-ai-prompt-3',
        issueId: 'seed-ai-prompt',
        authorName: 'AI 工程师',
        authorRole: '社区同学',
        content:
          '补充几点：1）用结构化输出格式（JSON/XML），让模型输出更可预测；2）设置明确的输出长度限制；3）使用"思考链"（Chain of Thought）提示词，让模型一步步推理；4）定期测试同一个提示词，记录成功率。如果波动太大，可以考虑用多个提示词投票或者微调一个小型模型。',
        createdAt: '2026-06-01T17:15:00.000Z',
        helpfulCount: 14,
      },
    ],
  },
  {
    id: 'seed-ai-data',
    careerId: 'ai-researcher',
    authorId: 'seed-student-l',
    authorName: '数据驱动者',
    title: '训练数据不够时，怎样提升模型效果？',
    content:
      '我想微调一个模型，但标注数据只有几百条，效果很差。有没有不用大量数据也能提升效果的方法？',
    tags: ['数据增强', '小样本学习', '模型微调'],
    status: 'open',
    priority: 'normal',
    createdAt: '2026-05-31T09:30:00.000Z',
    replies: [
      {
        id: 'seed-reply-ai-data-1',
        issueId: 'seed-ai-data',
        authorName: '机器学习工程师',
        authorRole: 'AI 研究员',
        content:
          '试试这些方法：1）数据增强（同义词替换、回译、随机掩码）；2）使用领域相关的预训练模型；3）Prompt tuning 代替全参数微调；4）主动学习（让模型自己挑选需要标注的样本）。小数据场景下，高质量标注比数量更重要。',
        createdAt: '2026-05-31T10:15:00.000Z',
        helpfulCount: 14,
      },
      {
        id: 'seed-reply-ai-data-2',
        issueId: 'seed-ai-data',
        authorName: 'NLP 工程师',
        authorRole: '社区同学',
        content:
          '补充一点：如果是文本分类任务，可以试试对比学习（Contrastive Learning）。用无标签数据学习更好的特征表示，再用少量标注数据做微调。另外，数据清洗比数据数量更重要，先把噪声数据清理干净。',
        createdAt: '2026-05-31T11:30:00.000Z',
        helpfulCount: 9,
      },
    ],
  },
  {
    id: 'seed-se-performance',
    careerId: 'software-engineer',
    authorId: 'seed-student-m',
    authorName: '性能优化者',
    title: '前端页面加载慢，应该从哪里开始优化？',
    content:
      '我的页面加载需要5秒以上，用户体验很差。用Lighthouse检测发现主要是JavaScript执行时间长和首屏渲染慢。想请教前端性能优化的系统方法，以及新手容易踩坑的地方。',
    tags: ['性能优化', '前端优化', 'Lighthouse'],
    status: 'triaged',
    priority: 'high',
    createdAt: '2026-05-30T14:00:00.000Z',
    replies: [
      {
        id: 'seed-reply-se-performance-1',
        issueId: 'seed-se-performance',
        authorName: '前端架构师',
        authorRole: '高级前端工程师',
        content:
          '性能优化建议按这个顺序来：1）先看网络请求（压缩资源、减少请求数、CDN缓存）；2）代码层面（懒加载、代码分割、Tree Shaking）；3）渲染层面（减少重绘重排、使用CSS containment）；4）运行时优化（防抖节流、Web Worker）。新手容易忽视的是：图片没有懒加载、没有设置缓存策略、第三方脚本阻塞主线程。',
        createdAt: '2026-05-30T14:45:00.000Z',
        helpfulCount: 16,
      },
      {
        id: 'seed-reply-se-performance-2',
        issueId: 'seed-se-performance',
        authorName: '性能专家',
        authorRole: '性能工程师',
        content:
          '分享一个实用技巧：用Performance API记录关键路径的时间线，找出真正的瓶颈。另外，注意避免渲染阻塞资源（把CSS放头部、JS放底部或用async/defer），使用关键CSS内联，图片用WebP/AVIF格式并设置正确的宽高比。',
        createdAt: '2026-05-30T15:30:00.000Z',
        helpfulCount: 12,
      },
      {
        id: 'seed-reply-se-performance-3',
        issueId: 'seed-se-performance',
        authorName: '前端新手',
        authorRole: '社区同学',
        content:
          '我之前也遇到类似问题，最后发现是因为引入了太多第三方库，而且没有按需加载。建议先用webpack-bundle-analyzer分析一下打包体积，把大的库换成更小的替代品或者按需引入。',
        createdAt: '2026-05-30T16:20:00.000Z',
        helpfulCount: 7,
      },
    ],
  },
  {
    id: 'seed-da-ab-test',
    careerId: 'data-analyst',
    authorId: 'seed-student-n',
    authorName: '实验分析师',
    title: 'AB测试样本量不够怎么办？如何判断结果是否可信？',
    content:
      '我们做了一个AB测试，但因为用户量太少，p-value总是不显著。业务方催着要结论，我该怎么判断测试结果是否可靠？有没有小样本下的分析方法？',
    tags: ['AB测试', '统计检验', '样本量'],
    status: 'open',
    priority: 'high',
    createdAt: '2026-05-29T10:30:00.000Z',
    replies: [
      {
        id: 'seed-reply-da-ab-1',
        issueId: 'seed-da-ab-test',
        authorName: '数据科学家',
        authorRole: '统计分析师',
        content:
          '小样本下可以考虑：1）延长测试时间积累更多数据；2）使用贝叶斯方法（可以给出概率而不是非黑即白的结论）；3）合并相似指标增加信号强度。另外，检查一下效应量，如果预期的提升很小，本来就需要很大样本量才能检测到。还要注意多重比较问题，别因为看了很多指标就随便挑显著的。',
        createdAt: '2026-05-29T11:15:00.000Z',
        helpfulCount: 18,
      },
      {
        id: 'seed-reply-da-ab-2',
        issueId: 'seed-da-ab-test',
        authorName: '增长分析师',
        authorRole: '社区同学',
        content:
          '分享一个经验：如果样本量不够但又必须给结论，可以采用"置信区间+业务判断"的方式。比如"新版本转化率比旧版本高2-5%，置信区间是[-1%, 8%]"，然后和业务方讨论这个范围是否值得发布。另外，可以看看用户分群的结果是否一致，增加结论的可信度。',
        createdAt: '2026-05-29T12:00:00.000Z',
        helpfulCount: 11,
      },
    ],
  },
  {
    id: 'seed-pm-kpi',
    careerId: 'product-designer',
    authorId: 'seed-student-o',
    authorName: 'KPI 思考者',
    title: '产品KPI怎么定才能既合理又能驱动团队？',
    content:
      '我们团队在定KPI时总是争论不休，业务想要增长，技术想要稳定性，运营想要活跃度。怎样才能找到大家都认可的KPI，并且真的能驱动团队前进？',
    tags: ['KPI', '目标管理', '团队协作'],
    status: 'solved',
    priority: 'normal',
    createdAt: '2026-05-28T15:00:00.000Z',
    replies: [
      {
        id: 'seed-reply-pm-kpi-1',
        issueId: 'seed-pm-kpi',
        authorName: '产品总监',
        authorRole: '资深产品经理',
        content:
          '推荐使用OKR框架：先定一个北极星指标（比如DAU、GMV、留存率），然后围绕它设定可衡量的关键结果。关键是要让KPI和用户价值挂钩，而不是单纯追求数字。另外，要区分"领先指标"和"滞后指标"，比如激活率是领先指标，留存是滞后指标。还要注意KPI不要太多，3-5个就够了，太多会分散注意力。',
        createdAt: '2026-05-28T15:45:00.000Z',
        helpfulCount: 22,
      },
      {
        id: 'seed-reply-pm-kpi-2',
        issueId: 'seed-pm-kpi',
        authorName: '敏捷教练',
        authorRole: '社区同学',
        content:
          '补充一点：KPI要可执行。比如不说"提升用户体验"，而是说"将页面加载时间从3秒优化到1.5秒"。还要考虑团队的实际能力，定一个跳一跳能够得着的目标。另外，定期回顾和调整KPI也很重要，市场变化很快，不能一成不变。',
        createdAt: '2026-05-28T16:30:00.000Z',
        helpfulCount: 14,
      },
    ],
  },
  {
    id: 'seed-se-security',
    careerId: 'software-engineer',
    authorId: 'seed-student-p',
    authorName: '安全小白',
    title: '前端开发需要注意哪些安全问题？',
    content:
      '作为前端开发者，我知道XSS和CSRF，但不知道具体怎么防范。还有哪些常见的安全漏洞需要注意？有没有实用的防护清单？',
    tags: ['安全', 'XSS', 'CSRF', '前端安全'],
    status: 'solved',
    priority: 'normal',
    createdAt: '2026-05-27T09:30:00.000Z',
    replies: [
      {
        id: 'seed-reply-se-security-1',
        issueId: 'seed-se-security',
        authorName: '安全工程师',
        authorRole: '信息安全专家',
        content:
          '前端安全防护清单：1）XSS防护（使用textContent而不是innerHTML，对用户输入进行转义，使用CSP）；2）CSRF防护（使用token验证，验证referer）；3）点击劫持（使用X-Frame-Options）；4）敏感数据保护（不要在前端存储密码，使用HTTPS）；5）依赖安全（定期更新依赖，使用npm audit）；6）输入验证（前端后端双重验证）。建议用OWASP Top 10作为学习清单。',
        createdAt: '2026-05-27T10:15:00.000Z',
        helpfulCount: 25,
      },
      {
        id: 'seed-reply-se-security-2',
        issueId: 'seed-se-security',
        authorName: '全栈开发者',
        authorRole: '社区同学',
        content:
          '分享一个实际经验：之前遇到过一个XSS攻击，是因为用了dangerouslySetInnerHTML。后来改成用React的安全渲染方式就好了。另外，记得设置HttpOnly和Secure属性的cookie，防止cookie被窃取。还有，不要相信任何用户输入，永远要做验证和转义。',
        createdAt: '2026-05-27T11:00:00.000Z',
        helpfulCount: 16,
      },
    ],
  },
  {
    id: 'seed-da-data-quality',
    careerId: 'data-analyst',
    authorId: 'seed-student-q',
    authorName: '数据质量守护者',
    title: '数据质量问题怎么发现和监控？',
    content:
      '我经常遇到数据不准的情况，比如统计出来的DAU和后端日志对不上。有没有系统的方法来发现和监控数据质量问题？',
    tags: ['数据质量', '数据监控', '数据治理'],
    status: 'triaged',
    priority: 'normal',
    createdAt: '2026-05-26T14:00:00.000Z',
    replies: [
      {
        id: 'seed-reply-da-quality-1',
        issueId: 'seed-da-data-quality',
        authorName: '数据治理专家',
        authorRole: '数据架构师',
        content:
          '数据质量监控可以从几个维度入手：1）完整性（是否有缺失值）；2）准确性（是否符合业务规则）；3）一致性（多源数据是否一致）；4）时效性（数据是否及时更新）；5）唯一性（是否有重复数据）。建议建立数据质量仪表盘，设置告警规则，定期做数据稽核。另外，在ETL流程中加入数据校验环节，问题早发现早处理。',
        createdAt: '2026-05-26T14:45:00.000Z',
        helpfulCount: 19,
      },
      {
        id: 'seed-reply-da-quality-2',
        issueId: 'seed-da-data-quality',
        authorName: 'ETL工程师',
        authorRole: '社区同学',
        content:
          '实用技巧：写一些简单的校验SQL，比如检查DAU是否在合理范围、增长率是否异常、不同表之间的数据是否能对上。可以用Airflow或类似工具定时运行这些校验，失败时发送告警。另外，数据字典和元数据管理也很重要，让大家都明白每个字段的含义和业务规则。',
        createdAt: '2026-05-26T15:30:00.000Z',
        helpfulCount: 13,
      },
    ],
  },
];
