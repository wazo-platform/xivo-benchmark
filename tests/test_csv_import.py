# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import time
import os.path

from datetime import datetime, timedelta

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient

from . import constants

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

    start = datetime.now()
    result = upload_csv(client, token_data['metadata']['tenant_uuid'])
    stop = datetime.now()

    assert 'created' in result, f'Result should contains the created users:\n{result}'
    assert len(result['created']) == 100, f'Should have created 100 users\n{result}'
    assert stop - start <= MAX_TIME, f"CSV import exceeded max time ({MAX_TIME})"

    # NOTE(fblackburn): wait until pjsip reload complete before starting next test
    time.sleep(5)


def upload_csv(client, tenant_uuid):
    filepath = os.path.join(constants.ASSET_DIR, "100entries.csv")
    with open(filepath, 'rb') as f:
        csvdata = f.read()
        return client.users.import_csv(csvdata, tenant_uuid=tenant_uuid)
