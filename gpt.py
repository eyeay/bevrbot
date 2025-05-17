import os
import speech_recognition as sr
from openai import OpenAI
from gtts import gTTS
from playsound import playsound
import uuid
import subprocess
from animations import set_expression

MODEL = "gpt-4o"
client = OpenAI(api_key="API KEY GOES HERE")
recognizer = sr.Recognizer()
mic = sr.Microphone(device_index=2)

conversation = [
    {"role": "system", "content": "You are a helpful and friendly assistant built into a small robot. You sound like a child and keep responses short and cheerful. Do not use emojis in your answers"}
]

def speak(text):
    print("Robot:", text)
    set_expression("happy")
    tts = gTTS(text=text, lang='en', tld='co.uk')
    filename = f"/tmp/{uuid.uuid4()}.mp3"
    tts.save(filename)
    playsound(filename)
    os.remove(filename)
    set_expression("neutral")

def listen():
    with mic as source:
        print("Listening...")
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
            speak("Sorry, I couldn't understand that.")
            return None
        except sr.RequestError:
            speak("Speech service is down.")
            return None

def chat_with_gpt(prompt):
    conversation.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=MODEL,
        messages=conversation
    )
    reply = response.choices[0].message.content
    conversation.append({"role": "assistant", "content": reply})
    return reply

def launch_menu():
    speak("Opening the menu!")
    subprocess.run(["python3", "/home/eyeay/app_menu.py"])

if __name__ == "__main__":
    set_expression("neutral")
    speak("Hello! I'm ready to chat.")

    while True:
        user_input = listen()
        if not user_input:
            continue

        user_input_lower = user_input.lower()

        if any(word in user_input_lower for word in ["exit", "quit", "goodbye", "bye"]):
            speak("Goodbye! See you later!")
            break

        if "menu" in user_input_lower:
            launch_menu()
            break

        response = chat_with_gpt(user_input)
        speak(response)
