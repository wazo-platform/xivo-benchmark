# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os.path
import time
import requests

from wazo_dird_client import Client as DirdClient
from xivo_auth_client import Client as AuthClient

from . import constants

MAX_TIME = 10
USERNAME = 'alice'
PASSWORD = 'alice'


def test_csv_import():
    auth_client = AuthClient(
        constants.HOST,
        verify_certificate=False,
        username='admin',
        password='proformatique'
    )
    dird_client = DirdClient(
        constants.HOST,
        https=True,
        verify_certificate=False,
        timeout=MAX_TIME
    )

    token_data = auth_client.token.new(expiration=300)
    token = token_data['token']
    auth_client.set_token(token)

    try:
        auth_client.users.new(
            username=USERNAME,
            password=PASSWORD,
            tenant_uuid=token_data['metadata']['tenant_uuid'],
        )
    except requests.HTTPError as e:
        if e.response.status_code == 409:
            pass
        else:
            raise

    user_auth_client = AuthClient(
        constants.HOST,
        verify_certificate=False,
        username=USERNAME,
        password=PASSWORD,
    )
    token = user_auth_client.token.new('wazo_user', expiration=300)['token']

    result, time_to_complete = upload_csv(dird_client, token)

    assert 'created' in result, 'The result does not contain created contacts'
    assert len(result['created']) == 1000, 'expected 1000 created contacts: {}'.format(len(result['created']))
    assert time_to_complete < MAX_TIME, 'The import took too long {}s > {}s'.format(time_to_complete,
                                                                                    MAX_TIME)


def upload_csv(dird_client, token):
    filepath = os.path.join(constants.ASSET_DIR, "1000contacts.csv")
    with open(filepath, 'rb') as f:
        csvdata = f.read()
        start = time.time()
        result = dird_client.personal.import_csv(csvdata, token=token)
        end = time.time()
        return result, end - start
