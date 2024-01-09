import asyncio
import threading
import time
from threading import Event

from web import PerfWebSocket


class MonitorIter(object):

    def __init__(self, stop_event):
        self.stop_event: threading.Event = stop_event

    def __aiter__(self):
        return self

    def __anext__(self):
        if self.stop_event.is_set():
            future = asyncio.Future()
            future.set_result(None)
            return future
        elif not self.stop_event.is_set():
            raise StopAsyncIteration()


class Monitor(object):

    def __init__(self, func, ws, **kwargs):
        super(Monitor, self).__init__()
        self.stop_event = Event()
        self.func = func
        self.kwargs = kwargs
        self.stop_event.set()
        self.ws = ws

    async def run(self):
        async for _ in MonitorIter(self.stop_event):
            before_func = time.time()
            res = await self.func(**self.kwargs)
            self.ws.write(res)
            end_func = time.time()
            if interval_time := (int(end_func) - int(before_func)) <= 1:
                await asyncio.sleep(interval_time)

    def stop(self):
        self.stop_event.clear()
