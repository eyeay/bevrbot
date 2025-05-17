import random
import speech_recognition as sr
from gtts import gTTS
import uuid
import os
import subprocess
from animations import set_expression

recognizer = sr.Recognizer()
mic = sr.Microphone(device_index=2)

def speak(text):
    print("Buddy:", text)
    set_expression("happy")
    tts = gTTS(text=text, lang='en', tld='co.uk')
    filename = f"/tmp/{uuid.uuid4()}.mp3"
    tts.save(filename)
    os.system(f"mpg123 -q {filename}")
    os.remove(filename)
    set_expression("neutral")

def listen():
    with mic as source:
        print("🎤 Listening...")
        recognizer.energy_threshold = 250
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            print("Processing...")
            return recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            speak("I didn't hear anything.")
            return None
        except sr.UnknownValueError:
            speak("What was that, buddy?")
            return None
        except sr.RequestError:
            speak("Speech service is down, buddy.")
            return None

def is_question(text):
    question_words = ("who", "what", "when", "where", "why", "how")
    return "?" in text or text.strip().lower().startswith(question_words)

def launch_menu():
    speak("Opening the menu!")
    subprocess.run(["python3", "/home/eyeay/app_menu.py"])

def buddy_mode():
    set_expression("neutral")
    speak("Buddy mode activated. Ask me anything.")

    while True:
        user_input = listen()
        if user_input is None:
            continue

        lower_input = user_input.lower()

        if lower_input in ["exit", "quit", "goodbye", "bye"]:
            speak("Later, buddy.")
            break

        if "menu" in lower_input:
            launch_menu()
            break

        if is_question(lower_input):
            response = random.choice(["Alright buddy.", "Who asked, buddy?"])
        else:
            response = "That ain't even a question, buddy."

        speak(response)

if __name__ == "__main__":
    buddy_mode()
