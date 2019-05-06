# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from invoke import task


@task
def reset_server(connection):
    connection.run("wazo-service stop")
    reset_database(connection)
    connection.run("wazo-service start")
    upgrade_server(connection)
    snapshot_server(connection)


@task
def reset_database(connection):
    drop_database(connection)
    restore_database(connection)


@task
def drop_database(connection):
    connection.sudo("dropdb asterisk", user="postgres")


@task
def restore_database(connection):
    connection.run("rm -rf /var/tmp/pg-backup")
    connection.run("tar xvf /var/tmp/snapshot/db.tgz -C /var/tmp")
    connection.sudo("pg_restore -C -d postgres /var/tmp/pg-backup/asterisk-*.dump", user="postgres")


@task
def upgrade_server(connection):
    connection.run("wazo-upgrade -f")


@task
def snapshot_server(connection):
    connection.run("mkdir -p /var/tmp/snapshot")
    connection.run("xivo-backup db /var/tmp/snapshot/db")
