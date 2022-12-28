import asyncio
from asyncio import Queue


class RoborockQueue(Queue):

    def __init__(self, *args):
        super().__init__(*args)

    async def async_put(self, item, timeout):
        return await asyncio.wait_for(self.put(item), timeout=timeout)

    async def async_get(self, timeout):
        return await asyncio.wait_for(self.get(), timeout=timeout)
