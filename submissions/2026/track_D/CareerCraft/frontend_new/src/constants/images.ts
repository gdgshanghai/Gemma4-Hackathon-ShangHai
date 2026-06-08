/**
 * CareerCraft pixel story asset manifest.
 * All image files live in public/images.
 */
export const IMAGES = {
  // Scenes / maps
  WORLD_MAP: '/images/world-map.png',
  GUILD_HALL: '/images/guild-hall.png',
  ENGINEER_COMMUNITY_GUILD: '/images/engineer-community-guild-v1.png',
  CAREER_CAMPUS_BACKDROP: '/images/career-continent-v2.png',
  QUEST_PANEL: '/images/quest-panel-v2.png',
  MISSION_WORKBENCH: '/images/mission-workbench-v1.png',
  PORTFOLIO_ARCHIVE: '/images/portfolio-archive-v1.png',
  FEYNMAN_CHAMBER: '/images/feynman-chamber-v1.png',

  // Career islands
  DATA_MOUNTAINS: '/images/data-mountains.png',
  DATA_STORY_HERO: '/images/career-data-story-v2.png',
  SILICON_ISLE: '/images/silicon-isle-v3.png',
  PRODUCT_DESIGN_HARBOR: '/images/product-design-harbor-v1.png',
  AI_RESEARCH_TOWER: '/images/ai-research-tower-v1.png',

  // Mentors
  MENTOR_DATA: '/images/mentor-data.png',
  MENTOR_DATA_GUIDE: '/images/mentor-data-guide-v2.png',
  MENTOR_SOFTWARE: '/images/mentor-software-v2.png',
  MENTOR_PRODUCT: '/images/mentor-product-v1.png',
  MENTOR_COMPANIONS: '/images/mentor-companions-v1.png',
  MENTOR_DATA_STATES: '/images/mentor-data-states-v1.png',
  MENTOR_SOFTWARE_STATES: '/images/mentor-software-states-v1.png',
  MENTOR_PRODUCT_STATES: '/images/mentor-product-states-v1.png',
  MENTOR_AI_STATES: '/images/mentor-ai-states-v1.png',
} as const;

/** Get the main island image for a career id. */
export function getCareerImage(careerId: string): string {
  if (careerId.includes('data')) return IMAGES.DATA_STORY_HERO;
  if (careerId.includes('software')) return IMAGES.SILICON_ISLE;
  if (careerId.includes('product') || careerId.includes('design') || careerId.includes('ux')) {
    return IMAGES.PRODUCT_DESIGN_HARBOR;
  }
  if (careerId.includes('ai') || careerId.includes('research') || careerId.includes('ml')) {
    return IMAGES.AI_RESEARCH_TOWER;
  }
  return IMAGES.WORLD_MAP;
}

/** Get the mentor portrait for a career id. */
export function getMentorImage(careerId: string): string {
  if (careerId.includes('data')) return IMAGES.MENTOR_DATA_GUIDE;
  if (careerId.includes('software')) return IMAGES.MENTOR_SOFTWARE;
  if (careerId.includes('product') || careerId.includes('design') || careerId.includes('ux')) {
    return IMAGES.MENTOR_PRODUCT;
  }
  if (careerId.includes('ai') || careerId.includes('research') || careerId.includes('ml')) {
    return IMAGES.AI_RESEARCH_TOWER;
  }
  return IMAGES.MENTOR_DATA;
}

export function getMentorStateSheet(careerId: string): string {
  if (careerId.includes('software')) return IMAGES.MENTOR_SOFTWARE_STATES;
  if (careerId.includes('product') || careerId.includes('design') || careerId.includes('ux')) {
    return IMAGES.MENTOR_PRODUCT_STATES;
  }
  if (careerId.includes('ai') || careerId.includes('research') || careerId.includes('ml')) {
    return IMAGES.MENTOR_AI_STATES;
  }
  return IMAGES.MENTOR_DATA_STATES;
}
