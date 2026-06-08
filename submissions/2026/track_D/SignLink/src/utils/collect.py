import cv2
import mediapipe as mp
import numpy as np
import os

# 配置
DATA_PATH = os.path.join('HandSign_Data', 'hello') # 存放动作名称的文件夹
SEQUENCE_LENGTH = 30  # 每个动作录制30帧
os.makedirs(DATA_PATH, exist_ok=True)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5)
cap = cv2.VideoCapture(0)

def collect_data(action_name):
    sequence = []
    frame_count = 0
    
    print(f"开始录制动作: {action_name}。请开始做动作...")

    while len(sequence) < SEQUENCE_LENGTH:
        ret, frame = cap.read()
        if not ret: break

        # MediaPipe 处理
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(image)
        
        current_frame_landmarks = np.zeros((21, 3)) # 初始化全0，防止丢帧

        if results.multi_hand_landmarks:
            # 默认取第一只手
            hand_landmarks = results.multi_hand_landmarks[0]
            for i, lm in enumerate(hand_landmarks.landmark):
                current_frame_landmarks[i] = [lm.x, lm.y, lm.z]
            
            # 视觉反馈：在屏幕上画出来，告诉你正在录制
            mp.solutions.drawing_utils.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            cv2.putText(frame, f"Recording: {frame_count}/{SEQUENCE_LENGTH}", (50, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # 将当前帧的63个特征存入序列
        sequence.append(current_frame_landmarks.flatten())
        frame_count += 1
        
        cv2.imshow('Data Collection', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 保存数据
    if len(sequence) == SEQUENCE_LENGTH:
        data_array = np.array(sequence) # 形状为 (30, 63)
        file_name = f"{action_name}_{frame_count}.npy"
        np.save(os.path.join(DATA_PATH, file_name), data_array)
        print(f"成功保存: {file_name}")
    else:
        print("采集失败，帧数不足")

# 使用示例
action = input("请输入动作名称 (例如 'hello'): ")
collect_data(action)

cap.release()
cv2.destroyAllWindows()