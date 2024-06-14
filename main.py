import logging
import utils
from importlib import import_module
import vosk
from vosk_microphone_pi import action_listen, load_model
import time

from threading import Thread
from threading import Condition
import PiRelay

FORMAT = '%(asctime)-15s %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)
logger = logging.getLogger(__name__)

def cmd_handler_task(cmd_hnd):
    relay1 = PiRelay.Relay("RELAY1")
    relay2 = PiRelay.Relay("RELAY2")

    while (cmd_hnd.running):
        relay1.off()
        relay2.off()

        if (cmd_hnd.cmd_name == "recliner_down"):
            for _ in range(1, 10):
                if (cmd_hnd.cmd_name == "recliner_down"):
                    logger.debug("down down down")
                    relay1.on()
                    time.sleep(1)
            # Continue from the start of the loop
            continue

        if (cmd_hnd.cmd_name == "recliner_up"):
            for _ in range(1, 10):
                if (cmd_hnd.cmd_name == "recliner_up"):
                    relay2.on()
                    logger.debug("up up up")
                    time.sleep(1)
            # Continue from the start of the loop
            continue
        #with (cmd_hnd.cv):
        #    cmd_hnd.cv.wait()
        #    print("running " + cmd_hnd.cmd_name)
        time.sleep(1)

class cmd_handler:

    def __init__(self):
        self.command_mode = False
        self.cv = Condition()
        self.running = True
        self.thrd = Thread(target = cmd_handler_task, args = (self, ))
        self.cmd_name = "none"
        self.thrd.start()

    def execute(self, cmd):
        if (cmd == "hey_chair_recliner_up"):
            self.command_mode = True
            self.command_mode_start_time = time.time()
            logger.debug("Entering command mode - Recliner up")
            self.cmd_name = "recliner_up"
            return

        if (cmd == "hey_chair_recliner_down"):
            self.command_mode = True
            self.command_mode_start_time = time.time()
            logger.debug("Entering command mode - Recliner down")
            self.cmd_name = "recliner_down"
            return

        if (cmd == "hey_chair"):
            self.command_mode = True
            self.command_mode_start_time = time.time()
            logger.debug("Entering command mode")
            return

        if (not self.command_mode):
            return

        now = time.time()
        if (now - self.command_mode_start_time > 10):
            logger.debug("Command mode time has expired")
            self.command_mode = False
            self.cmd_name = "none"
            return

        if (cmd == "recliner_up"):
            logger.debug("Recliner raising")
            self.command_mode = False
            self.cmd_name = cmd
            #self.cv.notify()
            return

        if (cmd == "recliner_down"):
            logger.debug("Recliner lowering")
            self.command_mode = False
            self.cmd_name = cmd
            #self.cv.notify()
            return

def load_config(path: str = './config/config.yml'):
    import yaml
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        # print(config)
    except FileNotFoundError as e:
        logger.error(f'config file not exists: {path}')
        raise e
    else:
        return config

def task_action(cmd_handler, model, sample_rate, cmd_table, d, chunk):
    """The function for receiving, recognizing and executing the voice commands.

    Parameters
    ----------
    ser : serial.Serial
        The serial port of Petoi.

    model : vosk.Model
        The loaded vosk model for speech recognition.

    sample_rate : int
        The sample rate when receiving audio data.

    cmd_table : dict{ str:str }
        Key represents the result of speech recognition(voice command).
        Value represents the corresponding Petoi command.

    d : str
        A customized dictionary indicating the range of words to be recognized.

    chunk : int
        The chunk size of the audio stream data.
    """

    logger.info("Start act")
    action_listen(cmd_handler=cmd_handler, model=model, sample_rate=sample_rate, cmd_table=cmd_table, d=d, chunk=chunk)


def main_loop(cmd_handler, mode=0):
    """The loop for waking up Petoi and sending voice commands.

    Parameters
    ----------
    mode : int
        0 if you want to begin with wakeup recognition.
        1 if you want to begin with command recognition.
    """

    table_pkg = import_module(configs['cmd_table']['package'])
    cmd_table = getattr(table_pkg, configs['cmd_table']['table_name'])
    build_dict = getattr(table_pkg, configs['cmd_table']['build_dict'])

    # Chunk size of audio stream data for vosk recognizer.
    vosk_chunk = 20
    # The rate of audio stream data for vosk recognizer.
    sample_rate = 16000

    # Initialize vosk model for speech recognition.
    d = build_dict(cmd_table)
    model = load_model(model=configs['vosk_model_path'])

    while True:
        logger.debug(f'mode={mode}, action_listen')
        task_action(cmd_handler=cmd_handler, model=model, sample_rate=sample_rate, cmd_table=cmd_table, d=d, chunk=vosk_chunk)

configs = load_config('./config/config.yml')

try:
    main_loop(cmd_handler(), mode=1)
except KeyboardInterrupt:
    print('\nDone, exit')
    exit(0)
