import time

porcupine_awake = False
last_wake_time = 0.0
WAKE_ACTIVE_SECONDS = 180.0
_wake_callbacks = []


def register_wake_callback(callback):
    _wake_callbacks.append(callback)


def trigger_wake():
    global porcupine_awake, last_wake_time
    porcupine_awake = True
    last_wake_time = time.time()

    for callback in list(_wake_callbacks):
        try:
            callback()
        except Exception:
            pass


def consume_if_awake() -> bool:
    global porcupine_awake

    if not porcupine_awake:
        return False

    if time.time() - last_wake_time > WAKE_ACTIVE_SECONDS:
        porcupine_awake = False
        return False

    porcupine_awake = False
    return True


def sleep_now():
    global porcupine_awake
    porcupine_awake = False
