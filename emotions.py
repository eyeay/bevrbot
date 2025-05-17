import cv2
import numpy as np
import time
import mediapipe as mp
from picamera2 import Picamera2
from tensorflow.keras.models import load_model
from gtts import gTTS
import os
from animations import set_expression

model = load_model('/home/eyeay/Downloads/fer2013_mini_XCEPTION.102-0.66.hdf5', compile=False)
emotion_labels = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
valid_emotions = ['happy', 'sad', 'fear']

mp_face = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.6)

picam2 = Picamera2()
picam2.preview_configuration.main.size = (640, 480)
picam2.preview_configuration.main.format = "RGB888"
picam2.configure("preview")
picam2.start()

current_state = None
state_start_time = None
mood_mode = "neutral"

set_expression("neutral")

def speak(text):
    tts = gTTS(text=text, lang='en', tld='co.uk')
    tts.save("/tmp/emotion.mp3")
    os.system("mpg123 /tmp/emotion.mp3")

while True:
    frame = picam2.capture_array()
    rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
    display_frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    result = mp_face.process(rgb)
    detected_emotion = None

    if result.detections:
        for detection in result.detections:
            bbox = detection.location_data.relative_bounding_box
            h, w, _ = rgb.shape
            x1 = max(int(bbox.xmin * w), 0)
            y1 = max(int(bbox.ymin * h), 0)
            x2 = min(int((bbox.xmin + bbox.width) * w), w)
            y2 = min(int((bbox.ymin + bbox.height) * h), h)

            face = rgb[y1:y2, x1:x2]
            try:
                face_resized = cv2.resize(face, (64, 64))
                gray_face = cv2.cvtColor(face_resized, cv2.COLOR_RGB2GRAY)

                input_data = np.expand_dims(gray_face, axis=0)
                input_data = np.expand_dims(input_data, axis=-1)
                input_data = input_data / 255.0

                predictions = model.predict(input_data, verbose=0)
                raw_emotion = emotion_labels[np.argmax(predictions)]

                if raw_emotion not in valid_emotions:
                    continue

                detected_emotion = "sad" if raw_emotion in ["sad", "fear"] else "happy"

                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                cv2.putText(display_frame, f"{detected_emotion}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            except Exception as e:
                print("Face processing error:", e)

    now = time.time()
    if detected_emotion != current_state:
        current_state = detected_emotion
        state_start_time = now
    elif detected_emotion and (now - state_start_time) >= 0.75:
        if detected_emotion == "sad" and mood_mode == "neutral":
            speak("Smile and cheer up!")
            set_expression("happy")
            mood_mode = "prompted"

        elif detected_emotion == "happy" and mood_mode == "prompted":
            speak("That's much better!")
            set_expression("neutral")
            mood_mode = "neutral"

        elif detected_emotion == "happy" and mood_mode == "neutral":
            speak("You seem happy, keep it up")
            set_expression("happy")
            time.sleep(1)
            set_expression("neutral")

    cv2.imshow("Emotion Response", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
