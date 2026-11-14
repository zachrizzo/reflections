"""Local protocol tests for recipe_relay.py. They never contact OpenAI (the describe function is a stub)."""
import asyncio
import json
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

import recipe_relay

TOKEN = 'x' * 40


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.seen = []

        def describe(text):
            self.seen.append(text)
            return {'form': 'Orb', 'element': 'Lightning', 'modifiers': ['Gravity', 'Chain', 'Chain', 'Nonsense'],
                    'trigger': 'Pulse', 'power': 9, 'name': 'Storm\x00 Eye'}
        relay = recipe_relay.RecipeRelay(TOKEN, describe)
        self.server = await serve(relay.handle, '127.0.0.1', 0)
        self.url = 'ws://127.0.0.1:%d' % self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def ask(self, message):
        async with connect(self.url) as ws:
            await ws.send(json.dumps(message))
            return json.loads(await ws.recv())

    async def test_recipe_is_sanitized(self):
        reply = await self.ask({'type': 'describe', 'token': TOKEN, 'text': 'a slow orb of lightning that pulls enemies in'})
        self.assertEqual(reply['type'], 'recipe')
        self.assertEqual(reply['recipe']['modifiers'], ['Gravity', 'Chain'])
        self.assertEqual(reply['recipe']['power'], 5)
        self.assertEqual(reply['recipe']['name'], 'Storm Eye')

    async def test_wrong_token_is_refused(self):
        reply = await self.ask({'type': 'describe', 'token': 'nope', 'text': 'fireball'})
        self.assertEqual(reply['type'], 'error')
        self.assertEqual(self.seen, [])

    async def test_text_is_truncated(self):
        await self.ask({'type': 'describe', 'token': TOKEN, 'text': 'a' * 5000})
        self.assertEqual(len(self.seen[0]), recipe_relay.MAX_TEXT)

    def test_short_token_rejected(self):
        with self.assertRaises(ValueError):
            recipe_relay.RecipeRelay('short', lambda t: {})


if __name__ == '__main__':
    unittest.main()
