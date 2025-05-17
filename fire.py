import cv2
import mediapipe as mp
import time
import random
import serial
import os
from picamera2 import Picamera2
from animations import set_expression, move_servos, animate_neutral_to

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

ser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
time.sleep(2)

camera = Picamera2()
camera.configure(camera.create_still_configuration(main={"size": (FRAME_WIDTH, FRAME_HEIGHT)}))
camera.start()

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands_detector = mp_hands.Hands(
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7,
    max_num_hands=1
)

def is_finger_extended(landmarks, tip_id, pip_id):
    return landmarks[tip_id].y < landmarks[pip_id].y

def is_gun_gesture(landmarks):
    index = is_finger_extended(landmarks, 8, 6)
    middle = is_finger_extended(landmarks, 12, 10)
    ring = not is_finger_extended(landmarks, 16, 14)
    pinky = not is_finger_extended(landmarks, 20, 18)
    thumb = landmarks[4].y < landmarks[0].y - 0.05
    return index and middle and ring and pinky and thumb

def is_fist(landmarks):
    fingers = [
        not is_finger_extended(landmarks, 8, 6),
        not is_finger_extended(landmarks, 12, 10),
        not is_finger_extended(landmarks, 16, 14),
        not is_finger_extended(landmarks, 20, 18),
    ]
    thumb_bent = landmarks[4].x < landmarks[3].x
    return all(fingers) and thumb_bent

def blink_once():
    animate_neutral_to("neutral")
    time.sleep(0.1)
    animate_neutral_to("neutral")
    print("blink")

def shake_head(pan_min=80, pan_max=100, duration=2.0, speed=0.1):
    end_time = time.time() + duration
    toggle = False
    while time.time() < end_time:
        pan = pan_min if toggle else pan_max
        toggle = not toggle
        move_servos(pan, 75, 65, 115)
        time.sleep(speed)

def main():
    gesture_triggered = False
    last_blink_time = time.time()
    next_blink_interval = random.uniform(3, 7)
    reset_time = None

    set_expression("neutral")

    while True:
        frame = camera.capture_array("main")
        frame = cv2.flip(frame, 1)
        display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        results = hands_detector.process(frame)
        current_time = time.time()

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(display_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                lm = hand_landmarks.landmark

                if is_gun_gesture(lm) and not gesture_triggered:
                    print("Gun gesture detected!")
                    move_servos(90, 75, 65, 115)
                    animate_neutral_to("confused")
                    shake_head()
                    reset_time = time.time() + 3
                    gesture_triggered = True

                elif is_fist(lm):
                    print("Fist detected! Exiting to menu...")
                    camera.stop()
                    time.sleep(1.0)
                    cv2.destroyAllWindows()
                    ser.close()
                    os.execvp("python3", ["python3", "/home/eyeay/app_menu.py"])

        if gesture_triggered and reset_time and current_time > reset_time:
            set_expression("neutral")
            move_servos(90, 75, 180, 0)
            gesture_triggered = False
            reset_time = None
            last_blink_time = time.time()
            next_blink_interval = random.uniform(3, 7)

        if not gesture_triggered and current_time - last_blink_time > next_blink_interval:
            blink_once()
            last_blink_time = current_time
            next_blink_interval = random.uniform(3, 7)

        cv2.imshow("Robot - Gun Gesture Response", display_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        time.sleep(0.01)

    camera.stop()
    time.sleep(0.5)
    cv2.destroyAllWindows()
    ser.close()
    os.execvp("python3", ["python3", "/home/eyeay/app_menu.py"])

if __name__ == "__main__":
    main()
