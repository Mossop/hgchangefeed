HTTP_THREADS = 40

import urllib2
from threading import Thread, Lock, Condition
from Queue import Queue

def http_fetch(url):
    while True:
        try:
            response = urllib2.urlopen(url)
            return response.read()
        except:
            pass

class HttpQueue(object):
    fetch_queue = None
    response_queue = None
    lock = None
    pending_count = None

    def __init__(self):
        self.fetch_queue = Queue()
        self.response_queue = Queue()
        self.lock = Lock()
        self.pending_count = 0

        for i in range(HTTP_THREADS):
             t = Thread(target = self.worker)
             t.daemon = True
             t.start()

    def worker(self):
        while True:
            (url, context) = self.fetch_queue.get(True)

            data = http_fetch(url)

            self.response_queue.put((data, context))

            self.lock.acquire()
            self.pending_count = self.pending_count - 1
            self.lock.release()

    def fetch(self, url, context = None):
        self.lock.acquire()
        self.pending_count = self.pending_count + 1
        self.lock.release()

        self.fetch_queue.put((url, context))

    def next(self):
        self.lock.acquire()
        try:
            if self.pending_count == 0 and self.response_queue.empty():
                return (None, None)
        finally:
            self.lock.release()

        return self.response_queue.get(True)


class OrderedHttpQueue(object):
    fetch_list = None
    response_list = None
    lock = None
    next_response = None
    next_fetch = None

    def __init__(self):
        self.lock = Condition()
        self.reset()

        for i in range(HTTP_THREADS):
             t = Thread(target = self.worker)
             t.daemon = True
             t.start()

    def reset(self):
        self.fetch_list = []
        self.response_list = []
        self.next_fetch = 0
        self.next_response = 0

    def get_next_fetch(self):
        self.lock.acquire()
        try:
            while self.next_fetch >= len(self.fetch_list):
                self.lock.wait()

            id = self.next_fetch
            (url, context) = self.fetch_list[id]
            self.fetch_list[id] = None
            self.next_fetch = self.next_fetch + 1
            return (id, url, context)
        finally:
            self.lock.release()

    def worker(self):
        while True:
            (id, url, context) = self.get_next_fetch()

            data = http_fetch(url)

            self.lock.acquire()
            self.response_list[id] = (data, context)
            self.lock.notifyAll()
            self.lock.release()

    def fetch(self, url, context = None):
        self.lock.acquire()
        self.fetch_list.append((url, context))
        self.response_list.append(None)
        self.lock.notifyAll()
        self.lock.release()

    def next(self):
        self.lock.acquire()
        try:
            if self.next_response >= len(self.response_list):
                self.reset()
                return (None, None)

            while True:
                result = self.response_list[self.next_response]
                if result:
                    self.response_list[self.next_response] = None
                    self.next_response = self.next_response + 1
                    return result
                self.lock.wait()
        finally:
            self.lock.release()
