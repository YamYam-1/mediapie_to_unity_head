# meidapipe to unity

MediaPipe Face Mesh를 이용해 얼굴을 추적하고, 추적 결과를 Unity의 VRM 아바타에 실시간으로 적용하는 프로젝트입니다.

---


## Demo

<img width="1562" height="807" alt="Image" src="https://github.com/user-attachments/assets/9384040e-c63b-40db-ad9c-085c44f88236" />

---

## Tech Stack


- MediaPipe
- OpenCV
- Python
- C#
- VRM 0.x
- UDP

---

## Features

먼저 MediaPipe를 통해 2D 점 데이터를 추정합니다. 
```cpp
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    min_detection_confidence=0.5, 
    min_tracking_confidence=0.5,
    refine_landmarks=True

results = face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
)
```
EAR(Eye Aspect Ratio)를 이용하여 눈 깜빡임을, MAR(Mouth Aspect Ratio)를 이용하여 입 벌림 정도를 계산했습니다.
VRM BlendShape의 Blink는 값이 0이면 눈을 뜨고, 1이면 눈을 감는 형태이므로 EAR 값을 반전하여 사용했습니다.
반면 Mouth Open은 MAR 값이 증가할수록 입이 더 크게 열리도록 그대로 매핑했습니다.
```cpp

left_ear = (left_eye_height / left_eye_width)
right_ear = (right_eye_height / right_eye_width)
            
left_blink = 1.0 - np.clip((left_ear - 0.15) * 10, 0.0, 1.0)
right_blink = 1.0 - np.clip((right_ear - 0.15) * 10, 0.0, 1.0)
            
mouth_width = np.linalg.norm(left_lip - right_lip)
mouth_height = np.linalg.norm(top_lip - bot_lip)
            
mar = (mouth_height / mouth_width)
open_mouth = np.clip((mar - 0.3) * 10, 0.0, 1.0)
```


SolvePnP 는 MediaPipe에서 뽑은 2D 점 데이터를 통해 3D 물체의 위치와 회전을 구해줍니다.
```cpp
(success, rvec, tvec) = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_SQPNP)
```

Unity와 OpenCV는 다른 좌표계를 가지고 있습니다.Yaw와 Roll 축은 부호를 반대로 Unity 좌표계에 맞게 보정했습니다.
```cpp
pitch = np.degrees(pitch)
yaw   = -np.degrees(yaw)
roll  = -np.degrees(roll)
```

추출한 Head Pose와 표정 데이터를 하나의 패킷으로 직렬화하여 UDP를 통해 Unity로 실시간 전송했습니다.
```cpp
payload = struct.pack(
            '<6f',
            yaw, pitch, roll, left_blink, right_blink, open_mouth
            )
        
            client_socket.sendto(payload, server_addr)
```

Server 측에서 VRM 0.0의 VRMBlendShapeProxy를 이용하여 눈 깜빡임과 입 벌림에 대응하는 BlendShape를 초기화하고, 실시간으로 전달받은 값을 모델에 적용했습니다.

```cpp
proxy = GetComponent<VRMBlendShapeProxy>();
L_blinkKey = BlendShapeKey.CreateFromPreset(BlendShapePreset.Blink_L);
R_blinkKey = BlendShapeKey.CreateFromPreset(BlendShapePreset.Blink_R);
Open_mouth_Key = BlendShapeKey.CreateFromPreset(BlendShapePreset.A);
```


Python에서 전달받은 Head Pose를 VRM Head Bone에 적용하여 얼굴 회전을 구현했습니다.
 Quaternion.Slerp를 사용해 현재 회전과 목표 회전 사이를 보간하여, 얼굴 움직임이 자연스럽게 이어지도록 했습니다.
```cpp
if (Head != null)
{
  Quaternion target = Quaternion.Euler(head_pitch, head_yaw, head_roll);
  Head.localRotation = Quaternion.Slerp(
  Head.localRotation,
  target,
  Time.deltaTime * 10f
  );
}
```

얼굴 추적 데이터는 프레임마다 미세한 오차가 발생하여 머리와 표정이 떨리는 현상이 있었습니다.
이를 완화하기 위해 이전 프레임과 현재 프레임을 선형 보간(Low-pass Filtering)하여 노이즈를 감소시켰습니다.
```cpp
head_yaw = prev_hyaw + (head_yaw - prev_hyaw) * alpha;
head_pitch = prev_hpitch + (head_pitch - prev_hpitch) * alpha;
head_roll = prev_hroll + (head_roll - prev_hroll) * alpha;

left_blink = prev_left_blink + (left_blink - prev_left_blink) * eye_alpha;
right_blink = prev_right_blink + (right_blink - prev_right_blink) * eye_alpha;
open_mouth = prev_open_mouth + (open_mouth - prev_open_mouth) * eye_alpha;
```
