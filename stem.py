import cv2
import mediapipe as mp
import pygame
import time
import os
import threading
import serial
import math
import sys
from picamera2 import Picamera2
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageDraw

FRAME_WIDTH, FRAME_HEIGHT = 640, 480
VOLUME_THRESHOLD = 0.1
EXTENSION_FACTOR = 0.35
SONGS_DIR = "/home/eyeay/Music/SONGS"

stem_files = {
    "vocals": "vocals.mp3",
    "guitar": "guitar.mp3",
    "drums": "drums.mp3",
    "bass": "bass.mp3"
}

stem_state = "selecting"
current_song_index = 0
last_pinch_time = 0
pinch_count = 0
pinch_detected = False
DOUBLE_PINCH_WINDOW = 1.5
FIST_HOLD_DURATION = 3.0
fist_start_time = None

song_folders = [f for f in os.listdir(SONGS_DIR) if os.path.isdir(os.path.join(SONGS_DIR, f))]
if not song_folders:
    print("❌ No song folders found in:", SONGS_DIR)
    sys.exit(1)

ser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
time.sleep(2)
oled_serial = i2c(port=1, address=0x3D)
device = ssd1306(oled_serial)
camera = Picamera2()
camera.configure(camera.create_still_configuration(main={"size": (FRAME_WIDTH, FRAME_HEIGHT)}))
camera.start()

pygame.mixer.init()
channels = {
    "vocals": pygame.mixer.Channel(0),
    "guitar": pygame.mixer.Channel(1),
    "drums": pygame.mixer.Channel(2),
    "bass": pygame.mixer.Channel(3)
}

def load_stems(index):
    folder = os.path.join(SONGS_DIR, song_folders[index])
    try:
        return {
            name: pygame.mixer.Sound(os.path.join(folder, filename))
            for name, filename in stem_files.items()
        }
    except Exception as e:
        print("❌ Failed to load stems from:", folder)
        print("Error:", e)
        sys.exit(1)

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands_detector = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7, max_num_hands=1)

def move_servos(pan, tilt, left, right):
    command = f"{int(pan)},{int(tilt)},{int(left)},{int(right)}\n"
    ser.write(command.encode("utf-8"))

def dance_animation():
    t = 0
    while stem_state == "playing":
        tilt = 80 + 5 * math.sin(t)
        left_wave = (math.sin(t) + 1) / 2
        left_arm = int(65 + left_wave * (180 - 65))
        right_wave = 1 - left_wave
        right_arm = int(0 + right_wave * (115 - 0))
        move_servos(90, int(tilt), left_arm, right_arm)
        time.sleep(0.05)
        t += 0.1

def is_fist(lm):
    return all(lm[tip].y > lm[pip].y for tip, pip in [(8,6), (12,10), (16,14), (20,18)]) and lm[4].x < lm[3].x

def is_pinch(lm):
    dist = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
    return dist < 0.05

def compute_finger_volume(lm, pip_idx, tip_idx, height):
    pip_y = lm[pip_idx].y * FRAME_HEIGHT
    tip_y = lm[tip_idx].y * FRAME_HEIGHT
    return max(0.0, min(1.0, (pip_y - tip_y) / (height * EXTENSION_FACTOR)))

def show_oled_song(name):
    name = name.replace("_", " ").title()
    with canvas(device) as draw:
        draw.text((5, 20), "Select Song:", fill=255)
        draw.text((5, 40), name[:20], fill=255)

def show_volume_bars(volumes):
    with canvas(device) as draw:
        bar_width = 10
        max_height = 40
        spacing = 15
        labels = ["V", "G", "D", "B"]
        num_bars = len(labels)
        total_width = num_bars * bar_width + (num_bars - 1) * spacing
        x_start = (device.width - total_width) // 2

        for i, (label, vol) in enumerate(zip(labels, volumes.values())):
            x = x_start + i * (bar_width + spacing)
            bar_height = int(vol * max_height)
            y_top = 24 + (max_height - bar_height)
            draw.rectangle((x, y_top, x + bar_width, 24 + max_height), fill=255)
            label_x = x + (bar_width // 2) - 3
            draw.text((label_x, 10), label, fill=255)

def main():
    global stem_state, current_song_index, last_pinch_time, pinch_count, pinch_detected
    global fist_start_time

    show_oled_song(song_folders[current_song_index])
    stem_sounds = {}

    while True:
        frame = camera.capture_array("main")
        frame = cv2.flip(frame, 1)
        display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        results = hands_detector.process(frame)

        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            lm = hand.landmark
            mp_drawing.draw_landmarks(display_frame, hand, mp_hands.HAND_CONNECTIONS)

            if is_fist(lm):
                if fist_start_time is None:
                    fist_start_time = time.time()
                elif time.time() - fist_start_time >= FIST_HOLD_DURATION:
                    camera.stop()
                    time.sleep(1)
                    cv2.destroyAllWindows()
                    pygame.mixer.quit()
                    ser.close()
                    os.execvp("python3", ["python3", "/home/eyeay/app_menu.py"])
            else:
                fist_start_time = None

            if is_pinch(lm):
                if not pinch_detected:
                    pinch_detected = True
                    now = time.time()
                    if now - last_pinch_time < DOUBLE_PINCH_WINDOW:
                        pinch_count += 1
                    else:
                        pinch_count = 1
                    last_pinch_time = now

                    if stem_state == "selecting":
                        if pinch_count == 1:
                            current_song_index = (current_song_index + 1) % len(song_folders)
                            show_oled_song(song_folders[current_song_index])
                        elif pinch_count >= 2:
                            stem_sounds = load_stems(current_song_index)
                            for name, sound in stem_sounds.items():
                                channels[name].play(sound, loops=-1)
                            stem_state = "playing"
                            threading.Thread(target=dance_animation, daemon=True).start()
                            pinch_count = 0
            else:
                pinch_detected = False

            if stem_state == "playing":
                y_coords = [int(l.y * FRAME_HEIGHT) for l in lm]
                height = max(y_coords) - min(y_coords) or 1
                volumes = {
                    "vocals": compute_finger_volume(lm, 6, 8, height),
                    "guitar": compute_finger_volume(lm, 10, 12, height),
                    "drums": compute_finger_volume(lm, 14, 16, height),
                    "bass": compute_finger_volume(lm, 18, 20, height),
                }
                for name, ch in channels.items():
                    ch.set_volume(volumes[name])
                show_volume_bars(volumes)

                y = 50
                for name, vol in volumes.items():
                    cv2.putText(display_frame, f"{name}: {vol:.2f}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    y += 30

        cv2.imshow("Stem Player", display_frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        time.sleep(0.01)

    camera.stop()
    pygame.mixer.quit()
    ser.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
