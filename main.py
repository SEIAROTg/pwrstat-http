#!/usr/bin/env python3

import json
import logging
import os
import socket
import time

from aiohttp import web


HTTP_HOST = os.getenv('HTTP_HOST', 'localhost')
HTTP_PORT = int(os.getenv('HTTP_PORT', '3000'))
LOG_FORMATTER = '%(asctime)s [%(levelname)-5.5s] %(message)s'
PWRSTATD_SOCK = '/var/pwrstatd.ipc'
INFLUX_MEASUREMENT = os.getenv('INFLUX_MEASUREMENT', 'ups')
is_yes = lambda val: val == 'yes'
TRANSFORMERS = {
    'state': int,
    'battery_volt': int,
    'input_rating_volt': int,
    'output_rating_watt': int,
    'avr_supported': is_yes,
    'online_type': is_yes,
    'diagnostic_result': int,
    'power_event_result': int,
    'battery_remainingtime': int,
    'battery_charging': is_yes,
    'battery_discharging': is_yes,
    'ac_present': is_yes,
    'boost': is_yes,
    'utility_volt': int,
    'output_volt': int,
    'load': int,
    'battery_capacity': int,
}
TAGS = {
    'model_name',
    'firmware_num',
    'battery_volt',
    'input_rating_volt',
    'output_rating_watt',
    'avr_supported',
    'online_type',
}


def influxify(v):
    if type(v) is int:
        return f'{v}i'
    return json.dumps(v)


class Pwrstat:
    def __init__(self):
        self._sock = None
        self._logger = logging.getLogger('pwrstat-http')
        self._logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMATTER))
        self._logger.addHandler(handler)
        self._logger.info('pwrstat-http started.')

    def _connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(PWRSTATD_SOCK)
        sock.settimeout(1)
        return sock

    def _send_command(self, req):
        try:
            if not self._sock:
                self._sock = self._connect()
                self._logger.info('connected to pwrstatd.')
        except Exception as e:
            self._logger.error('failed to connect to pwrstatd: %s', str(e))
            raise
        try:
            self._sock.send((req + '\n\n').encode())
            ret = b''
            while b'\n\n' not in ret:
                buf = self._sock.recv(4096)
                if not buf:
                    raise RuntimeError('connection broken.')
                ret += buf
            return ret.split(b'\n\n', 1)[0].decode()
        except Exception:
            self._sock = None
            self._logger.exception('error while communicating with pwrstatd.')
            raise

    def _parse(self, resp):
        try:
            fields = {'timestamp': time.time_ns()}
            for line in resp.splitlines()[1:]:
                if '=' not in line:
                    continue
                k, v = line.split('=', 1)
                transformer = TRANSFORMERS.get(k, str)
                fields[k] = transformer(v)
            return fields
        except Exception:
            self._logger.exception('Failed to parse pwrstatd response: %s', resp)
            raise

    def status(self):
        return self._parse(self._send_command('STATUS'))

    def handle_status(self, req):
        data = self.status()
        if req.query.get('format') == 'influx':
            timestamp = str(data.pop('timestamp'))
            tags = ','.join(f'{k}={json.dumps(v)}' for k, v in data.items() if k in TAGS)
            fields = ','.join(f'{k}={influxify(v)}' for k, v in data.items() if k not in TAGS)
            return web.Response(text=' '.join((
                ','.join((INFLUX_MEASUREMENT, tags)), fields, timestamp)))
        return web.json_response(data)


if __name__ == '__main__':
    pwrstat = Pwrstat()
    logging.getLogger('aiohttp').setLevel(logging.CRITICAL + 1)
    app = web.Application()
    app.add_routes([
        web.get('/status', pwrstat.handle_status),
    ])
    web.run_app(app, host=HTTP_HOST, port=HTTP_PORT, print=None)
