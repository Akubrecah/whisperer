import threading
import queue
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from gi.repository import GLib

class WhisperRecorder:
    """
    Handles audio streaming and live transcription using faster-whisper.
    """
    def __init__(self, model_size="tiny", callback=None):
        self.model_size = model_size
        self.callback = callback # Function to call with live text
        self.recording = False
        self.audio_queue = queue.Queue()
        self.model = None
        self.current_transcript = ""
        self.stream = None

    def start(self):
        if self.recording: return
        self.recording = True
        self.current_transcript = ""
        while not self.audio_queue.empty(): self.audio_queue.get()
        
        self.stream = sd.InputStream(samplerate=16000, channels=1, callback=self._audio_callback)
        self.stream.start()
        threading.Thread(target=self._transcription_worker, daemon=True).start()

    def stop(self):
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _audio_callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_queue.put(indata.copy().flatten())

    def _transcription_worker(self):
        try:
            if self.model is None:
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            
            audio_buffer = np.array([], dtype=np.float32)
            while self.recording:
                chunks = []
                start = time.time()
                while time.time() - start < 0.6:
                    try:
                        chunks.append(self.audio_queue.get(timeout=0.1))
                    except queue.Empty:
                        continue
                
                if not chunks: continue
                
                audio_buffer = np.concatenate([audio_buffer] + chunks)
                # Keep buffer manageable (last 15 seconds)
                if len(audio_buffer) > 16000 * 15:
                    audio_buffer = audio_buffer[-(16000 * 15):]
                
                segments, _ = self.model.transcribe(audio_buffer, beam_size=1)
                text = " ".join([s.text for s in segments]).strip()
                self.current_transcript = text
                
                if self.callback:
                    GLib.idle_add(self.callback, text)
        except Exception as e:
            print(f"Transcription Error: {e}")
