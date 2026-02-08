#!/usr/bin/env python3
import asyncio
import websockets
import json
import base64
import time

MSG_TYPE_PTY_CREATE = 0x10
MSG_TYPE_PTY_DATA = 0x11
MSG_TYPE_PTY_CLOSE = 0x13
MSG_TYPE_DEVICE_LIST = 0x50

async def run():
    uri = 'ws://127.0.0.1:8765'
    print('connecting to', uri)
    async with websockets.connect(uri) as ws:
        print('connected')
        device_id = None
        session_id = 1
        # wait for device list
        while True:
            msg = await ws.recv()
            if len(msg) < 1:
                continue
            t = msg[0]
            data = {}
            try:
                data = json.loads(msg[1:].decode('utf-8'))
            except:
                pass
            print('recv type', hex(t), data)
            if t == MSG_TYPE_DEVICE_LIST:
                devices = data.get('devices', [])
                if devices:
                    device_id = devices[0]['device_id']
                    print('found device:', device_id)
                    break
        # send pty create
        create = {'device_id': device_id, 'session_id': session_id, 'rows': 24, 'cols': 80}
        msg = bytes([MSG_TYPE_PTY_CREATE]) + json.dumps(create).encode('utf-8')
        print('sending PTY_CREATE', create)
        await ws.send(msg)

        # wait for pty create ack
        while True:
            msg = await ws.recv()
            t = msg[0]
            data = json.loads(msg[1:].decode('utf-8'))
            print('recv type', hex(t), data)
            if t == MSG_TYPE_PTY_CREATE and data.get('status') == 'created':
                print('pty created')
                break

        # send command via PTY_DATA
        cmd = 'ls\n'
        payload = {'device_id': device_id, 'session_id': session_id, 'data': base64.b64encode(cmd.encode()).decode()}
        msg = bytes([MSG_TYPE_PTY_DATA]) + json.dumps(payload).encode('utf-8')
        print('sending PTY_DATA', payload)
        ts_send = time.time()
        await ws.send(msg)
        print('sent at', ts_send)

        # listen for PTY_DATA for some time
        end_time = time.time() + 6
        while time.time() < end_time:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                print('recv timeout waiting for PTY data')
                continue
            t = msg[0]
            data = json.loads(msg[1:].decode('utf-8'))
            now = time.time()
            print('recv type', hex(t), 'at', now, 'data keys', list(data.keys()))
            if t == MSG_TYPE_PTY_DATA:
                print('PTY_DATA payload len', len(data.get('data','')))
        # close pty
        close = {'device_id': device_id, 'session_id': session_id}
        msg = bytes([MSG_TYPE_PTY_CLOSE]) + json.dumps(close).encode('utf-8')
        print('sending PTY_CLOSE')
        await ws.send(msg)
        # wait a bit for any remaining data
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(run())
