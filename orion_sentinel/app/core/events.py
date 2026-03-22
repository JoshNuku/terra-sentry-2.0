import queue

_event_queue = queue.Queue()

def emit(event):
    _event_queue.put(event)

def listen():
    return _event_queue.get()
