import cv2
import mediapipe as mp
import numpy as np
import time
import subprocess
import os
import serial
from picamera2 import Picamera2
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

serial_display = i2c(port=1, address=0x3D)
device = ssd1306(serial_display)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)

def update_oled_icon(index):
    app_name = os.path.splitext(APP_LIST[index])[0]
    display_text = app_name[:16]
    text_width, text_height = font.getsize(display_text)
    x = (device.width - text_width) // 2
    y = (device.height - text_height) // 2
    with canvas(device) as draw:
        draw.text((x, y), display_text, fill=255, font=font)

def clear_oled():
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline=0, fill=0)

def set_neutral_position():
    try:
        ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=1)
        time.sleep(2)
        command = "90,75,180,0\n"
        ser.write(command.encode('utf-8'))
        print("Sent neutral:", command.strip())
        time.sleep(1)
        ser.close()
    except Exception as e:
        print("Could not send neutral servo position:", e)

APP_FOLDER = "/home/eyeay/BEVR BOT APPS"
APP_LIST = sorted([f for f in os.listdir(APP_FOLDER) if f.endswith(".py")])
NUM_APPS = len(APP_LIST)
SELECTED_INDEX = 0

PINCH_THRESHOLD = 0.04
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

camera = Picamera2()
camera.configure(camera.create_still_configuration(main={"size": (FRAME_WIDTH, FRAME_HEIGHT)}))
camera.start()

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7, max_num_hands=1)

def is_pinch(hand_landmarks):
    tip = hand_landmarks.landmark[8]
    thumb = hand_landmarks.landmark[4]
    distance = np.hypot(tip.x - thumb.x, tip.y - thumb.y)
    return distance < PINCH_THRESHOLD

def is_fist(hand_landmarks):
    try:
        finger_tips = [8, 12, 16, 20]
        finger_mcps = [5, 9, 13, 17]
        closed_fingers = 0
        for tip, mcp in zip(finger_tips, finger_mcps):
            tip_y = hand_landmarks.landmark[tip].y
            mcp_y = hand_landmarks.landmark[mcp].y
            if tip_y - mcp_y > -0.02:
                closed_fingers += 1
        return closed_fingers >= 3
    except Exception as e:
        print("Error in is_fist:", e)
        return False

def draw_app_menu(image, selected_index):
    spacing = FRAME_WIDTH // NUM_APPS
    radius = 40
    for i in range(NUM_APPS):
        center = (spacing // 2 + i * spacing, FRAME_HEIGHT // 2)
        color = (0, 255, 0) if i == selected_index else (100, 100, 100)
        cv2.rectangle(image, (center[0]-radius, center[1]-radius), (center[0]+radius, center[1]+radius), color, -1)
        cv2.putText(image, f"{i+1}", (center[0]-10, center[1]+10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

def launch_app(index):
    app_path = os.path.join(APP_FOLDER, APP_LIST[index])
    print(f"Launching: {app_path}")
    clear_oled()
    subprocess.Popen(["python3", app_path])
    os._exit(0)

print("Starting app navigator... setting neutral position")
set_neutral_position()
time.sleep(2)

last_gesture = None
gesture_cooldown = 1.0
last_gesture_time = 0

update_oled_icon(SELECTED_INDEX)

while True:
    frame = camera.capture_array("main")
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    results = hands.process(rgb_frame)
    image = frame.copy()
    current_time = time.time()
    gesture = None

    if results.multi_hand_landmarks:
        hand = results.multi_hand_landmarks[0]
        mp_drawing.draw_landmarks(image, hand, mp_hands.HAND_CONNECTIONS)

        if is_fist(hand):
            gesture = "fist"
        elif is_pinch(hand):
            gesture = "pinch"

        print("Gesture:", gesture)

        if gesture != last_gesture and current_time - last_gesture_time > gesture_cooldown:
            if gesture == "pinch":
                SELECTED_INDEX = (SELECTED_INDEX + 1) % NUM_APPS
                update_oled_icon(SELECTED_INDEX)
                last_gesture_time = current_time
            elif gesture == "fist":
                launch_app(SELECTED_INDEX)

        last_gesture = gesture
    else:
        last_gesture = None

    draw_app_menu(image, SELECTED_INDEX)
    cv2.putText(image, "Pinch = Next | Fist = Select", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("BEVR App Navigator", image)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

clear_oled()
camera.stop()
cv2.destroyAllWindows()
