"""Local development test: no OpenAI connection and no recorded audio.

Sends a synthetic test tone, not a generated NPC response. Set the same random
REFLECTIONS_VOICE_LOCAL_TOKEN in the relay and Unreal process environments.
"""
import asyncio
import base64
import json
import math
import os
import struct

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from relay import VoiceRelay


async def main():
    async def fake_upstream(ws):
        await ws.send(json.dumps({"type": "session.created"}))
        await ws.recv()
        await ws.send(json.dumps({"type": "session.updated"}))
        bytes_received = 0
        async for raw in ws:
            event = json.loads(raw)
            if event.get("type") == "input_audio_buffer.append":
                bytes_received += len(base64.b64decode(event["audio"]))
            if event.get("type") == "response.create":
                print(f"MOCK: received {bytes_received} audio bytes; returning test tone", flush=True)
                # A clearly synthetic 0.5-second quiet tone; no speech is stored.
                pcm = b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / 24000))) for i in range(12000))
                await ws.send(json.dumps({"type": "response.output_audio.delta", "delta": base64.b64encode(pcm).decode()}))
                await ws.send(json.dumps({"type": "response.done"}))
                bytes_received = 0

    async with serve(fake_upstream, "127.0.0.1", 0) as upstream:
        port = upstream.sockets[0].getsockname()[1]
        def local_connect(uri, **kwargs):
            return connect(f"ws://127.0.0.1:{port}", proxy=None)
        relay = VoiceRelay("fake-test-key", os.environ.get("REFLECTIONS_VOICE_LOCAL_TOKEN", ""), connector=local_connect)
        async with serve(relay.handle, "127.0.0.1", 8765, max_size=100_000):
            print("MOCK: ready; no external connection", flush=True)
            await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
