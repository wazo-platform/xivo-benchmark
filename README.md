XiVO Benchmark
==============

Tests for measuring performance issues on physical servers

Setup
=====

These tests require a recent XiVO business server installed with a software RAID. Once the
installation is finished you must go through the following steps:

 * Go through wizard setup
 * Add context ranges
  * user : 6000-9999
  * from-extern: 1000-9999
 * add a webservice user
  * username: admin
  * password: proformatique
  * acl:
    * `auth.users.create`
    * `confd.users.import.create`
    * `confd.contexts.read`

 * Add the following line in `/etc/rabbitmq/rabbitmq.config`:

   ```
   {loopback_users, []}
   ```
 * `systemctl restart rabbitmq-server`
 * Add the following line in `/etc/postgresql/15/main/postgresql.conf`:
   ```
   listen_addresses = '0.0.0.0'
   ```
 * Add the following line in `/etc/postgresql/15/main/pg_hba.conf`:
   ```
   host all asterisk 0.0.0.0/0   md5
   ```

Once the server is ready, install the python dependencies for running the tests:

    pip install -r requirements.txt

Running tests
=============

These tests require a "fresh" install of Wazo before every run.  In order to avoid reinstalling a
physical server every time, a fabfile with commands to reset the database and upgrade the Wazo is
included. Resetting the server is done by running:

    fab -H <host> reset-server

Once the server is reset, run the tests with pytest:

    pytest tests


### call-logd tests
For call-logd processing tests, a script is available to populate the database 'cel' table from a seed cel sequence.
The script can be run on the command line and is configured through these environment variables:
```
WAZO_BENCHMARK_ASSETS_DIR=assets
WAZO_BENCHMARK_DATABASE_URI='postgresql://localhost:5432/asterisk'
WAZO_BENCHMARK_MAX_CELS=100_000_000
WAZO_BENCHMARK_GENERATED_CELS_FILENAME=${WAZO_BENCHMARK_MAX_CELS}_cels.csv
```
The scripts connects directly to the database, and might be run locally with an ssh port forward to the test environment's database,
or directly in the test environment.

```
$ ssh -L 5432:localhost:5432 -N wazo-benchmark.dev.wazo.io &
$ python scripts/populate_cel_table.py
```

Modifying the server
==

When the server needs to be modified to include new configurations the following steps should be taken.

#. Restore the server to its initial state `fab -H <host> reset-server`
#. Make the required configurations
#. Create a new snapshot such that reset_server take the modification into account `fab -H <host> snapshot-server`
