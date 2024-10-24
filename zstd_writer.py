import asyncio
from io import BufferedReader, BytesIO
import zstandard as zstd

class ZstdFrameWriter:
    def __init__(self, raw_writer: asyncio.StreamWriter, skip_packets=0):
        self.compressor = zstd.ZstdCompressor()
        self.raw_writer = raw_writer
        self.skip_packets = skip_packets

    async def drain(self):
        await self.raw_writer.drain()

    def close(self):
        self.raw_writer.close()
        self.compressor = None

    def write(self, data):

        if self.skip_packets > 0:
            self.skip_packets -= 1
            self.raw_writer.write(data)
            return

        self.raw_writer.write(self.compressor.compress(data))