import argparse
import itertools
import os
import random
import socket
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import sqlalchemy

DEFAULT_DATABASE_URI = 'postgresql://localhost:5432/asterisk'
DEFAULT_COUNT = 100_000
BATCH_SIZE = 1000

DIRECTIONS = ('inbound', 'internal', 'outbound')
NAMES = (
    'Alice Martin', 'Bob Tremblay', 'Charlie Roy', 'Diana Gagnon',
    'Eve Bouchard', 'Frank Côté', 'Grace Morin', 'Hugo Lavoie',
    'Isabelle Fortin', 'Jean Gagné',
)
EXTENS = ('1001', '1002', '1003', '1004', '1005', '1006', '1007', '1008', '1009', '1010')
LINE_IDS = (1, 2, 3, 4, 5)

CALL_LOG_COLUMNS = (
    'date', 'date_answer', 'date_end', 'tenant_uuid',
    'source_name', 'source_exten', 'source_internal_name',
    'source_internal_exten', 'source_internal_context',
    'source_line_identity', 'requested_name', 'requested_exten',
    'requested_context', 'requested_internal_exten',
    'requested_internal_context', 'destination_name',
    'destination_exten', 'destination_internal_exten',
    'destination_internal_context', 'destination_line_identity',
    'blocked', 'direction', 'user_field', 'conversation_id',
)

PARTICIPANT_COLUMNS = (
    'call_log_id', 'user_uuid', 'line_id', 'role', 'tags', 'answered', 'requested',
)

DESTINATION_COLUMNS = (
    'call_log_id', 'destination_details_key', 'destination_details_value',
)


def log(*args: object) -> None:
    print(*args, file=sys.stdout)


def _build_netloc(user: str, password: str | None, host: str, port: int) -> str:
    userinfo = f'{user}:{password}' if password else user
    return f'{userinfo}@{host}:{port}'


@contextmanager
def ssh_tunnel(database_uri: str, db_user: str, db_password: str | None):
    """SSH to the host in the URI, forward localhost:<db_port> to localhost:<db_port> on the remote.

    Yields a rewritten URI pointing to localhost:<db_port> with the given credentials.
    """
    parsed = urlparse(database_uri)
    remote_host = parsed.hostname
    db_port = parsed.port or 5432

    if not remote_host or remote_host in ('localhost', '127.0.0.1', '::1'):
        local_uri = urlunparse(parsed._replace(
            netloc=_build_netloc(db_user, db_password, remote_host or 'localhost', db_port),
        ))
        yield local_uri
        return

    forward = f'{db_port}:localhost:{db_port}'
    ssh_cmd = [
        'ssh', '-N', '-L', forward,
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ExitOnForwardFailure=yes',
        f'root@{remote_host}',
    ]

    log(f'Opening SSH tunnel {remote_host} -> localhost:{db_port}')
    proc = subprocess.Popen(ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # Wait for the tunnel to be ready
    for _ in range(30):
        try:
            with socket.create_connection(('127.0.0.1', db_port), timeout=1):
                break
        except OSError:
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode() if proc.stderr else ''
                log(f'ERROR: SSH tunnel failed: {stderr}')
                sys.exit(1)
            import time
            time.sleep(0.5)
    else:
        proc.terminate()
        log('ERROR: SSH tunnel did not become ready in time')
        sys.exit(1)

    local_uri = urlunparse(parsed._replace(
        netloc=_build_netloc(db_user, db_password, 'localhost', db_port),
    ))
    try:
        yield local_uri
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        log('SSH tunnel closed')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Populate call_logd_call_log table with synthetic data for benchmarking.',
    )
    parser.add_argument(
        '--count',
        type=int,
        default=DEFAULT_COUNT,
        help=f'Number of call_log rows to generate (default: {DEFAULT_COUNT})',
    )
    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Start of date range (ISO 8601, e.g. 2024-01-01)',
    )
    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='End of date range (ISO 8601, e.g. 2024-12-31)',
    )
    parser.add_argument(
        '--database-uri',
        type=str,
        default=os.getenv('WAZO_BENCHMARK_DATABASE_URI', DEFAULT_DATABASE_URI),
        help=f'Database URI (default: env WAZO_BENCHMARK_DATABASE_URI or {DEFAULT_DATABASE_URI})',
    )
    parser.add_argument(
        '--db-user',
        type=str,
        required=True,
        help='Username for the database connection',
    )
    parser.add_argument(
        '--db-password',
        type=str,
        default=None,
        help='Password for the database connection (optional)',
    )
    return parser.parse_args()


def fetch_tenant_uuid(engine: sqlalchemy.engine.Engine) -> uuid.UUID:
    tenant_table = sqlalchemy.table(
        'call_logd_tenant', sqlalchemy.column('uuid'),
    )
    with engine.connect() as conn:
        row = conn.execute(sqlalchemy.select(tenant_table.c.uuid).limit(1)).first()
    if row is None:
        log('ERROR: No tenant found in call_logd_tenant. Aborting.')
        sys.exit(1)
    return row[0]


def fetch_extensions(engine: sqlalchemy.engine.Engine) -> list[str]:
    call_log_table = sqlalchemy.table(
        'call_logd_call_log',
        sqlalchemy.column('source_exten'),
        sqlalchemy.column('destination_exten'),
    )
    with engine.connect() as conn:
        source_rows = conn.execute(
            sqlalchemy.select(call_log_table.c.source_exten)
            .where(call_log_table.c.source_exten.isnot(None))
            .distinct()
        ).fetchall()
        dest_rows = conn.execute(
            sqlalchemy.select(call_log_table.c.destination_exten)
            .where(call_log_table.c.destination_exten.isnot(None))
            .distinct()
        ).fetchall()
    extens = list({row[0] for row in source_rows} | {row[0] for row in dest_rows})
    if extens:
        log(f'Found {len(extens)} existing extension(s) from DB')
        return extens
    log(f'No extensions found in DB, using {len(EXTENS)} defaults')
    return list(EXTENS)


def fetch_user_uuids(engine: sqlalchemy.engine.Engine) -> list[uuid.UUID]:
    participant_table = sqlalchemy.table(
        'call_logd_call_log_participant', sqlalchemy.column('user_uuid'),
    )
    with engine.connect() as conn:
        rows = conn.execute(
            sqlalchemy.select(participant_table.c.user_uuid).distinct()
        ).fetchall()
    if not rows:
        log('ERROR: No existing users found in call_logd_call_log_participant. Aborting.')
        sys.exit(1)
    user_uuids = [row[0] for row in rows]
    log(f'Found {len(user_uuids)} existing user(s)')
    return user_uuids


def generate_call_logs(
    count: int,
    start_date: datetime,
    end_date: datetime,
    tenant_uuid: uuid.UUID,
    user_uuids: list[uuid.UUID],
    extensions: list[str],
) -> Iterator[dict]:
    total_seconds = (end_date - start_date).total_seconds()
    interval = total_seconds / count if count > 1 else 0

    for i in range(count):
        date = start_date + timedelta(seconds=interval * i)
        answered = random.random() < 0.9
        date_answer = date + timedelta(seconds=random.randint(5, 30)) if answered else None
        if answered and date_answer is not None:
            date_end = date_answer + timedelta(seconds=random.randint(10, 600))
        else:
            date_end = date + timedelta(seconds=random.randint(5, 15))

        direction = random.choice(DIRECTIONS)
        source_name = random.choice(NAMES)
        dest_name = random.choice(NAMES)
        source_exten = random.choice(extensions)
        remaining_extens = [e for e in extensions if e != source_exten]
        dest_exten = random.choice(remaining_extens) if remaining_extens else source_exten
        source_user = random.choice(user_uuids)
        dest_user = random.choice(user_uuids)

        yield {
            'date': date,
            'date_answer': date_answer,
            'date_end': date_end,
            'tenant_uuid': tenant_uuid,
            'source_name': source_name,
            'source_exten': source_exten,
            'source_internal_name': source_name,
            'source_internal_exten': source_exten,
            'source_internal_context': 'default',
            'source_line_identity': f'PJSIP/{source_exten}',
            'requested_name': dest_name,
            'requested_exten': dest_exten,
            'requested_context': 'default',
            'requested_internal_exten': dest_exten,
            'requested_internal_context': 'default',
            'destination_name': dest_name,
            'destination_exten': dest_exten,
            'destination_internal_exten': dest_exten,
            'destination_internal_context': 'default',
            'destination_line_identity': f'PJSIP/{dest_exten}',
            'blocked': random.random() < 0.02,
            'direction': direction,
            'user_field': '',
            'conversation_id': str(uuid.uuid4()),
            '_source_user_uuid': source_user,
            '_dest_user_uuid': dest_user,
            '_answered': answered,
        }


def generate_participants(call_log_id: int, call_log: dict) -> list[dict]:
    return [
        {
            'call_log_id': call_log_id,
            'user_uuid': call_log['_source_user_uuid'],
            'line_id': random.choice(LINE_IDS),
            'role': 'source',
            'tags': '{}',
            'answered': True,
            'requested': False,
        },
        {
            'call_log_id': call_log_id,
            'user_uuid': call_log['_dest_user_uuid'],
            'line_id': random.choice(LINE_IDS),
            'role': 'destination',
            'tags': '{}',
            'answered': call_log['_answered'],
            'requested': True,
        },
    ]


def generate_destination_details(call_log_id: int, call_log: dict) -> list[dict]:
    return [
        {
            'call_log_id': call_log_id,
            'destination_details_key': 'type',
            'destination_details_value': 'user',
        },
        {
            'call_log_id': call_log_id,
            'destination_details_key': 'user_name',
            'destination_details_value': call_log['destination_name'],
        },
    ]


def _strip_internal_keys(call_log: dict) -> dict:
    return {k: v for k, v in call_log.items() if not k.startswith('_')}


def write_to_database(
    call_log_stream: Iterator[dict],
    engine: sqlalchemy.engine.Engine,
) -> None:
    call_log_table = sqlalchemy.table(
        'call_logd_call_log',
        sqlalchemy.column('id'),
        *(sqlalchemy.column(col) for col in CALL_LOG_COLUMNS),
    )
    participant_table = sqlalchemy.table(
        'call_logd_call_log_participant',
        *(sqlalchemy.column(col) for col in PARTICIPANT_COLUMNS),
    )
    destination_table = sqlalchemy.table(
        'call_logd_call_log_destination',
        *(sqlalchemy.column(col) for col in DESTINATION_COLUMNS),
    )

    total = 0
    with engine.connect() as conn:
        while batch := list(itertools.islice(call_log_stream, BATCH_SIZE)):
            db_transaction = conn.begin()
            insert_stmt = (
                sqlalchemy.insert(call_log_table)
                .values([_strip_internal_keys(row) for row in batch])
                .returning(call_log_table.c.id)
            )
            result = conn.execute(insert_stmt)
            inserted_ids = [row[0] for row in result]

            all_participants: list[dict] = []
            all_destinations: list[dict] = []
            for call_log_id, call_log in zip(inserted_ids, batch):
                all_participants.extend(generate_participants(call_log_id, call_log))
                all_destinations.extend(generate_destination_details(call_log_id, call_log))

            if all_participants:
                conn.execute(sqlalchemy.insert(participant_table), all_participants)
            if all_destinations:
                conn.execute(sqlalchemy.insert(destination_table), all_destinations)

            db_transaction.commit()
            total += len(batch)
            log(f'Inserted {total} call logs')


if __name__ == '__main__':
    args = parse_args()

    start_date = datetime.fromisoformat(args.start_date).replace(tzinfo=timezone.utc)
    end_date = datetime.fromisoformat(args.end_date).replace(tzinfo=timezone.utc)

    if start_date >= end_date:
        log('ERROR: --start-date must be before --end-date')
        sys.exit(1)

    with ssh_tunnel(args.database_uri, args.db_user, args.db_password) as local_uri:
        engine = sqlalchemy.create_engine(local_uri)
        tenant_uuid = fetch_tenant_uuid(engine)
        log(f'Using tenant: {tenant_uuid}')

        user_uuids = fetch_user_uuids(engine)
        extensions = fetch_extensions(engine)

        log(f'Generating {args.count} call logs from {start_date} to {end_date}')
        call_log_stream = generate_call_logs(
            args.count, start_date, end_date, tenant_uuid, user_uuids, extensions,
        )
        write_to_database(call_log_stream, engine)
        log('Done')
