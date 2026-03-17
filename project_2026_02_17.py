import cv2
import mediapipe as mp
import numpy as np
import struct
import socket


client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_addr = ('192.168.0.59', 800)

# MediaPipe 초기화
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    min_detection_confidence=0.5, 
    min_tracking_confidence=0.5,
    refine_landmarks=True # 정밀도 향상
)

cap = cv2.VideoCapture(0)

# 1. 확장된 3D 모델 포인트 (기존 6개 + 외곽 및 이마 점 추가)
# 좌표 기준: 코 끝(0,0,0), 단위: mm (대략적인 표준 얼굴 비율)
model_points = np.array([
    # 중심 기준점
    (0.0, 0.0, 0.0),          # 1  Nose tip

    # 턱
    (0.0, -330.0, -65.0),     # 152 Chin

    # 이마
    (0.0, 350.0, -100.0),     # 10 Forehead center

    (-100.0, 330.0, -110.0),  # 103 Left forehead
    (100.0, 330.0, -110.0),   # 332 Right forehead

    # 얼굴 외곽
    (-350.0, 100.0, -200.0),  # 234 Left face edge
    (350.0, 100.0, -200.0),   # 454 Right face edge

    (-280.0, -150.0, -150.0), # 58 Left jaw
    (280.0, -150.0, -150.0),  # 288 Right jaw

], dtype=np.float64)

# 대응하는 MediaPipe 인덱스 리스트
indices = [ 
    1,    # Nose tip
    152,  # Chin

    10,   # Forehead center

    103,  # Left forehead
    332,  # Right forehead

    234,  # Left face edge
    454,  # Right face edge

    58,   # Left jaw
    288   # Right jaw
]

eye_idx = [145, 159, 374, 386]

mouth_idx = [13, 14, 61, 291]

prev_yaw = 0.0
prev_pitch = 0.0
prev_roll = 0.0
prev_left_blink = 0.0
prev_right_blink = 0.0
alpha = 0.2
eye_alpha = 0.5

while cap.isOpened():
    success, image = cap.read()
    if not success: break

    image = cv2.flip(image, 1)
    size = image.shape
    results = face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            # 2. 실시간 2D 이미지 포인트 추출
            image_points = []
            for idx in indices:
                lm = face_landmarks.landmark[idx]
                image_points.append((lm.x * size[1], lm.y * size[0]))
                
            image_points = np.array(image_points, dtype="double")
            
            def to_pixel(idx):
                lm = face_landmarks.landmark[idx]
                return np.array([lm.x * size[1], lm.y * size[0]])
            
            left_outer = to_pixel(33)
            left_inner = to_pixel(133)
            left_top   = to_pixel(159)
            left_bot   = to_pixel(145)
            
            right_outer = to_pixel(263)
            right_inner = to_pixel(362)
            right_top   = to_pixel(386)
            right_bot   = to_pixel(374)
            
            # 거리 계산
            left_eye_width  = np.linalg.norm(left_inner - left_outer)
            left_eye_height = np.linalg.norm(left_top - left_bot)
            right_eye_width = np.linalg.norm(right_inner - right_outer)
            right_eye_height = np.linalg.norm(right_top - right_bot)
            
            left_ear = (left_eye_height / left_eye_width)
            right_ear = (right_eye_height / right_eye_width)
            
            left_blink = 1.0 - np.clip((left_ear - 0.15) * 10, 0.0, 1.0)
            right_blink = 1.0 - np.clip((right_ear - 0.15) * 10, 0.0, 1.0)
            
            left_lip = to_pixel(61)
            right_lip = to_pixel(291)
            bot_lip = to_pixel(14)  
            top_lip = to_pixel(13)
            
            mouth_width = np.linalg.norm(left_lip - right_lip)
            mouth_height = np.linalg.norm(top_lip - bot_lip)
            
            mar = (mouth_height / mouth_width)
            open_mouth = np.clip((mar - 0.3) * 10, 0.0, 1.0)
            
            
            
            

            # 3. 카메라 매트릭스 설정
            focal_length = size[1]
            center = (size[1]/2, size[0]/2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype="double")

            dist_coeffs = np.zeros((4,1))

            # 4. SolvePnP 연산
            (success, rvec, tvec) = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_SQPNP)

            # 감도 조절 (Sensitivity)

            # 5. 시각화용 막대기 투영 (Y 오프셋 적용하여 위쪽 보정)
            # (0, -150, 600) -> -150은 위로 꺾음, 600은 막대 길이
            (nose_end_point2D, _) = cv2.projectPoints(
                np.array([(0.0, 0.0, 200.0)]), 
                rvec, tvec, camera_matrix, dist_coeffs
            )

            # 6. 그리기
            p1 = (int(image_points[0][0]), int(image_points[0][1]))
            p2 = (int(nose_end_point2D[0][0][0]), int(nose_end_point2D[0][0][1]))
            cv2.line(image, p1, p2, (255, 0, 0), 2)
            #R, _ = cv2.Rodrigues(rvec)
            #R = R.T
            #angles, _, _, _, _, _ = cv2.RQDecomp3x3(R)
            #pitch = angles[0]
            #yaw   = angles[1]
            #roll = angles[2]
            
            R, _ = cv2.Rodrigues(rvec)

            # 안정적인 yaw/pitch/roll 계산
            sy = np.sqrt(R[0,0] * R[0,0] + R[1,0] * R[1,0])
            
            singular = sy < 1e-6
            
            if not singular:
                pitch = np.arctan2(R[2,1], R[2,2])
                yaw   = np.arctan2(-R[2,0], sy)
                roll  = np.arctan2(R[1,0], R[0,0])
            else:
                pitch = np.arctan2(-R[1,2], R[1,1])
                yaw   = np.arctan2(-R[2,0], sy)
                roll  = 0
            
            # rad → deg
            pitch = np.degrees(pitch)
            yaw   = -np.degrees(yaw)
            roll  = -np.degrees(roll)
            

            

            
            if pitch < -90:
                pitch += 180
            elif pitch > 90:
                pitch -= 180
            #print(R)
            #print(np.linalg.det(R))
            print(f'yaw : {yaw}, pitch : {pitch}, roll : {roll}, left_blink : {left_blink}, Right_blink : {right_blink}, Open_mouth : {open_mouth}')
            
            
            payload = struct.pack(
            '<6f',
            yaw, pitch, roll, left_blink, right_blink, open_mouth
            )
        
            #packet = struct.pack('<I', len(payload)) + payload
            client_socket.sendto(payload, server_addr)

            for p in image_points:
                cv2.circle(image, (int(p[0]), int(p[1])), 3, (0, 0, 255), -1)

    cv2.imshow("head_unity", image)
    key = cv2.waitKey(1) & 0xFF
    if key == 27: break
    if cv2.getWindowProperty("head_unity", cv2.WND_PROP_VISIBLE) < 1: break

cap.release()
cv2.destroyAllWindows()