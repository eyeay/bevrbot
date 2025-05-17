from picamera2 import Picamera2
import cv2
import numpy as np
import time
from gtts import gTTS
import uuid
import os
import speech_recognition as sr
import subprocess
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas

serial = i2c(port=1, address=0x3D)
device = ssd1306(serial)

def draw_expression(draw, expression, width=14, height=50):
    radius = 4
    top_margin = (64 - height) // 2
    left_center_x = 26 + 7
    right_center_x = 88 + 7

    def eye_shape(x, y, w, h):
        draw.pieslice((x, y, x + w, y + 2 * radius), 180, 360, fill=255)
        draw.pieslice((x, y + h - 2 * radius, x + w, y + h), 0, 180, fill=255)
        draw.rectangle((x, y + radius, x + w, y + h - radius), fill=255)

    if expression == "neutral":
        for cx in [left_center_x, right_center_x]:
            eye_shape(cx - width // 2, top_margin, width, height)
    elif expression == "happy":
        eye_size = 14
        top = 20
        outer_height = eye_size
        inner_offset = 6
        for cx in [left_center_x, right_center_x]:
            outer = [(cx - eye_size, top + outer_height), (cx, top), (cx + eye_size, top + outer_height)]
            draw.polygon(outer, fill=255)
            inner = [(cx - eye_size + inner_offset, top + outer_height), (cx, top + inner_offset + 4), (cx + eye_size - inner_offset, top + outer_height)]
            draw.polygon(inner, fill=0)
    elif expression == "sad":
        eye_size = 14
        top = 34
        outer_height = eye_size
        inner_offset = 6
        for cx in [left_center_x, right_center_x]:
            outer = [(cx - eye_size, top), (cx, top + outer_height), (cx + eye_size, top)]
            draw.polygon(outer, fill=255)
            inner = [(cx - eye_size + inner_offset, top), (cx, top + outer_height - (inner_offset + 4)), (cx + eye_size - inner_offset, top)]
            draw.polygon(inner, fill=0)

def animate_neutral_to(device, target_expression):
    for h in [50, 40, 30, 20, 10]:
        with canvas(device) as draw:
            draw_expression(draw, "neutral", height=h)
        time.sleep(0.04)
    with canvas(device) as draw:
        draw_expression(draw, target_expression)

recognizer = sr.Recognizer()
mic = sr.Microphone(device_index=2)

def speak(text):
    print("🤖", text)
    tts = gTTS(text=text, lang='en', tld='co.uk')
    filename = f"/tmp/{uuid.uuid4()}.mp3"
    tts.save(filename)
    os.system(f"mpg123 -q {filename}")
    os.remove(filename)

def listen():
    with mic as source:
        print("Listening...")
        recognizer.energy_threshold = 250
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            print("Processing...")
            return recognizer.recognize_google(audio).lower()
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            speak("Speech service is down.")
            return None

def detect_shape(contour):
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
    sides = len(approx)
    if sides == 3:
        return "triangle"
    elif sides == 4:
        (x, y, w, h) = cv2.boundingRect(approx)
        if 0.95 <= w / float(h) <= 1.05:
            return "square"
    elif 8 <= sides <= 12:
        return "star"
    elif sides > 6:
        area = cv2.contourArea(contour)
        if area == 0:
            return None
        circularity = 4 * np.pi * (area / (peri * peri))
        if 0.7 < circularity < 1.2:
            return "circle"
    return None

camera = Picamera2()
camera.configure(camera.create_still_configuration(main={"size": (640, 480)}))
camera.start()
time.sleep(1)

while True:
    animate_neutral_to(device, "neutral")
    speak("Please show me a shape.")
    confirmed_shape = None
    current_shape = None
    shape_start_time = None

    while not confirmed_shape:
        frame = camera.capture_array("main")
        frame = cv2.flip(frame, 1)
        display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(display_frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (90, 80, 50), (130, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_shape = None
        for contour in contours:
            if cv2.contourArea(contour) < 500:
                continue
            shape = detect_shape(contour)
            if shape:
                detected_shape = shape
                break

        if detected_shape:
            if detected_shape == current_shape:
                if shape_start_time and (time.time() - shape_start_time >= 0.5):
                    confirmed_shape = detected_shape
            else:
                current_shape = detected_shape
                shape_start_time = time.time()
        else:
            current_shape = None
            shape_start_time = None

        cv2.imshow("Shape Detection", display_frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            camera.stop()
            cv2.destroyAllWindows()
            exit()

    speak("Do you know what shape this is?")
    while True:
        answer = listen()
        if not answer:
            speak("Can you say the shape again?")
            continue
        if "menu" in answer:
            speak("Opening menu.")
            camera.stop()
            cv2.destroyAllWindows()
            subprocess.Popen(["python3", "/home/eyeay/app_menu.py"])
            exit()
        if confirmed_shape in answer:
            animate_neutral_to(device, "happy")
            speak("Well done!")
        else:
            animate_neutral_to(device, "sad")
            speak(f"Nice try, but that's actually a {confirmed_shape}.")
        break

    time.sleep(2)
