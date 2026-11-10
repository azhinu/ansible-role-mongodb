"""Exercise the live server without exposing inventory credentials."""
import json
import sys
from pathlib import Path
import pymongo
from pymongo import MongoClient
from pymongo.errors import OperationFailure

assert sys.prefix == sys.base_prefix, "PyMongo must use the system interpreter"
assert Path(pymongo.__file__).resolve().is_relative_to("/usr/lib/python3/dist-packages"), "PyMongo must come from the system package"
cfg = json.load(sys.stdin)
options = dict(host=cfg["host"], port=int(cfg["port"]), serverSelectionTimeoutMS=10000)
if cfg["authorization"] == "enabled":
    options.update(username=cfg["admin"], password=cfg["password"], authSource="admin")
client = MongoClient(**options)
assert client.admin.command("ping")["ok"] == 1, "MongoDB ping failed"
assert client.server_info()["version"].startswith(cfg["version"]), "MongoDB version differs"
live = client.admin.command("getCmdLineOpts")["parsed"]
assert live["net"]["port"] == int(cfg["port"]), "MongoDB port differs"
assert live["net"]["bindIp"] == cfg["bindip"], "MongoDB bind address differs"
assert live["storage"]["dbPath"] == cfg["dbpath"], "MongoDB database path differs"
assert live["systemLog"]["path"] == cfg["logpath"], "MongoDB log path differs"
assert live["security"]["authorization"] == cfg["authorization"], "MongoDB authorization differs"
assert live["net"]["maxIncomingConnections"] == int(cfg["maxconns"]), "MongoDB connection limit differs"
if cfg["cache_size"] is not None:
    assert live["storage"]["wiredTiger"]["engineConfig"]["cacheSizeGB"] == cfg["cache_size"], "WiredTiger cache size differs"
for parameter, expected in (cfg["parameters"] or {}).items():
    assert client.admin.command("getParameter", **{parameter: 1})[parameter] == expected, "MongoDB parameter differs"
if cfg["authorization"] == "enabled":
    anonymous = MongoClient(cfg["host"], int(cfg["port"]), serverSelectionTimeoutMS=5000)
    try:
        anonymous.admin.command("listDatabases")
    except OperationFailure as exc:
        assert exc.code == 13, "Unexpected anonymous access failure"
    else:
        raise AssertionError("Anonymous database access is allowed")
    finally:
        anonymous.close()
for user in cfg["users"]:
    info = client[user["database"]].command("usersInfo", user["name"])["users"]
    if user.get("state", "present") == "absent":
        assert not info, "Removed user still exists"
        continue
    assert len(info) == 1, "Requested user does not exist"
    roles = user["roles"]
    if isinstance(roles, str):
        roles = roles.split(",")
    expected = {(r, user["database"]) if isinstance(r, str) else (r["role"], r["db"]) for r in roles}
    assert {(r["role"], r["db"]) for r in info[0]["roles"]} == expected, "User roles differ"
    authenticated = MongoClient(cfg["host"], int(cfg["port"]), username=user["name"],
                                password=user["password"], authSource=user["database"],
                                serverSelectionTimeoutMS=5000)
    assert authenticated[user["database"]].command("connectionStatus")["authInfo"]["authenticatedUsers"], "User authentication failed"
    authenticated.close()
collection = client["ansible_molecule_smoke"]["crud"]
try:
    collection.replace_one({"_id": "role-test"}, {"_id": "role-test", "value": 42}, upsert=True)
    assert collection.find_one({"_id": "role-test"})["value"] == 42, "MongoDB read/write failed"
    assert collection.delete_one({"_id": "role-test"}).deleted_count == 1, "MongoDB delete failed"
finally:
    client.drop_database("ansible_molecule_smoke")
if cfg["replset"]:
    status = client.admin.command("replSetGetStatus")
    assert status["set"] == cfg["replset"], "Replica set name differs"
    assert sum(m["stateStr"] == "PRIMARY" for m in status["members"]) == 1, "Replica set has no primary"
    assert len(status["members"]) == len(cfg["members"]), "Replica set members differ"
    assert all(m["health"] == 1 for m in status["members"]), "Replica set member is unhealthy"
client.close()
print("MongoDB authentication, roles, configuration and CRUD verified")
