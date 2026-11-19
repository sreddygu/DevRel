import socket # https://docs.python.org/3/library/socket.html
import threading
import time

import msgpack

REQUEST = 0
RESPONSE = 1
NOTIFY = 2
REGISTER = "$/register"
ROUTER_SOCKET = "/var/run/arduino-router.sock"


class ArduinoBridge:
    def __init__(self, socket_path=ROUTER_SOCKET):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(socket_path)
        self.sock.setblocking(True)

        self.lock = threading.Lock()
        self.msgid = 0
        self.pending = {}
        self.handlers = {}
        self.unpacker = msgpack.Unpacker(raw=False)
        self.running = True

        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

    def _next_msgid(self):
        with self.lock:
            self.msgid += 1
            return self.msgid

    def _send(self, message):
        self.sock.send(msgpack.packb(message, use_bin_type=True))

    def _recv_loop(self):
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.unpacker.feed(data)
                for message in self.unpacker:
                    self._handle_message(message)
            except OSError:
                break

    def _handle_message(self, message):
        if not isinstance(message, list) or not message:
            return

        kind = message[0]
        if kind == RESPONSE and len(message) >= 4:
            self.pending[message[1]] = (message[2], message[3])
            return

        if kind == REQUEST and len(message) >= 4:
            _, msgid, method, params = message
            handler = self.handlers.get(method)
            if handler is None:
                self._send([RESPONSE, msgid, f"no handler for {method}", None])
                return

            try:
                result = handler(*params)
                self._send([RESPONSE, msgid, None, result])
            except Exception as exc:
                self._send([RESPONSE, msgid, str(exc), None])
            return

        if kind == NOTIFY and len(message) >= 3:
            _, method, params = message
            handler = self.handlers.get(method)
            if handler is None:
                return
            try:
                handler(*params)
            except Exception as exc:
                print(f"notify handler '{method}' failed: {exc}")

    def call(self, method, *params, timeout=5):
        msgid = self._next_msgid()
        self.pending[msgid] = None
        self._send([REQUEST, msgid, method, list(params)])

        started = time.time()
        while time.time() - started < timeout:
            response = self.pending.get(msgid)
            if response is not None:
                del self.pending[msgid]
                error, result = response
                if error:
                    raise RuntimeError(error)
                return result
            time.sleep(0.01)

        del self.pending[msgid]
        raise TimeoutError(f"Timed out waiting for '{method}'")

    def notify(self, method, *params):
        self._send([NOTIFY, method, list(params)])

    def provide(self, method, handler, timeout=5):
        self.handlers[method] = handler
        self.call(REGISTER, method, timeout=timeout)

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


def test_linux_mul(a, b):
    print(f"linux_mul({a}, {b})")
    return a * b


def test_linux_log(value):
    print(f"linux_log({value})")


def main():
    bridge = ArduinoBridge()
    try:
        bridge.provide("linux_mul", test_linux_mul)
        bridge.provide("linux_log", test_linux_log)
        print("Linux handlers registered: linux_mul, linux_log")

        time.sleep(1.0)

        print(f"mcu_ping() -> {bridge.call('mcu_ping')}")
        print(f"mcu_add(2, 3) -> {bridge.call('mcu_add', 2, 3)}")
        bridge.notify("mcu_ping")
        print("notify('mcu_ping') sent")

        print("Waiting 5 seconds for MCU -> Linux calls...")
        time.sleep(5.0)
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
