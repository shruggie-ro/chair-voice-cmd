import logging
import subprocess
import time
from threading import Thread, Event, Condition

import os
from dotenv import load_dotenv
import google.generativeai as genai
import pyaudio
import pyttsx3
import sounddevice as sd
import speech_recognition as sr
import vosk
from importlib import import_module
from pydub import AudioSegment
from pydub.playback import play
from vosk_microphone_pi import action_listen, load_model
import PiRelay

# Setup logging
FORMAT = '%(asctime)-15s %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger(__name__)

# Festival TTS function
def speak_text(text):
    """Speaks the given text using Festival."""
    command = ["festival", "--language", "american_english", "--tts", "-"]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    process.stdin.write(text.encode('utf-8'))
    process.stdin.close()
    process.wait()

# Example usage
speak_text("Hello! Your interactive chair is booting!")

def log_and_speak(message):
    speak_text(message)
    logger.debug(message)

class cmd_handler:
    def __init__(self):
        self.command_mode = False
        self.cv = Condition()
        self.running = True
        self.cmd_name = "none"
        self.stop_event = Event()
        self.speech_active = False
        self.thrd = Thread(target=cmd_handler_task, args=(self,))
        self.thrd.start()

    def execute(self, cmd):
        if cmd == "check_internet":
            self.check_internet()
        elif cmd == "stop":
            self.stop_command()
        elif cmd in ["hey_chair_recliner_up", "hey_chair_recliner_down", "hey_chair"]:
            self.handle_chair_commands(cmd)
        elif cmd == "hey_bird":
            if not self.speech_active:
                self.handle_hey_bird()
        elif not self.command_mode:
            return
        else:
            self.handle_command_mode(cmd)

    def check_internet(self):
        self.command_mode = True
        self.command_mode_start_time = time.time()
        try:
            completed_process = subprocess.run(['ping', '-c', '1', 'google.com'], capture_output=True)
            if completed_process.returncode == 0:
                log_and_speak("Internet connection available")
            else:
                log_and_speak("No internet connection")
        except subprocess.CalledProcessError:
            log_and_speak("Error pinging to check internet connection")

    def stop_command(self):
        self.command_mode = False
        self.cmd_name = "stop"
        self.stop_event.set()
        log_and_speak("Stopping")

    def handle_chair_commands(self, cmd):
        self.command_mode = True
        self.command_mode_start_time = time.time()
        if cmd == "hey_chair_recliner_up":
            self.cmd_name = "recliner_up"
        elif cmd == "hey_chair_recliner_down":
            self.cmd_name = "recliner_down"
        elif cmd == "hey_chair":
            logger.debug("Entering command mode")

    def handle_hey_bird(self):
        self.command_mode = True
        self.speech_active = True
        self.stop_event.clear()
        engine = pyttsx3.init()
        recognizer = sr.Recognizer()
        text_to_speak = "I am listening you..."
        log_and_speak(text_to_speak)

        with sr.Microphone() as source:
            audio_data = recognizer.listen(source)
            self.command_mode_start_time = time.time()

        try:
            text = recognizer.recognize_google(audio_data)
            print(f"You said: {text}")
        except sr.UnknownValueError:
            text = "Sorry, I couldn't understand that"
            log_and_speak(text)
        except sr.RequestError as e:
            text = f"Could not request results from Google Speech Recognition service; {e}"
            log_and_speak(text)

        self.generate_and_speak_response(engine, text)

    def generate_and_speak_response(self, engine, text):
        self.command_mode = True
        p = pyaudio.PyAudio()
        device = sd.query_devices(kind='output')
        device_index = device['index']
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True, output_device_index=device_index)

        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
        response = model.generate_content([text])
        print(response.text)

        self.command_mode_start_time = time.time()

        def run_speech():
            engine.connect('started-word', on_word)
            engine.say(response.text)
            engine.runAndWait()
            self.stop_event.set()
            self.speech_active = False

        def on_word(name, location, length):
            if self.stop_event.is_set():
                engine.stop()

        speech_thread = Thread(target=run_speech)
        speech_thread.start()

        def listen_for_stop():
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                while not self.stop_event.is_set():
                    try:
                        audio_data = recognizer.listen(source, timeout=1, phrase_time_limit=2)
                        stop_text = recognizer.recognize_google(audio_data).lower()
                        if "stop" in stop_text:
                            self.stop_event.set()
                            engine.stop()
                            print("Speech stopped by user command.")
                            break
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as e:
                        print(f"Could not request results from Google Speech Recognition service; {e}")
                        break
                    except sr.WaitTimeoutError:
                        continue

        stop_thread = Thread(target=listen_for_stop)
        stop_thread.start()
        speech_thread.join()
        stop_thread.join()
        if stream.is_active():
            stream.stop_stream()
        stream.close()
        p.terminate()

    def handle_command_mode(self, cmd):
        now = time.time()
        if now - self.command_mode_start_time > 10:
            self.command_mode = False
            self.cmd_name = "none"
            logger.debug("Command mode time has expired")
        elif cmd in ["recliner_up", "recliner_down"]:
            self.cmd_name = cmd
            self.command_mode = False

def cmd_handler_task(cmd_hnd):
    relay1 = PiRelay.Relay("RELAY1")
    relay2 = PiRelay.Relay("RELAY2")

    while cmd_hnd.running:
        relay1.off()
        relay2.off()

        if cmd_hnd.cmd_name == "recliner_down":
            for _ in range(1, 10):
                if cmd_hnd.cmd_name == "recliner_down":
                    relay1.on()
                    time.sleep(1)
            cmd_hnd.cmd_name = "none"
        elif cmd_hnd.cmd_name == "recliner_up":
            for _ in range(1, 10):
                if cmd_hnd.cmd_name == "recliner_up":
                    relay2.on()
                    time.sleep(1)
            cmd_hnd.cmd_name = "none"

        time.sleep(1)

def load_config(path: str = './config/config.yml'):
    import yaml
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.load(f, Loader=yaml.FullLoader)
    except FileNotFoundError as e:
        logger.error(f'config file not exists: {path}')
        raise e

def task_action(cmd_handler, model, sample_rate, cmd_table, d, chunk):
    logger.info("Start act")
    action_listen(cmd_handler=cmd_handler, model=model, sample_rate=sample_rate, cmd_table=cmd_table, d=d, chunk=chunk)

def main_loop(cmd_handler, mode=0):
    table_pkg = import_module(configs['cmd_table']['package'])
    cmd_table = getattr(table_pkg, configs['cmd_table']['table_name'])
    build_dict = getattr(table_pkg, configs['cmd_table']['build_dict'])

    vosk_chunk = 20
    sample_rate = 16000

    d = build_dict(cmd_table)
    model = load_model(model=configs['vosk_model_path'])

    while True:
        task_action(cmd_handler=cmd_handler, model=model, sample_rate=sample_rate, cmd_table=cmd_table, d=d, chunk=vosk_chunk)

configs = load_config('./config/config.yml')

try:
    main_loop(cmd_handler(), mode=1)
except KeyboardInterrupt:
    print('\nDone, exit')
    exit(0)
