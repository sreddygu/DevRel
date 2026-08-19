#!/usr/bin/env python3
# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""AURA TTS on IQ8: text -> piper (aarch64) -> WAV (optionally played via aplay).

CPU synthesis (piper bundles its own libonnxruntime + espeak-ng). Not on the
NPU — piper is a small vocoder, not the LLM, so CPU is fine. Mirrors the
aura.speech.tts.TextToSpeech seam: synthesize(text) -> wav bytes on disk.
"""
import os, subprocess, sys
PIPER = '/opt/aura-speech/piper'
VOICE = '/opt/aura-speech/voices/en_US-lessac-medium.onnx'

def synthesize(text, out_path):
    env = dict(os.environ, LD_LIBRARY_PATH=PIPER)
    r = subprocess.run([PIPER + '/piper', '--model', VOICE, '--output_file', out_path],
                       input=text, env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, text=True)
    if r.returncode != 0:
        raise RuntimeError('piper failed')
    return out_path

def speak(text, out_path='/tmp/aura_reply.wav'):
    synthesize(text, out_path)
    # ALSA playback (arecord/aplay are present on the device).
    subprocess.run(['aplay', '-q', out_path], stderr=subprocess.DEVNULL)
    return out_path

if __name__ == '__main__':
    text = ' '.join(sys.argv[1:]) or 'AURA vision and speech are running on the IQ8.'
    out = synthesize(text, '/opt/aura-speech/reply.wav')
    print('synthesized:', out)
