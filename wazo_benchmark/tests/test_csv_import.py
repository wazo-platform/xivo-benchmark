# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os.path
import time
from datetime import datetime, timedelta

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient

from .. import constants

MAX_TIME = timedelta(seconds=150)


def test_csv_import():
    auth_client = AuthClient(
        constants.HOST,
        verify_certificate=False,
        username='admin',
        password='proformatique',
    )
    token_data = auth_client.token.new(expiration=300)
    token = token_data['token']
    auth_client.set_token(token)

    client = ConfdClient(
        constants.HOST,
        verify_certificate=False,
        token=token,
    )

    contexts = client.contexts.list()

    internal_contexts = [context['name'] for context in contexts['items'] if context['type'] == 'internal']
    if not internal_contexts:
        raise Exception('Could not find any internal context with username "admin"')
    internal_context = internal_contexts[0]

    incall_contexts = [context['name'] for context in contexts['items'] if context['type'] == 'incall']
    if not incall_contexts:
        raise Exception('Could not find any incall context with username "admin"')
    incall_context = incall_contexts[0]

    file_path = os.path.join(constants.ASSET_DIR, '100entries.csv')
    csv_data = read_csv(file_path, internal_context, incall_context)
    start = datetime.now()
    result = upload_csv(client, token_data['metadata']['tenant_uuid'], csv_data)
    stop = datetime.now()

    assert 'created' in result, f'Result should contains the created users:\n{result}'
    assert len(result['created']) == 100, f'Should have created 100 users\n{result}'
    assert stop - start <= MAX_TIME, f'CSV import exceeded max time ({MAX_TIME})'

    # NOTE(fblackburn): wait until pjsip reload complete before starting next test
    time.sleep(5)


def read_csv(file_path, internal_context_name, incall_context_name):
    with open(file_path, 'rb') as f:
        csv_data = f.read()
    csv_data = csv_data.replace(b'INTERNAL_CONTEXT', bytes(internal_context_name, 'utf-8'))
    csv_data = csv_data.replace(b'INCALL_CONTEXT', bytes(incall_context_name, 'utf-8'))
    return csv_data


def upload_csv(client, tenant_uuid, csv_data):
    return client.users.import_csv(csv_data, tenant_uuid=tenant_uuid)
