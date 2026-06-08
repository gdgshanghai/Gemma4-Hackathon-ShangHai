export interface SignWord {
  id: string;
  word: string;
  pinyin: string;
  translation: string;
  category: "greetings" | "daily" | "emergency";
  description: string;
  // Hand joint descriptions relative to standard 21 MediaPipe landmarks
  landmarksDescription: string;
  // Vector data simulated for practice matching
  landmarks: { x: number; y: number; z: number }[];
  difficulty: "easy" | "medium" | "hard";
  memoryLevel: number; // 0 to 100 for Spaced Repetition
  lastPracticed?: string;
  emoji: string;
}

export interface Message {
  id: string;
  sender: "self" | "peer" | "system";
  text: string;
  timestamp: string;
  isGesture?: boolean; // Text translated from sign language
  gestureWord?: string;
  reactionEmoji?: string;
}

export interface CallSession {
  peerName: string;
  peerRole: string;
  status: "idle" | "ringing" | "connected";
  latencyMs: number;
  fps: number;
  resolution: string;
  bitrateKbps: number;
  packetLoss: number;
  useSignLanguageToText: boolean;
  visualRingtoneEnabled: boolean;
}

export interface PracticeSession {
  activeWord: SignWord | null;
  score: number; // 0 to 100 accuracy
  isMatched: boolean;
  userFeedState: "searching" | "analyzing" | "matched";
}
