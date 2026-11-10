# Ansible role for MongoDB

Ansible role to install and manage [MongoDB](https://www.mongodb.org/).

- Install and configure MongoDB.
- Create the initial administrator and manage database users.
- Configure authentication and replica sets.
- Install and configure Percona MongoDB Exporter.
- Optionally install the MMS monitoring agent.

The role requires **Ansible core 2.21 or later** and the `community.mongodb`
collection. PyMongo is installed exclusively through the operating system's
`python3-pymongo` package. Use a system Python interpreter that can import this
package; the role does not install PyMongo through pip or create a virtualenv.

MongoDB test matrix:

| Distribution | MongoDB | System PyMongo | Verification |
| ------------ | ------- | -------------- | ------------ |
| Ubuntu 24.04, amd64 | 4.4.31 | 3.11.0 | Docker: standalone, bootstrap, three-node replica set, authorization disabled |
| Debian | Not tested in the current matrix | OS package | Debian-family installation tasks available |
| RHEL-family / Amazon Linux | Not tested in the current matrix | OS package | RPM installation tasks available; require DNF and matching packages |

The table describes the current role tests, rather than upstream MongoDB platform
support. Other distribution/version combinations require separate validation.
On Ubuntu 22 or later, the default compatibility calculation selects the Focal
MongoDB repository for MongoDB versions below 5.0. The role installs `libssl1.1`
from Focal security when needed and removes that temporary repository in an
`always` block. The configured MongoDB version is not implicitly changed to a
newer major release.

#### Variables

The following settings cover the role's main interface. See
[defaults/main.yml](defaults/main.yml) for the full defaults and
[meta/argument_specs.yml](meta/argument_specs.yml) for input validation.
Values in inventory take precedence over role defaults.

```yaml
# Installation source and version.
# mongodb-org uses the official MongoDB repository.
# Alternative package names are not covered by the current test matrix.
mongodb_package: mongodb-org
mongodb_package_state: present
mongodb_version: "4.4" # Release series, or an exact package version such as "4.4.31".

# Normally calculated from the distribution and MongoDB version.
# Set false to select the legacy Ubuntu/Focal compatibility path explicitly.
# mongodb_version_supported: false

# Use the collection's legacy API path for the system PyMongo 3.x package.
mongodb_strict_compatibility: false
mongodb_user_update_password: "on_create" # Choices: on_create, always.
mongodb_users: []
mongodb_oplog_users: []

# Service management.
mongodb_manage_service: true
mongodb_manage_systemd_unit: true
mongodb_systemd_unit_limit_nofile: 64000
mongodb_systemd_unit_limit_nproc: 64000
mongodb_disable_transparent_hugepages: false
mongodb_use_numa: true

mongodb_user: "{{ 'mongod' if ansible_facts['os_family'] == 'RedHat' else 'mongodb' }}"
mongodb_uid: null # Optional service account UID.
mongodb_gid: null # Optional service account GID.
mongodb_daemon_name: "{{ 'mongod' if 'mongodb-org' in mongodb_package else 'mongodb' }}"

## net options
mongodb_net_bindip: "127.0.0.1" # Comma-separated listen addresses.
mongodb_net_ipv6: false
mongodb_net_maxconns: 65536
mongodb_net_port: 27017
mongodb_net_ssl: disabled
mongodb_net_ssl_mode: ""
mongodb_net_ssl_pemfile: ""
mongodb_net_ssl_host: ""

# Connection settings used by database management tasks on the managed host.
# requireSSL selects mongodb_net_ssl_host instead of 127.0.0.1 by default.
mongodb_login_host: "{{ mongodb_net_ssl_host if mongodb_net_ssl_mode == 'requireSSL' else '127.0.0.1' }}"
mongodb_login_port: "{{ mongodb_net_port }}"

## processManagement options
# The managed systemd Type=simple unit requires a foreground process.
mongodb_processmanagement_fork: false

## security options
mongodb_security_authorization: "disabled" # Choices: disabled, enabled.
mongodb_security_javascript_enabled: true
mongodb_security_keyfile: /etc/mongodb-keyfile
mongodb_keyfile_content: "" # Required shared secret for an authenticated replica set.
mongodb_root_admin_name: siteRootAdmin
mongodb_root_admin_password: "" # Required when authorization is enabled.

## storage options
mongodb_storage_dbpath: /data/db
mongodb_storage_dirperdb: false
mongodb_storage_engine: wiredTiger
mongodb_storage_journal_enabled: true # Rendered for MongoDB versions up to 6.0.
mongodb_wiredtiger_directory_for_indexes: false
# Optional WiredTiger cache size in GB; omitted by default.
# mongodb_wiredtiger_cache_size: 1

## systemLog options
mongodb_systemlog_destination: file # Choices: file, syslog.
mongodb_systemlog_logappend: true
mongodb_systemlog_logrotate: rename # MongoDB's own log rotation behavior.
mongodb_systemlog_path: "/var/log/mongodb/{{ mongodb_daemon_name }}.log"

## operationProfiling options
mongodb_operation_profiling_slow_op_threshold_ms: 100
mongodb_operation_profiling_mode: "off"

## replication options
mongodb_replication_replset: "" # Nonempty replica set name enables replication.
mongodb_replication_oplogsize: 1024 # Oplog size in MB.
mongodb_master: false # Enable on the node that manages the replica set.
mongodb_replication_params: [] # Complete member list, configured on that node.

## setParameter options
mongodb_set_parameters: {}

## Extend individual configuration sections with YAML lines.
mongodb_config: {}

## MongoDB Exporter
mongodb_exporter_install: false
mongodb_exporter_version: "0.43.1"
mongodb_exporter_name: exporter
mongodb_exporter_password: ""
mongodb_exporter_web_listen_address: ":9216"
mongodb_exporter_uri: "mongodb://{{ mongodb_login_host }}:{{ mongodb_login_port }}/?authSource=admin"
mongodb_exporter_collectors:
  - --collector.diagnosticdata
  - --collector.dbstats
# Architecture is derived from ansible_facts: x86_64 -> amd64, aarch64 -> arm64.
# mongodb_exporter_arch: amd64
# The download URL is derived from the version and architecture by default.
# mongodb_exporter_download_url: https://example.org/mongodb_exporter.tar.gz
mongodb_exporter_checksum: "" # Optional checksum accepted by get_url, e.g. sha256:<digest>.

## MMS monitoring agent
# Set mongodb_mms_agent_pkg to the appropriate package URL for your platform.
mongodb_mms_group_id: ""
mongodb_mms_api_key: "" # A nonempty value enables installation.
mongodb_mms_base_url: https://mms.mongodb.com
```

The role creates the data and log directories and manages their ownership without
recursively changing ownership of existing database files. When moving existing
data, ensure that the files already belong to `mongodb_user`.

`mongodb_config` appends YAML lines to the supported configuration sections:
`net`, `processManagement`, `replication`, `security`, `storage`, `systemLog`, and
`operationProfiling`. For example:

```yaml
mongodb_set_parameters:
  ttlMonitorSleepSecs: 30

mongodb_config:
  net:
    - "compression: {compressors: snappy}"
```

#### Usage

Add `ansible-role-mongodb` to your playbook and define the desired settings in
inventory:

```yaml
---
- name: Deploy MongoDB
  hosts: mongo
  become: true
  roles:
    - ansible-role-mongodb
```

The repository's deployment playbook accepts a host pattern through
`selected_hosts`. Run it from the repository root:

```sh
ansible-playbook -i inventory/dev_test_inv.yml deploy-mongodb.yml \
  -e selected_hosts=mongo --vault-password-file /path/to/vault-password
```

Example vars for authorization:

```yaml
mongodb_security_authorization: enabled
mongodb_root_admin_name: root
mongodb_root_admin_password: "{{ vault_mongodb_root_admin_password }}"
mongodb_users:
  - name: app_user
    database: app_development
    password: "{{ vault_mongodb_app_password }}"
    roles:
      - role: readWrite
        db: app_development
    update_password: on_create
```

The first administrator is created through MongoDB's localhost exception without
turning authorization off. Initial creation requires a local connection from the
managed host. On an initialized database, the supplied administrator credentials
must already be valid; the role does not reset an existing administrator's
password after a failed login. To rotate that password, change it using valid
existing credentials and then update the inventory secret.

Database users accept `name`, `database`, `password`, `roles`, and the optional
`state` and `update_password` fields. `on_create` preserves an existing password;
`always` applies the supplied password on each run. Per-user settings override
`mongodb_user_update_password`. To remove a user:

```yaml
mongodb_users:
  - name: obsolete_user
    database: app_development
    state: absent
```

Example vars for an oplog reader, created in `admin` when replication is enabled:

```yaml
mongodb_oplog_users:
  - user: oplog_reader
    password: "{{ vault_mongodb_oplog_password }}"
```

Required secrets for an authenticated deployment:

```yaml
mongodb_root_admin_password: "{{ vault_mongodb_root_admin_password }}"

# All members of an authenticated replica set must use the same key.
mongodb_keyfile_content: "{{ vault_mongodb_keyfile }}"

# Required when the exporter is enabled.
mongodb_exporter_password: "{{ vault_mongodb_exporter_password }}"
```

Store these values and database user passwords in Ansible Vault. The role manages
the root administrator, explicitly requested `mongodb_users`, and oplog readers;
it does not automatically create separate user-administrator or backup accounts.

Example vars for replication, shared by all replica set nodes:

```yaml
mongodb_replication_replset: rs0
mongodb_net_bindip: "0.0.0.0"
mongodb_security_authorization: enabled
mongodb_root_admin_password: "{{ vault_mongodb_root_admin_password }}"
mongodb_keyfile_content: "{{ vault_mongodb_keyfile }}"
```

Configure the complete membership list on the node with `mongodb_master: true`:

```yaml
mongodb_master: true
mongodb_replication_params:
  - host_name: mongo1.example.internal
    host_port: 27017
    priority: 2
  - host_name: mongo2.example.internal
    host_port: 27017
  - host_name: mongo3.example.internal
    host_port: 27017
```

Each member accepts `host_name`, `host_port`, `host_type` (`replica` or `arbiter`),
`priority`, `votes`, `hidden`, and `build_indexes`. Port defaults to
`mongodb_net_port`. Arbiters and hidden members default to priority zero; other
members default to priority one.

And an example inventory file for the replica set:

```ini
[mongo_master]
mongo1.example.internal mongodb_master=true

[mongo_replicas]
mongo2.example.internal
mongo3.example.internal

[mongo:children]
mongo_master
mongo_replicas

[mongo:vars]
ansible_python_interpreter=/usr/bin/python3
```

`mongodb_master` selects the node on which the role manages membership and users;
it does not permanently assign the MongoDB PRIMARY. Run the role against all
members so that their services are configured before initialization. Member names
must resolve between nodes. Apply membership changes one member at a time per
run, following the collection module's reconfiguration constraints. Management
connections must reach the current writable primary when changing an existing
replica set or its users.

Example vars for MongoDB Exporter:

```yaml
mongodb_exporter_install: true
mongodb_exporter_name: exporter
mongodb_exporter_password: "{{ vault_mongodb_exporter_password }}"
mongodb_users:
  - name: "{{ mongodb_exporter_name }}"
    database: admin
    password: "{{ mongodb_exporter_password }}"
    roles:
      - role: clusterMonitor
        db: admin
      - role: read
        db: local
```

Define the exporter's database account in `mongodb_users`, including any
additional permissions required by your enabled collectors. The exporter runs as
a dedicated system user. Credentials are stored in `/etc/mongodb_exporter.env`
with root ownership and mode `0600`. Releases are extracted into versioned
subdirectories of `/opt/mongodb_exporter`; `/usr/local/bin/mongodb_exporter`
selects the active binary through a symlink. Changed credentials, binaries, or
service configuration notify the exporter restart handler.

#### Testing

Molecule tests run against Docker containers using the repository's
`inventory/dev_test_inv.yml` and `deploy-mongodb.yml`. Install the controller
dependencies from [requirements.txt](requirements.txt) and the collections from
[molecule/requirements.yml](molecule/requirements.yml). The controller needs access
to Docker and the inventory's Vault password. Tests disable fact injection into
`ansible_*` variables.

Inside the project's Docker controller:

```sh
cd /workspace/roles/ansible-role-mongodb
export ANSIBLE_VAULT_PASSWORD_FILE=/run/vault-pass
molecule test -s default
molecule test -s bootstrap
molecule test -s cluster
molecule test -s no_auth
ANSIBLE_ROLES_PATH=/workspace/roles ansible-lint -c .ansible-lint .
```

- `default`: apply the deployment playbook to the existing `dev-test-mongo`
  container, check idempotence, and verify its inventory configuration. This
  scenario leaves the container running.
- `bootstrap`: install into a disposable container with a clean database,
  different ports and paths, and an exporter password containing special
  characters. Check restarts, password policies, role updates, and user removal.
- `cluster`: initialize an authenticated three-node replica set with a shared
  keyfile and check its primary, membership, and member health.
- `no_auth`: check authorization-disabled operation, a custom port, connection
  limits, WiredTiger cache size, and `setParameter` values.

Every scenario verifies idempotence and uses the system `python3-pymongo`
package. Verification checks the driver's system installation path and the
absence of a virtualenv, live server settings, authentication, user roles, CRUD,
service state, and permissions. Exporter-enabled scenarios also scrape
`mongodb_up` and diagnostic collector metrics. CRUD checks use and remove the
`ansible_molecule_smoke` database.

Disposable scenarios use the `chargers-ansible-test:ubuntu24` image and
`chargers-dev-test_downloads` Docker network by default. Override them through
`MONGODB_MOLECULE_IMAGE` and `MONGODB_MOLECULE_NETWORK`. These scenarios remove
their temporary containers at the end. See
[molecule/TEST_RESULTS.md](molecule/TEST_RESULTS.md) for recorded results.

Licensed under the GPLv2 License. See the [LICENSE.md](LICENSE.md) file for details.

#### Feedback, bug-reports, requests, ...

Issues and requests are [welcome](https://github.com/azhinu/ansible-role-mongodb/issues)!
