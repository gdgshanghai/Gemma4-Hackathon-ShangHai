import cv2
import mediapipe as mp

# 1. 初始化 MediaPipe 手部模型
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils  # 用于绘制关键点的工具
hands = mp_hands.Hands(
    static_image_mode=False,        # False 表示处理视频流（连续帧）
    max_num_hands=2,               # 同时检测几只手
    min_detection_confidence=0.5,   # 检测置信度阈值
    min_tracking_confidence=0.5     # 追踪置信度阈值
)

# 2. 打开摄像头
cap = cv2.VideoCapture(0)

print("正在启动摄像头... 按 'q' 退出")

while cap.isOpened():
    success, image = cap.read()
    if not success:
        print("忽略空帧")
        continue

    # 3. 图像预处理
    # OpenCV 默认读取的是 BGR 格式，而 MediaPipe 需要 RGB 格式
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # 为了提高性能，可以将图像标记为不可写
    image.flags.writeable = False
    results = hands.process(image)

    # 4. 图像后处理
    # 将图像转回 BGR 以便使用 OpenCV 显示
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    # 5. 检查是否检测到手部
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # A. 在图像上绘制关键点和连接线
            mp_drawing.draw_landmarks(
                image, 
                hand_landmarks, 
                mp_hands.HAND_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2), # 点的样式
                mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2)                # 线的样式
            )

            # B. 【核心】获取关键点的坐标数据
            # 每个 hand_landmarks 包含 21 个点
            for id, lm in enumerate(hand_landmarks.landmark):
                # lm.x, lm.y, lm.z 是归一化后的坐标 (0.0 到 1.0)
                # 需要乘以图像宽高才能得到像素坐标
                h, w, c = image.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                
                # 打印第一个点（大拇指指尖）的坐标作为测试
                if id == 4: 
                    cv2.putText(image, f"Thumb Tip: {cx},{cy}", (cx, cy-20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # 6. 显示结果
    cv2.imshow('MediaPipe Hands', image)

    # 按 'q' 退出循环
    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()