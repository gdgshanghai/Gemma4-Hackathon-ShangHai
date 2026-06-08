export interface Career {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  unlocked: boolean;
}

export interface CareerIsland {
  id: string;
  name: string;
  islandName: string;
  description: string;
  mentorName: string;
  mentorAvatar: string;
  themeColor: string;
  careers: Career[];
}
