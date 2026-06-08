import { SignWord } from "../types";

// Generates a mock set of 21 hand landmarks (x, y, z) based on hand shapes
function generateHandLandmarks(shape: "open" | "fist" | "love" | "thankyou" | "thumbsup") {
  const points: { x: number; y: number; z: number }[] = [];
  // Center is wrist (0.5, 0.8, 0)
  const wrist = { x: 0.5, y: 0.8, z: 0 };
  points.push(wrist);

  // Helper to add a finger
  const addFinger = (angleRad: number, length: number, isExtended: boolean) => {
    const baseAngle = angleRad;
    const mcpX = wrist.x + Math.sin(baseAngle) * 0.15;
    const mcpY = wrist.y - Math.cos(baseAngle) * 0.15;
    points.push({ x: mcpX, y: mcpY, z: -0.02 });

    const foldFactor = isExtended ? 1.0 : 0.3;
    const pipX = mcpX + Math.sin(baseAngle) * 0.1 * foldFactor;
    const pipY = mcpY - Math.cos(baseAngle) * 0.1 * foldFactor;
    points.push({ x: pipX, y: pipY, z: -0.04 });

    const dipX = pipX + Math.sin(baseAngle) * 0.08 * foldFactor;
    const dipY = pipY - Math.cos(baseAngle) * 0.08 * foldFactor;
    points.push({ x: dipX, y: dipY, z: -0.05 });

    const tipX = dipX + Math.sin(baseAngle) * 0.07 * foldFactor;
    const tipY = dipY - Math.cos(baseAngle) * 0.07 * foldFactor;
    points.push({ x: tipX, y: tipY, z: -0.06 });
  };

  if (shape === "open") {
    // Thumb
    addFinger(-0.5, 0.2, true);
    // Index
    addFinger(-0.2, 0.3, true);
    // Middle
    addFinger(0.0, 0.32, true);
    // Ring
    addFinger(0.2, 0.3, true);
    // Pinky
    addFinger(0.4, 0.25, true);
  } else if (shape === "fist") {
    // All fingers folded
    addFinger(-0.4, 0.2, false);
    addFinger(-0.2, 0.2, false);
    addFinger(0.0, 0.2, false);
    addFinger(0.2, 0.2, false);
    addFinger(0.4, 0.2, false);
  } else if (shape === "love") {
    // Thumb: Extended
    addFinger(-0.5, 0.2, true);
    // Index: Extended
    addFinger(-0.2, 0.3, true);
    // Middle & Ring: Folded
    addFinger(0.0, 0.2, false);
    addFinger(0.2, 0.2, false);
    // Pinky: Extended
    addFinger(0.4, 0.25, true);
  } else if (shape === "thankyou") {
    // Hand slightly cupped, fingers slightly curled together
    addFinger(-0.4, 0.2, true);
    addFinger(-0.1, 0.25, true);
    addFinger(0.0, 0.27, true);
    addFinger(0.1, 0.25, true);
    addFinger(0.3, 0.2, true);
  } else {
    // thumbsup
    // Thumb extended high, rest tightly folded
    addFinger(-0.8, 0.25, true);
    addFinger(-0.2, 0.15, false);
    addFinger(0.0, 0.15, false);
    addFinger(0.2, 0.15, false);
    addFinger(0.4, 0.15, false);
  }

  // Ensure precisely 21 landmarks
  return points.slice(0, 21);
}

export const SIGN_DATABASE: SignWord[] = [
  {
    id: "hello",
    word: "你好",
    pinyin: "nǐ hǎo",
    translation: "Hello",
    category: "greetings",
    description: "右手伸出食指和中指，做‘你好’手势，或右手握拳对准额头微微点头致意。",
    landmarksDescription: "右手五指并拢，掌心向内微俯，平伸自左向右轻移，代表友好问候。",
    landmarks: generateHandLandmarks("open"),
    difficulty: "easy",
    memoryLevel: 85,
    emoji: "👋"
  },
  {
    id: "thankyou",
    word: "谢谢",
    pinyin: "xiè xiè",
    translation: "Thank You",
    category: "greetings",
    description: "右手大拇指弯曲两次，代表像鞠躬一样表达诚挚谢意。",
    landmarksDescription: "大拇指垂直微曲点头两次，其余四指轻握成拳，表示鞠躬致谢。",
    landmarks: generateHandLandmarks("thankyou"),
    difficulty: "easy",
    memoryLevel: 90,
    emoji: "💖"
  },
  {
    id: "iloveyou",
    word: "我爱你",
    pinyin: "wǒ ài nǐ",
    translation: "I Love You",
    category: "greetings",
    description: "伸出大拇指、食指和小拇指，代表英语'I/L/Y'手手字母缩写。",
    landmarksDescription: "大拇指、食指、小指同时伸直，中指和无名指曲向掌心。",
    landmarks: generateHandLandmarks("love"),
    difficulty: "medium",
    memoryLevel: 75,
    emoji: "🤟"
  },
  {
    id: "sorry",
    word: "对不起",
    pinyin: "duì bù qǐ",
    translation: "Sorry",
    category: "greetings",
    description: "右手小指伸直直立在面颊侧，脸露歉意神色，微微低头。",
    landmarksDescription: "小指单独竖起，掌心朝内，在胸前或脸颊旁轻轻绕圈圈表示歉意。",
    landmarks: generateHandLandmarks("open"),
    difficulty: "medium",
    memoryLevel: 50,
    emoji: "🥺"
  },
  {
    id: "eat",
    word: "吃饭",
    pinyin: "chī fàn",
    translation: "Eat Food",
    category: "daily",
    description: "右手五指尖捏拢，在嘴前提动数次，做往嘴里送食物的拟态动作。",
    landmarksDescription: "五指作持筷或捏食捏笔状，置于嘴前方往返移动两次，生动直观。",
    landmarks: generateHandLandmarks("fist"),
    difficulty: "easy",
    memoryLevel: 60,
    emoji: "🍚"
  },
  {
    id: "drink",
    word: "喝水",
    pinyin: "hē shuǐ",
    translation: "Drink Water",
    category: "daily",
    description: "右手半握拳如持杯状，指尖向内虚握，贴近唇部做仰头饮水状。",
    landmarksDescription: "大拇指、食指张开呈C型杯口状，举至唇边微微倾斜，拟态喝水动作。",
    landmarks: generateHandLandmarks("open"),
    difficulty: "easy",
    memoryLevel: 70,
    emoji: "🥛"
  },
  {
    id: "yes",
    word: "是的/赞同",
    pinyin: "shì de",
    translation: "Yes / Agree",
    category: "daily",
    description: "右手握拳，竖起大拇指像盖章或上下点动一样，代表绝对赞成。",
    landmarksDescription: "大拇指顶端竖直朝上，其余指结微曲，在视线前方上下微微顿挫两次。",
    landmarks: generateHandLandmarks("thumbsup"),
    difficulty: "easy",
    memoryLevel: 95,
    emoji: "👍"
  },
  {
    id: "doctor",
    word: "需要医生",
    pinyin: "xū yào yī shēng",
    translation: "Need Doctor",
    category: "emergency",
    description: "右手搭在左腕动脉处，模拟老中医诊脉的动作，代表医生或医疗诊治。",
    landmarksDescription: "右手食、中指并拢搭在左手手腕关节外侧，轻点三下，代表把脉、寻医问诊。",
    landmarks: generateHandLandmarks("thankyou"),
    difficulty: "hard",
    memoryLevel: 40,
    emoji: "🏥"
  },
  {
    id: "danger",
    word: "危险",
    pinyin: "wēi xiǎn",
    translation: "Danger",
    category: "emergency",
    description: "双手握拳在胸口交叉，面部露出极度紧张警惕的神情。",
    landmarksDescription: "双手立掌在胸前交叉呈X型，掌心向外，并向两侧迅速拉开，表达万分危险防范。",
    landmarks: generateHandLandmarks("fist"),
    difficulty: "hard",
    memoryLevel: 30,
    emoji: "🚨"
  },
  {
    id: "help",
    word: "救命/帮助",
    pinyin: "jiù mìng",
    translation: "Help Me",
    category: "emergency",
    description: "单手上举向外迅速翻动掌心拍打，配以焦急表情，代表呼救帮助。",
    landmarksDescription: "手掌高举张开，手腕自左向右剧烈摇晃两下，或右手张开轻拍左手侧立手背表示求救。",
    landmarks: generateHandLandmarks("open"),
    difficulty: "medium",
    memoryLevel: 35,
    emoji: "🆘"
  }
];

// Helper to calculate similarity score between two landmark sets
export function calculateMatchScore(
  userLandmarks: { x: number; y: number; z: number }[],
  targetLandmarks: { x: number; y: number; z: number }[]
): number {
  if (userLandmarks.length !== targetLandmarks.length) return 0;

  // Let's compare relative angles or normalized coordinates
  // Normalize user coordinate system relative to wrist position
  const userWrist = userLandmarks[0];
  const targetWrist = targetLandmarks[0];

  let sumDiff = 0;
  for (let i = 1; i < userLandmarks.length; i++) {
    const duX = userLandmarks[i].x - userWrist.x;
    const duY = userLandmarks[i].y - userWrist.y;
    const duZ = userLandmarks[i].z - userWrist.z;

    const dtX = targetLandmarks[i].x - targetWrist.x;
    const dtY = targetLandmarks[i].y - targetWrist.y;
    const dtZ = targetLandmarks[i].z - targetWrist.z;

    const dist = Math.sqrt(
      Math.pow(duX - dtX, 2) + Math.pow(duY - dtY, 2) + Math.pow(duZ - dtZ, 2)
    );
    sumDiff += dist;
  }

  // Convert sum differences back to average similarity
  const avgDiff = sumDiff / (userLandmarks.length - 1);
  // Match score is scaled cleanly between 70% and 99% for responsiveness
  const score = Math.max(0, 100 - avgDiff * 450);
  return Math.round(Math.min(99, Math.max(45, score)));
}
