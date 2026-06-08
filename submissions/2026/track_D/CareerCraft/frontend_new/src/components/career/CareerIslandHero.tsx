import React from 'react';
import Image from 'next/image';
import { PixelBadge } from '@/components/pixel';
import { getCareerImage, getMentorImage } from '@/constants/images';

interface CareerIslandHeroProps {
  careerId: string;
  careerName: string;
}

const CAREER_STORY: Record<
  string,
  {
    islandName: string;
    chapter: string;
    mentorName: string;
    mentorRole: string;
    headline: string;
    message: string;
    signal: string;
  }
> = {
  'data-analyst': {
    islandName: '数据山脉',
    chapter: '从校园传送门出发',
    mentorName: '林澈',
    mentorRole: 'AI 数据导师',
    headline: '把职业规划草图，变成一次可完成、可复盘的真实试炼。',
    message:
      '你是一名计算机系大学生。进入职业岛后，你会通过真实任务验证岗位方向：做什么、怎么做、做到什么程度，都由 AI 同事给出反馈。',
    signal: '当前试炼：用数据回答一个真实业务问题。',
  },
  'software-engineer': {
    islandName: '硅之岛',
    chapter: '进入工程工坊',
    mentorName: '许砚',
    mentorRole: 'AI 工程导师',
    headline: '从课堂代码走向工程任务，学会拆解、实现和复盘。',
    message:
      '硅之岛会把抽象知识转化成真实工程委托。AI 导师会像团队同事一样审阅你的方案和交付。',
    signal: '当前试炼：完成一个可交付的工程小任务。',
  },
  'product-designer': {
    islandName: '产品设计港',
    chapter: '进入产品工作室',
    mentorName: '叶舟',
    mentorRole: 'AI 产品导师',
    headline: '把用户需求、技术约束和方案表达连成一条路线。',
    message:
      '产品设计港适合想把技术能力连接到用户价值的学生。你会练习需求拆解、用户旅程、原型说明和优先级判断。',
    signal: '当前试炼：把一个模糊需求整理成可执行方案。',
  },
  'ai-researcher': {
    islandName: 'AI 研究塔',
    chapter: '远方研究区',
    mentorName: '沈栖',
    mentorRole: 'AI 研究导师',
    headline: '把模型想法变成可以验证、可以复盘的实验。',
    message:
      '这条路线将训练提示工程、模型评估和实验设计。当前仍在建设中，建议先完成数据或工程路线作为前置基础。',
    signal: '当前状态：路线预告，等待开放。',
  },
};

export default function CareerIslandHero({ careerId, careerName }: CareerIslandHeroProps) {
  const story = CAREER_STORY[careerId] ?? {
    islandName: careerName,
    chapter: '职业大陆初探',
    mentorName: 'CareerCraft',
    mentorRole: 'AI 职业导师',
    headline: '把职业兴趣变成一条可以实践、可以复盘的路线。',
    message: '进入职业大陆后，你会通过模拟任务理解岗位日常，并把成果沉淀为成长档案。',
    signal: '当前试炼：完成第一次职业探索。',
  };
  const heroImage = getCareerImage(careerId);
  const mentorImage = getMentorImage(careerId);

  return (
    <section
      className="relative min-h-[520px] overflow-hidden border-4 border-slate-700 bg-slate-950 shadow-[0_18px_42px_rgba(2,6,23,0.52)]"
      style={{
        backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.91) 0%, rgba(2,6,23,0.76) 38%, rgba(2,6,23,0.18) 74%), url(${heroImage})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-slate-950 to-transparent" />

      <div className="relative z-10 flex min-h-[520px] flex-col justify-between p-5 sm:p-8 lg:p-10">
        <div className="max-w-2xl">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <PixelBadge variant="warning">计算机系职业规划沙盒</PixelBadge>
            <span className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
              {story.chapter}
            </span>
          </div>

          <p className="mb-3 font-mono text-sm uppercase tracking-[0.18em] text-slate-400">
            Career Continent / {careerName}
          </p>
          <h1 className="pixel-title mb-5 text-4xl font-bold leading-tight text-amber-300 sm:text-5xl">
            {story.islandName}
          </h1>
          <p className="mb-5 text-xl font-semibold leading-8 text-slate-100">{story.headline}</p>
          <p className="max-w-xl text-base leading-7 text-slate-300">{story.message}</p>
        </div>

        <div className="mt-10 flex max-w-4xl flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="grid gap-2 sm:grid-cols-3">
            {['探索岗位', '完成委托', '沉淀作品'].map((label, index) => (
              <div key={label} className="border border-amber-700/50 bg-slate-950/62 px-4 py-3 backdrop-blur-sm">
                <div className="font-mono text-xs text-amber-500">0{index + 1}</div>
                <div className="mt-1 text-sm font-bold text-slate-100">{label}</div>
              </div>
            ))}
          </div>

          <aside className="max-w-md border border-slate-600 bg-slate-950/72 p-4 backdrop-blur-sm">
            <div className="flex items-center gap-4">
              <div className="relative h-16 w-16 overflow-hidden border-2 border-amber-600 bg-slate-900">
                <Image src={mentorImage} alt={`${story.mentorName} mentor portrait`} fill className="object-cover" sizes="64px" />
              </div>
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.16em] text-emerald-300">Mentor Online</div>
                <div className="mt-1 font-bold text-amber-300">{story.mentorName}</div>
                <div className="text-xs text-slate-400">{story.mentorRole}</div>
              </div>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">{story.signal}</p>
          </aside>
        </div>
      </div>
    </section>
  );
}
