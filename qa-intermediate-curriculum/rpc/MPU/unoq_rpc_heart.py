import time
from pathlib import Path
from rpc_base import ArduinoBridge

def main():
    bridge = ArduinoBridge()
    try: 
        for idx in range(10):
            print(f"Flash Heart calling MCU function -> {bridge.call('flash_heart')}")
            print(f"idx={idx}")
            time.sleep(2)
    finally:
        bridge.close()

if __name__ == "__main__":
    main()