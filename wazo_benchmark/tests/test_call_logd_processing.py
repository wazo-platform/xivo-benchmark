# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import subprocess
import sys
import time
import types
from contextlib import contextmanager
from uuid import uuid4

import kombu

from . import constants

logger = logging.getLogger(__name__)


SSH_BASE_COMMAND = [
    'ssh',
    '-q',
    '-o',
    'PreferredAuthentications=publickey',
    '-o',
    'StrictHostKeyChecking=no',
    '-o',
    'UserKnownHostsFile=/dev/null',
    '-l',
    'root',
]
HOST = os.getenv('WAZO_BENCHMARK_HOST', constants.HOST)


def ssh_command(host, ssh_args=None, remote_command=None):
    command = SSH_BASE_COMMAND[:]
    if ssh_args:
        command += list(ssh_args)
    command.append(host)
    if remote_command:
        command += remote_command

    return command


@contextmanager
def ssh_tunnel(host, port: int):
    tunnel_args = ['-L', f'{port}:localhost:{port}', '-N', '-f']
    tunnel_proc = subprocess.Popen(ssh_command(host, ssh_args=tunnel_args), stderr=subprocess.PIPE)
    with tunnel_proc:
        assert tunnel_proc.stderr
        for line in iter(tunnel_proc.stderr.readline, b''):
            logger.info('(ssh tunnel %d:%s:%d %s): %s', port, 'localhost', port, host, line)
        yield
        return


_DEFAULT_CONFIG = {
    'username': 'guest',
    'password': 'guest',
    'host': 'localhost',
    'vhost': '',
    'port': 5672,
    'exchange_name': 'wazo-headers',
    'exchange_type': 'headers',
}
BUS_TIMEOUT = 60 * 5
MAX_PROCESSING_TIME = 10


def send_linkedid_end(connection: kombu.Connection, exchange_config, linkedid):
    exchange = kombu.Exchange(exchange_config['exchange_name'], type=exchange_config['exchange_type'])
    producer = kombu.Producer(connection, exchange=exchange, auto_declare=True)
    payload = {
        'data': {
            'EventName': 'LINKEDID_END',
            'LinkedID': linkedid,
        },
        'name': 'CEL',
    }
    headers = {'name': 'CEL'}
    with producer:
        producer.publish(payload, headers=headers)


@contextmanager
def timer():
    obj = types.SimpleNamespace()
    obj.start_time = time.time()
    logger.info('Starting timer at time %f', obj.start_time)
    try:
        yield obj
    finally:
        obj.end_time = time.time()
        obj.elapsed_time = obj.end_time - obj.start_time
        logger.info('Stopping timer at time %f; %f seconds elapsed', obj.end_time, obj.elapsed_time)


def listen_for_call_log_created(connection: kombu.Connection, config):
    exchange = kombu.Exchange(config['exchange_name'], type=config['exchange_type'])
    queue_name = str(uuid4())
    # headers = {"name": "call_log_created"}
    queue = kombu.Queue(
        name=queue_name,
        exchange=exchange,
        bindings=[kombu.binding(exchange=exchange, routing_key='call_log.created')],
        channel=connection.channel(),
    )
    messages = []

    def message_callback(body, message: kombu.Message):
        print("Caught 'call_log_created' event")
        messages.append((body, message.headers))
        message.ack()

    with kombu.Consumer(connection, queues=[queue], auto_declare=True) as consumer:
        consumer.register_callback(message_callback)
        connection.drain_events(timeout=BUS_TIMEOUT)
    return messages.pop()


def project(m, ks):
    return {k: m.get(k) for k in ks}


def test_call_logd_processing(config):
    bus_url = 'amqp://{username}:{password}@{host}:{port}/{vhost}'.format_map(config)

    exchange_config = project(config, ['exchange_type', 'exchange_name'])
    logger.info('Starting ssh tunnel')
    with ssh_tunnel(config['host'], config['port']):
        logger.info('Starting rabbitmq connection')
        with kombu.Connection(bus_url) as connection:
            logger.info('Sending LINKEDID_END event')
            send_linkedid_end(
                connection,
                exchange_config,
                config['linkedid'],
            )
            with timer() as t:
                logger.info('Listening for call_log_created event')
                (event_body, event_headers) = listen_for_call_log_created(connection, exchange_config)
            assert event_headers['name'] == 'call_log_created'
            assert t.elapsed_time <= MAX_PROCESSING_TIME


if __name__ == '__main__':
    logging.basicConfig(
        level={'debug': logging.DEBUG, 'info': logging.INFO}[os.getenv('WAZO_BENCHMARK_LOG_LEVEL', 'info').lower()]
    )
    test_call_logd_processing(
        dict(
            _DEFAULT_CONFIG,
            host=os.getenv('WAZO_BENCHMARK_HOST'),
            linkedid=sys.argv[1],
        )
    )
