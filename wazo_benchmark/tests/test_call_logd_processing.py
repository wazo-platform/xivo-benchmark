# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import subprocess
import time
import types
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from uuid import uuid4

import kombu
import pytest

from .. import constants

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


@dataclass
class BusConfig:
    username: str = 'guest'
    password: str = 'guest'
    host: str = constants.HOST
    vhost: str = ''
    port: int = 5672
    exchange_name: str = 'wazo-headers'
    exchange_type: str = 'headers'
    timeout: int = 60 * 5


@dataclass
class Config:
    benchmark_host: str
    linkedid: str
    bus_config: BusConfig = field(default_factory=BusConfig)
    max_processing_time = 10
    assets_dir: str = constants.ASSET_DIR


@pytest.fixture()
def config():
    host = os.getenv('WAZO_BENCHMARK_HOST', constants.HOST)
    bus_config = BusConfig(
        username=os.getenv('WAZO_BENCHMARK_BUS_USERNAME', BusConfig.username),
        password=os.getenv('WAZO_BENCHMARK_BUS_PASSWORD', BusConfig.password),
        host=host,
    )
    linkedid = os.getenv('WAZO_BENCHMARK_LINKEDID')
    assert linkedid, linkedid
    config = Config(bus_config=bus_config, linkedid=linkedid, benchmark_host=host)
    return config


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


def send_linkedid_end(connection: kombu.Connection, exchange_config: BusConfig, linkedid):
    exchange = kombu.Exchange(exchange_config.exchange_name, type=exchange_config.exchange_type)
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


def listen_for_call_log_created(connection: kombu.Connection, config: BusConfig):
    exchange = kombu.Exchange(config.exchange_name, type=config.exchange_type)
    queue_name = str(uuid4())
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
        connection.drain_events(timeout=config.timeout)
    return messages.pop()


def project(m, ks):
    return {k: m.get(k) for k in ks}


def test_call_logd_processing(config: Config):
    bus_config = config.bus_config
    bus_url = 'amqp://{username}:{password}@{host}:{port}/{vhost}'.format_map(asdict(bus_config))

    logger.info('Starting ssh tunnel')
    with ssh_tunnel(bus_config.host, bus_config.port):
        logger.info('Starting rabbitmq connection')
        with kombu.Connection(bus_url) as connection:
            logger.info('Sending LINKEDID_END event')
            send_linkedid_end(
                connection,
                bus_config,
                config.linkedid,
            )
            with timer() as t:
                logger.info('Listening for call_log_created event')
                (event_body, event_headers) = listen_for_call_log_created(connection, bus_config)
            assert event_headers['name'] == 'call_log_created'
            assert t.elapsed_time <= config.max_processing_time
