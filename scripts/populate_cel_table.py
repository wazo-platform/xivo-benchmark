import csv
import itertools
import os
import sys
from collections.abc import Iterator, Mapping

import sqlalchemy

ASSETS_DIR = os.getenv('WAZO_BENCHMARK_ASSETS_DIR', 'assets')
DATABASE_URI = os.getenv('WAZO_BENCHMARK_DATABASE_URI', 'postgresql://localhost:5432/asterisk')
MAX_GENERATED_CELS = int(os.getenv('WAZO_BENCHMARK_MAX_CELS') or 100_000_000)
GENERATED_CELS_FILENAME = os.getenv('WAZO_BENCHMARK_GENERATED_CELS_FILENAME', f'{MAX_GENERATED_CELS}_cels.csv')

CEL_COLUMNS = (
    'id',
    'eventtype',
    'eventtime',
    'userdeftype',
    'cid_name',
    'cid_num',
    'cid_ani',
    'cid_rdnis',
    'cid_dnid',
    'exten',
    'context',
    'channame',
    'appname',
    'appdata',
    'amaflags',
    'accountcode',
    'peeraccount',
    'uniqueid',
    'linkedid',
    'userfield',
    'peer',
    'call_log_id',
    'extra',
)


def log(*args):
    print(*args, file=sys.stderr)


def generate_uniqueid(linkedid):
    (head, tail) = linkedid.split('.')
    yield linkedid
    current_tail = int(tail) + 1
    while True:
        yield f'{head}.{current_tail}'
        current_tail += 1


def generate_linkedid(initial='0.0'):
    (head, tail) = initial.split('.')
    yield initial
    current_head = int(head) + 1
    while True:
        yield f'{current_head}.{tail}'
        current_head += 1


def generate_new_cel_sequence(new_linkedid, initiator_cels):
    linkedid = new_linkedid
    uniqueid_gen = generate_uniqueid(linkedid)
    initator_linkedid = next(cel['linkedid'] for cel in initiator_cels)
    uniqueid_map = {initator_linkedid: linkedid}
    for cel in initiator_cels:
        new_cel = dict(cel)
        new_cel['linkedid'] = linkedid
        if cel['uniqueid'] in uniqueid_map:
            new_cel['uniqueid'] = uniqueid_map[cel['uniqueid']]
        else:
            new_cel['uniqueid'] = uniqueid_map[cel['uniqueid']] = next(uniqueid_gen)
        new_cel['call_log_id'] = None
        new_cel.pop('id', None)
        yield new_cel


def generate_cel_sequences(base_cels):
    linkedid_gen = generate_linkedid(next(cel['linkedid'] for cel in base_cels))
    total_cels = 0
    log(f'Generating {MAX_GENERATED_CELS} cels')
    while total_cels < MAX_GENERATED_CELS:
        linkedid = next(linkedid_gen)
        log(f'Generating new cel sequence with linkedid {linkedid}')
        new_rows = list(generate_new_cel_sequence(linkedid, base_cels))
        yield from new_rows
        total_cels += len(new_rows)
        log(f'Generated total of {total_cels} entries')


def write_cel_to_database(cel_stream: Iterator[Mapping], config):
    engine = sqlalchemy.create_engine(config['database_uri'])
    table = sqlalchemy.table('cel', *(sqlalchemy.column(col) for col in CEL_COLUMNS))
    with engine.connect(close_with_result=False) as conn:  # type: ignore[call-arg]
        while batch := list(itertools.islice(cel_stream, 1000)):
            conn.execute(sqlalchemy.insert(table), batch)


class SQLCSV(csv.Dialect):
    delimiter = '|'
    quotechar = "'"
    doublequote = True
    skipinitialspace = False
    lineterminator = '\r\n'
    quoting = csv.QUOTE_MINIMAL


def write_generator_to_csv_file(file, data, fieldnames=None):
    first = next(data)
    writer = csv.DictWriter(file, fieldnames=fieldnames or list(first.keys()), dialect=SQLCSV)
    writer.writeheader()
    writer.writerow(first)
    while batch := list(itertools.islice(data, 1000)):
        writer.writerows(batch)


if __name__ == '__main__':
    with open(f'{ASSETS_DIR}/cel_seed.csv') as file:
        csvreader = csv.DictReader(file, dialect=SQLCSV)
        log(csvreader.fieldnames)
        initiator = list(csvreader)

    # write_generator_to_csv_file(sys.stdout, generate_cel_sequences(initiator), fieldnames=csvreader.fieldnames)
    write_cel_to_database(generate_cel_sequences(initiator), {'database_uri': DATABASE_URI})
