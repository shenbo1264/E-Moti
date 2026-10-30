import sqlite3

import pytest

from guanghe_companion.host_auth import DeviceCredentials, AuthenticationError


def test_pairing_is_one_use_persistent_and_server_bound(tmp_path):
    path = tmp_path / "devices.sqlite3"
    auth = DeviceCredentials(path)
    invite = auth.invite(owner_id="local_user", character_ids=["xingxi_pixel_pet"], now=10)
    result = auth.pair(invite, device_name="phone", now=11)
    identity = DeviceCredentials(path).authenticate(result["access_token"], now=12)
    assert identity.owner_id == "local_user"
    assert identity.character_ids == ("xingxi_pixel_pet",)
    with pytest.raises(AuthenticationError):
        auth.pair(invite, device_name="other", now=12)
    with sqlite3.connect(path) as db:
        assert result["access_token"] not in repr(db.execute("SELECT * FROM devices").fetchall())
    auth.revoke(identity.device_id)
    with pytest.raises(AuthenticationError):
        auth.authenticate(result["access_token"], now=13)


def test_expired_invitation_and_credential_rejected(tmp_path):
    auth = DeviceCredentials(tmp_path / "devices.sqlite3")
    invite = auth.invite(owner_id="local_user", character_ids=["xingxi_pixel_pet"], now=10)
    with pytest.raises(AuthenticationError):
        auth.pair(invite, device_name="phone", now=311)
    invite = auth.invite(owner_id="local_user", character_ids=["xingxi_pixel_pet"], now=400)
    result = auth.pair(invite, device_name="phone", now=401)
    with pytest.raises(AuthenticationError):
        auth.authenticate(result["access_token"], now=result["expires_at"])
    with pytest.raises(AuthenticationError):
        auth.authenticate("untrusted", now=402)


def test_list_devices_exposes_status_without_secrets(tmp_path):
    auth = DeviceCredentials(tmp_path / "devices.sqlite3")
    first = auth.pair(auth.invite(owner_id="local_user", character_ids=["xingxi_pixel_pet"], now=10),
                      device_name="phone-a", now=11)
    second = auth.pair(auth.invite(owner_id="local_user", character_ids=["xingxi_pixel_pet"], now=20),
                       device_name="phone-b", now=21)
    auth.pair(auth.invite(owner_id="other_user", character_ids=["xingxi_pixel_pet"], now=30),
              device_name="foreign", now=31)
    auth.revoke(second["device_id"])
    devices = auth.list_devices(owner_id="local_user", now=40)
    assert [d["name"] for d in devices] == ["phone-b", "phone-a"]
    assert devices[0]["status"] == "revoked"
    assert devices[1] == {"device_id": first["device_id"], "name": "phone-a", "status": "active",
                          "paired_at": 11, "expires_at": first["expires_at"],
                          "character_ids": ["xingxi_pixel_pet"]}
    assert auth.list_devices(owner_id="local_user", now=first["expires_at"])[1]["status"] == "expired"
    assert first["access_token"] not in repr(devices)
