"""Local protocol tests for recipe_relay.py. They never contact OpenAI (the describe function is a stub)."""
import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock

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

    async def test_failure_is_reported_without_details(self):
        def broken(text):
            raise RuntimeError('OpenAI returned HTTP 401')
        relay = recipe_relay.RecipeRelay(TOKEN, broken)
        server = await serve(relay.handle, '127.0.0.1', 0)
        try:
            async with connect('ws://127.0.0.1:%d' % server.sockets[0].getsockname()[1]) as ws:
                await ws.send(json.dumps({'type': 'describe', 'token': TOKEN, 'text': 'fireball'}))
                reply = json.loads(await ws.recv())
        finally:
            server.close()
            await server.wait_closed()
        self.assertEqual(reply, {'type': 'error', 'message': 'Interpretation failed (RuntimeError).'})


class KeyAndTokenTests(unittest.TestCase):
    def test_key_is_read_from_file_and_stripped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'api_key')
            with open(path, 'w', encoding='utf-8-sig') as f:
                f.write('sk-test-' + 'a' * 40 + '\r\n')
            self.assertEqual(recipe_relay.load_api_key(path), 'sk-test-' + 'a' * 40)

    def test_bad_or_missing_key_file_exits_without_echoing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'api_key')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('not a key secret-value')
            with self.assertRaises(SystemExit) as raised:
                recipe_relay.load_api_key(path)
            self.assertNotIn('secret-value', str(raised.exception))
            with self.assertRaises(SystemExit):
                recipe_relay.load_api_key(os.path.join(folder, 'missing'))

    def test_token_file_is_published_only_without_launch_token(self):
        with tempfile.TemporaryDirectory() as folder:
            target = recipe_relay.Path(folder) / 'Saved' / 'SpellCrafting' / 'relay-token'
            with mock.patch.object(recipe_relay, 'TOKEN_FILE', target), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop('REFLECTIONS_SPELL_LOCAL_TOKEN', None)
                token, published = recipe_relay.local_token()
                self.assertTrue(published)
                self.assertGreaterEqual(len(token), 32)
                self.assertEqual(target.read_text(encoding='utf-8'), token)
                os.environ['REFLECTIONS_SPELL_LOCAL_TOKEN'] = 'y' * 40
                self.assertEqual(recipe_relay.local_token(), ('y' * 40, False))

    def test_sanitize_clamps_names_and_balance(self):
        recipe = recipe_relay.sanitize({'form': 'Laser', 'element': 'Ice', 'modifiers': [], 'trigger': 'Pulse',
                                        'power': 0, 'name': 'The   Very Long Frozen Spell Name Here'})
        self.assertEqual(recipe['form'], 'Bolt')
        self.assertEqual(recipe['modifiers'], ['Split'])
        self.assertEqual(recipe['power'], 1)
        self.assertEqual(recipe['name'], 'The Very Long Frozen')


if __name__ == '__main__':
    unittest.main()
