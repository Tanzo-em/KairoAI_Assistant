import time

porcupine_awake = False
last_wake_time = 0.0
WAKE_ACTIVE_SECONDS = 30.0


def trigger_wake():
    global porcupine_awake, last_wake_time
    porcupine_awake = True
    last_wake_time = time.time()


def consume_if_awake() -> bool:
    global porcupine_awake

    if not porcupine_awake:
        return False

    if time.time() - last_wake_time > WAKE_ACTIVE_SECONDS:
        porcupine_awake = False
        return False

    return True


def sleep_now():
    global porcupine_awake
    porcupine_awake = False