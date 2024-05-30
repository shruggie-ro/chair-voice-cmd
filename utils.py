# coding=utf-8
import os
import subprocess
import time
import threading
import librosa
import numpy as np
import soundfile as sf
import sounddevice as sd
from collections import deque
from dtw import dtw
import logging

LOG_FORMAT = '%(asctime)-15s %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

DEVICE = sd.query_devices(kind='input')
DEVICE_NAME = DEVICE['name']

CHUNK = 4000  # Number of frames per buffer
RATE = 16000  # Sampling frequency
CHUNK_TIME = 1 / RATE * CHUNK
CHANNELS = 1  # Mono

def convert_strip(frames: [list, deque], frame_length: int = CHUNK, hop_length: int = CHUNK // 2):
    """Convert raw audio data(bytes) into integers and strip silence.

    Parameters
    ----------
    frames : list, deque
        The wave data.

    frame_length : int
        Length of analysis frame (in samples) for energy calculation.

    hop_length : int
        Hop length for grouping the wave data.

    Returns
    -------
    data : np.ndarray
        The new wave data without silence.
    """

    data = b''.join(frames)
    data = np.frombuffer(data, np.int16) / 2 ** 15
    data = strip_silence(data, frame_length, hop_length)
    # data = data.astype(np.int16)
    return data


# Not used
def find_closest(voice: 'Voice', template_voices: list, need_strip=False):
    """Finding the most similar template voice to the "voice".

    Parameters
    ----------
    voice : Voice
        Find the most similar template voice to this "voice".

    template_voices : list
        A list of Voice objects to be compared with.

    need_strip : bool
        Whether the "voice" needs to be stripped.

    Returns
    -------
    score : DTW.normalizedDistance
        The normalized DTW distance.

    closest_voice :
         The most similar template voice.
    """

    score = float('inf')
    closest_voice = None

    for t in template_voices:
        try:
            s = t.dtw_with(another=voice)
        except Exception as e:
            logger.error(e)
        else:

            if s.normalizedDistance < score:
                score = s.normalizedDistance
                closest_voice = t

    return score, closest_voice


class Listener:
    """Class for recognizing wakeup word from real-time audio data.

    Attributes
    ----------
    chunk : int
        The chunk size when receiving audio stream data.

    channels : int
        The number of channels when receiving audio stream data.

    rate : int
        The sample rate of channels when receiving audio stream data.

    window_size : int
        The size of sliding window.

    template : Voice
        The template audio file for wakeup word recognition.

    thresh : int
        The threshold when recognizing wakeup word. Set ```thresh=0``` for finding proper threshold.

    _wakeup : bool
        The flag indicating whether Petoi is waken up.

    _frame_window : deque
        The sliding window that contains 2 secs of audio data.

    _frames : deque
        A deque for storing audio data chunks during listening.
    """

    def __init__(self, template: 'Voice', chunk=CHUNK, n_channels=CHANNELS, rate=RATE, thresh=0):
        self.chunk = chunk
        self.channels = n_channels
        self.rate = rate
        self.window_size = int(2 / CHUNK_TIME)
        self.template = template
        self.thresh = thresh  # Set 0 For finding proper thresh
        self._wakeup = False
        self._frame_window = deque([], maxlen=self.window_size)
        #
        self._frames = deque([], maxlen=int(5 / CHUNK_TIME))
        logger.debug(f'Listener Wake-up word template：{self.template.file_path}')

    def listening(self):
        """The function for recognizing wakeup word from real-time audio data.

        Returns
        -------
        result : dtw.DTW
            The DTW object that contains results of dtw(distance) calculation.
        """

        result = ''
        self.reset()
        stream = sd.RawInputStream(samplerate=self.rate, device=DEVICE_NAME, blocksize=self.chunk,
                                   channels=1, dtype='int16')
        stream.start()

        while not self._wakeup:
            data = stream.read(self.chunk)
            self._frames.append(data[0])

            if len(self._frames) > self.window_size:
                # print('start')
                if self._frame_window:
                    count = self.window_size // 2
                    # pop half of the data in sliding window
                    for i in range(count):
                        self._frame_window.popleft()
                    # then insert new audio data to be recognized
                    for i in range(count):
                        self._frame_window.append(self._frames.popleft())
                else:
                    # when sliding window is not full and there are existing cached frames,
                    # add the cached frames into the sliding window.
                    while len(self._frame_window) < self.window_size and len(self._frames) > 0:
                        self._frame_window.append(self._frames.popleft())
                signal = convert_strip(self._frame_window, self.chunk, self.chunk // 2)
                # for now signal is a float ndarray
                v = Voice(signal)
                s = time.time()
                result = v.dtw_with(self.template)
                logger.debug(f'len(_frames)={len(self._frames)}, DTW time cost: {time.time()-s}s, '
                             f'DTW.normalizedDistance={result.normalizedDistance}')
                if result.normalizedDistance < self.thresh:
                    logger.info('WakeUp')
                    self.wakeup()

        stream.stop()
        stream.close()
        logger.info("End monitoring")
        return result

    def wakeup(self):
        self._wakeup = True

    def is_wakeup(self):
        return self._wakeup

    def reset(self):
        self._wakeup = False
        self._frames.clear()
        self._frame_window.clear()

class Voice:
    """Class for storing and manipulating wave data.

    Attributes
    ----------
    file_path : str
        The file path of the wav file that is loaded into Voice object.

    mfcc : np.ndarray
        Sequence of mfcc feature of the wave data.

    wave_data : np.ndarray
        The wave data.

    sample_rate : int
        The rate of the wave data/file.
    """

    def __init__(self, path_or_data):
        """Constructor of class Voice.

        If the constructor get an str, that means it gets the path to the wav file.
        If the constructor get (list, np.ndarray, bytes), that means it gets the wave
        data in the memory.

        Parameters
        ----------
        path_or_data : str, list, np.ndarray, bytes
        """

        if isinstance(path_or_data, str):
            self.file_path = None
            self.mfcc = None
            self.__load_data(path_or_data)
        elif isinstance(path_or_data, (list, np.ndarray, bytes)):
            logger.debug("Voice's constructor got audio data")
            self.file_path = None
            self.mfcc = None
            self.wave_data = path_or_data
            self.sample_rate = RATE

    def __load_data(self, file_path: str):
        """Load wave data from a file.

        Parameters
        ----------
        file_path : str
            Path of a wave file.

        Returns
        -------
        True if the process is successful.

        Raises
        ------
        Exception
        """

        try:
            self.wave_data, self.sample_rate = librosa.load(file_path, sr=RATE)
            self.n_frames = len(self.wave_data)
            self.file_path = file_path
            self.name = os.path.basename(file_path)  # Record the file name
            return True
        except Exception as e:
            raise e

    def dtw_with(self, another: 'Voice'):
        """Calculate and return the DTW distance between self and another(Voice).

        Parameters
        ----------
        another : Voice
             Another Voice object to be calculated DTW distance with.

        Returns
        -------
        An object of class ``DTW``.
        """

        return dtw(another.get_mfcc().T, self.get_mfcc().T, dist_method='euclidean')

    def get_mfcc(self):
        """Calculate and cache the mfcc sequence of the wave data.

        Returns
        -------
        mfcc : np.ndarray [shape=(n_mfcc, t)]
            MFCC sequence
        """

        if self.mfcc is None:
            self.mfcc = librosa.feature.mfcc(y=self.wave_data, sr=self.sample_rate, n_mfcc=20)
        return self.mfcc

    def play(self):
        """Play the loaded wave data as sound.
        """

        # sounddevice needs int16 while librosa uses float
        data = self.wave_data * 2**15
        data = data.astype(np.int16)
        sd.play(data, self.sample_rate)
        sd.wait()
