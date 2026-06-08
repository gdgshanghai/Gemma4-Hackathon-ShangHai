import type { KnowledgeArticle, NewsItem } from '../types'

export const KNOWLEDGE: KnowledgeArticle[] = [
  { id: 'u-equals-u', title: 'U=U：检测不到，就是不传播', category: 'U=U', summary: '规范治疗并持续保持病毒载量检测不到时，不会通过性行为传播 HIV。', content: 'U=U 指 Undetectable = Untransmittable。感染者坚持规范抗病毒治疗，并经检测持续保持病毒载量低于检测下限时，不会通过性行为把 HIV 传播给性伴侣。U=U 不等于治愈，也不替代规律服药和复查。', source: '中国疾病预防控制中心艾防中心', sourceUrl: 'https://ncaids.chinacdc.cn/', updatedAt: '2026-05-20', keywords: ['U=U', '不传播', '病毒载量', '检测不到', '性传播'] },
  { id: 'pep', title: '暴露后阻断 PEP：越早越好', category: '检测与就医', summary: '可能发生 HIV 暴露后，应尽快到医疗机构评估，通常强调 72 小时内启动。', content: 'PEP 是暴露后预防。是否需要使用要由专业人员结合暴露方式、时间和来源情况评估。不要等待症状，也不要自行购买或搭配药物。若仍在 72 小时内，优先联系感染科、急诊或当地疾控获得评估。', source: '中国疾病预防控制中心', sourceUrl: 'https://www.chinacdc.cn/', updatedAt: '2026-05-20', keywords: ['PEP', '阻断', '72小时', '暴露', '高危'] },
  { id: 'testing-window', title: 'HIV 检测与窗口期', category: '检测与就医', summary: '检测时间与所用试剂有关，单凭身体感觉不能判断是否感染。', content: 'HIV 是否感染需要规范检测确认。不同检测方法的窗口期不同，暴露后过早检测可能需要按专业建议复检。自测试剂阳性是筛查结果，应尽快到医疗机构或疾控机构确认；阴性结果也要结合暴露时间和试剂类型理解。', source: '中国疾病预防控制中心', sourceUrl: 'https://www.chinacdc.cn/', updatedAt: '2026-05-20', keywords: ['检测', '窗口期', '自测', '阳性', '阴性'] },
  { id: 'viral-load-cd4', title: '看懂病毒载量与 CD4', category: '治疗管理', summary: '病毒载量反映病毒复制水平，CD4 是免疫状态的重要指标。', content: '病毒载量和 CD4 应结合用药、既往趋势、感染或疫苗接种等情况，由医生综合判断。单次波动不一定意味着治疗失败。不要依据 App 解读自行停药、换药或调整剂量，可以把趋势和问题带到复诊。', source: '中国疾病预防控制中心艾防中心', sourceUrl: 'https://ncaids.chinacdc.cn/', updatedAt: '2026-05-20', keywords: ['CD4', '病毒载量', '病载', '复查', '治疗'] },
  { id: 'mental-support', title: '恐艾与确诊后的心理支持', category: '心理支持', summary: '反复检查身体和搜索风险可能放大焦虑，寻求支持不是软弱。', content: '当担忧影响睡眠、工作或关系时，可以先减少重复搜索，记录触发点，进行短时呼吸练习，并向心理咨询师或感染科医护表达心理压力。出现自伤、自杀或无法保证自身安全的想法时，立即联系 12356、110 或 120。', source: '国家卫生健康委', sourceUrl: 'https://www.nhc.gov.cn/', updatedAt: '2026-05-20', keywords: ['恐艾', '焦虑', '心理', '睡眠', '求助'] },
]

export const LOCAL_NEWS: NewsItem[] = [
  { id: 'local-news-1', title: '本地缓存：规范治疗与 U=U 共识', summary: '持续规范治疗、规律监测，是实现并维持病毒抑制的核心。', topic: 'treatment', source: 'U2 本地知识库', url: 'https://ncaids.chinacdc.cn/', publishedAt: '2026-05-20', fetchedAt: '2026-05-20' },
]

export function retrieveKnowledge(query: string, limit = 3) {
  const terms = query.toLowerCase().split(/[\s，。！？、]+/).filter(Boolean)
  return KNOWLEDGE.map((article) => ({
    article,
    score: article.keywords.reduce((score, keyword) => score + (query.toLowerCase().includes(keyword.toLowerCase()) ? 3 : 0), 0)
      + terms.reduce((score, term) => score + (`${article.title}${article.summary}${article.content}`.toLowerCase().includes(term) ? 1 : 0), 0),
  })).sort((a, b) => b.score - a.score).filter((item) => item.score > 0).slice(0, limit).map((item) => item.article)
}
