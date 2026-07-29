using System;
using System.Net;
using System.Net.Sockets;
using UnityEngine;
using System.Threading;
using Unity;
using Unity.Mathematics;
using VRM;
public class server : MonoBehaviour
{

    public Transform Head;
    VRMBlendShapeProxy proxy;
    BlendShapeKey L_blinkKey, R_blinkKey, Open_mouth_Key;

    UdpClient client;
    Thread thread;
    const int Port = 800;
    float head_yaw, head_pitch, head_roll, left_blink, right_blink, open_mouth;
    float prev_hyaw = 0, prev_hpitch = 0, prev_hroll = 0;
    float prev_left_blink = 0, prev_right_blink = 0;
    float prev_open_mouth = 0;

    [SerializeField]
    float alpha = 0.2f;

    [SerializeField]
    float eye_alpha = 0.5f;

    bool running;
    async void Start()
    {
        client = new UdpClient(Port);
        proxy = GetComponent<VRMBlendShapeProxy>();
        L_blinkKey = BlendShapeKey.CreateFromPreset(BlendShapePreset.Blink_L);
        R_blinkKey = BlendShapeKey.CreateFromPreset(BlendShapePreset.Blink_R);
        Open_mouth_Key = BlendShapeKey.CreateFromPreset(BlendShapePreset.A);

        running = true;
        while (running)
        {
            UdpReceiveResult result = await client.ReceiveAsync();
            byte[] data = result.Buffer;

            head_yaw = System.BitConverter.ToSingle(data, 0);
            head_pitch = System.BitConverter.ToSingle(data, 4);
            head_roll = System.BitConverter.ToSingle(data, 8);
            left_blink = System.BitConverter.ToSingle(data, 12);
            right_blink = System.BitConverter.ToSingle(data, 16);
            open_mouth = System.BitConverter.ToSingle(data, 20);


            head_yaw = prev_hyaw + (head_yaw - prev_hyaw) * alpha;
            head_pitch = prev_hpitch + (head_pitch - prev_hpitch) * alpha;
            head_roll = prev_hroll + (head_roll - prev_hroll) * alpha;

            left_blink = prev_left_blink + (left_blink - prev_left_blink) * eye_alpha;
            right_blink = prev_right_blink + (right_blink - prev_right_blink) * eye_alpha;
            open_mouth = prev_open_mouth + (open_mouth - prev_open_mouth) * eye_alpha;

            prev_hyaw = head_yaw;
            prev_hpitch = head_pitch;
            prev_hroll = head_roll;
            prev_left_blink = left_blink;
            prev_right_blink = right_blink;
            prev_open_mouth = open_mouth;

            Debug.Log($"Yaw : {head_yaw}, Pitch : {head_pitch}, Roll : {head_roll}");
        }

    }

    void OnDisable()
    {
        running = false;
        client?.Close();
        Debug.Log("Closed");
    }

    private void LateUpdate()
    {
        if (Head != null)
        {
            Quaternion target = Quaternion.Euler(head_pitch, head_yaw, head_roll);
            Head.localRotation = Quaternion.Slerp(
                Head.localRotation,
                target,
                Time.deltaTime * 10f
            );
        }


        proxy.ImmediatelySetValue(L_blinkKey, left_blink);
        proxy.ImmediatelySetValue(R_blinkKey, right_blink);
        proxy.ImmediatelySetValue(Open_mouth_Key, open_mouth);

    }


}
