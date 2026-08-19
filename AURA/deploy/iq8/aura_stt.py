#!/usr/bin/env python3
# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""AURA STT on IQ8: WAV -> whisper.cpp (aarch64) -> speech Event."""
import json, os, subprocess, sys
from datetime import datetime, timezone
WBIN='/opt/aura-speech/whisper-bin-ubuntu-arm64'
MODEL='/opt/aura-speech/ggml-base.en.bin'
def transcribe(wav):
    env=dict(os.environ, LD_LIBRARY_PATH=WBIN)
    r=subprocess.run([WBIN+'/whisper-cli','-m',MODEL,'-f',wav,'-nt'],
                     env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if r.returncode!=0: raise RuntimeError('whisper-cli failed')
    return r.stdout.strip()
def to_event(text):
    return {'event':text,'timestamp':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'type':'speech','entities':[],'source':'speech','confidence':None,'attributes':{}}
if __name__=='__main__':
    wav=sys.argv[1] if len(sys.argv)>1 else '/opt/aura-speech/jfk.wav'
    t=transcribe(wav); print('== Transcript =='); print(t)
    print('== Event =='); print(json.dumps(to_event(t)))
