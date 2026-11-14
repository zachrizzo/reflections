import asyncio
import base64
import json
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from relay import VoiceRelay

TOKEN = "x" * 40


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.seen = asyncio.Queue()

        async def fake_upstream(ws):
            await ws.send(json.dumps({"type": "session.created"}))
            update = json.loads(await ws.recv())
            await self.seen.put(update)
            await ws.send(json.dumps({"type": "session.updated"}))
            async for raw in ws:
                event = json.loads(raw)
                await self.seen.put(event)
                if event["type"] == "response.create":
                    await ws.send(json.dumps({"type": "response.output_audio.delta", "delta": "AQACAA=="}))
                    await ws.send(json.dumps({"type": "response.done"}))

        self.upstream_server = await serve(fake_upstream, "127.0.0.1", 0)
        upstream_port = self.upstream_server.sockets[0].getsockname()[1]

        def fake_connect(uri, **kwargs):
            return connect(f"ws://127.0.0.1:{upstream_port}", proxy=None)

        self.relay = VoiceRelay("fake-key", TOKEN, connector=fake_connect)
        self.server = await serve(self.relay.handle, "127.0.0.1", 0)
        self.url = f"ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"

    async def asyncTearDown(self):
        self.server.close()
        self.upstream_server.close()
        await self.server.wait_closed()
        await self.upstream_server.wait_closed()

    async def begin(self, ws):
        await ws.send(json.dumps({"type": "session.start", "token": TOKEN,
                                  "npc": {"name": "Guard", "mood": "alert"}}))
        self.assertEqual(json.loads(await ws.recv())["type"], "session.ready")
        update = await self.seen.get()
        self.assertEqual(update["session"]["audio"]["input"]["format"]["rate"], 24000)
        self.assertIsNone(update["session"]["audio"]["input"]["turn_detection"])
        self.assertIn("Guard", update["session"]["instructions"])

    async def test_round_trip_and_order(self):
        async with connect(self.url, proxy=None) as ws:
            await self.begin(ws)
            pcm = base64.b64encode(b"\0\0\1\0").decode()
            await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": pcm}))
            await ws.send(json.dumps({"type": "turn.end"}))
            self.assertEqual([(await self.seen.get())["type"] for _ in range(3)],
                             ["input_audio_buffer.append", "input_audio_buffer.commit", "response.create"])
            self.assertEqual(json.loads(await ws.recv())["delta"], "AQACAA==")
            self.assertEqual(json.loads(await ws.recv())["type"], "response.done")

    async def test_bad_token_never_connects_upstream(self):
        async with connect(self.url, proxy=None) as ws:
            await ws.send(json.dumps({"type": "session.start", "token": "wrong"}))
            with self.assertRaises(ConnectionClosed):
                await ws.recv()
            self.assertTrue(self.seen.empty())

    async def rejected(self, event):
        async with connect(self.url, proxy=None) as ws:
            await self.begin(ws)
            await ws.send(json.dumps(event))
            with self.assertRaises(ConnectionClosed):
                await ws.recv()

    async def test_arbitrary_event_rejected(self):
        await self.rejected({"type": "session.update", "session": {}})

    async def test_oversized_audio_rejected(self):
        await self.rejected({"type": "input_audio_buffer.append", "audio": base64.b64encode(b"a" * 32002).decode()})


if __name__ == "__main__":
    unittest.main()
