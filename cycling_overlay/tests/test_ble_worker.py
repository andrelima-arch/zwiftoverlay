import asyncio
import sys
import types
from types import SimpleNamespace

from app.sensors.ble_worker import (
    CSC_MEASUREMENT_UUID,
    FTMS_INDOOR_BIKE_DATA_UUID,
    HR_MEASUREMENT_UUID,
    POWER_MEASUREMENT_UUID,
    BleWorker,
)


def _install_bleak(monkeypatch, scanner=None, client=None) -> None:
    bleak = types.ModuleType("bleak")
    if scanner:
        bleak.BleakScanner = scanner
    if client:
        bleak.BleakClient = client
    monkeypatch.setitem(sys.modules, "bleak", bleak)


def _collect_scan(worker: BleWorker) -> tuple[list[tuple[str, str, list]], list[tuple[str, str]], list[bool]]:
    results = []
    statuses = []
    finished = []
    worker.scan_result.connect(lambda address, name, services: results.append((address, name, services)))
    worker.connection_status.connect(lambda address, status: statuses.append((address, status)))
    worker.scan_finished.connect(lambda: finished.append(True))
    return results, statuses, finished


def _collect_statuses(worker: BleWorker) -> list[tuple[str, str]]:
    statuses = []
    worker.connection_status.connect(lambda address, status: statuses.append((address, status)))
    return statuses


def _collect_sensor_data(worker: BleWorker) -> list[dict]:
    data = []
    worker.sensor_data_changed.connect(lambda _, payload: data.append(payload))
    return data


def _services(*uuids: str):
    return SimpleNamespace(
        characteristics={
            uuid: SimpleNamespace(uuid=uuid)
            for uuid in uuids
        }
    )


class NotifyClient:
    def __init__(self):
        self.handler = None
        self.uuid = None

    async def start_notify(self, uuid, handler):
        self.uuid = uuid
        self.handler = handler


class MultiNotifyClient:
    def __init__(self):
        self.handlers = {}
        self.stopped = []
        self.disconnected = False
        self.is_connected = True

    async def start_notify(self, uuid, handler):
        self.handlers[uuid] = handler

    async def stop_notify(self, uuid):
        self.stopped.append(uuid)

    async def disconnect(self):
        self.disconnected = True
        self.is_connected = False


def test_scan_uses_advertisement_data_service_uuids(monkeypatch):
    device = SimpleNamespace(address="AA:BB", name=None)

    class Scanner:
        @staticmethod
        async def discover(timeout, return_adv=False):
            assert timeout == 10.0
            assert return_adv is True
            advertisement = SimpleNamespace(
                local_name="Trainer",
                service_uuids=["00001826-0000-1000-8000-00805f9b34fb"],
            )
            return {"AA:BB": (device, advertisement)}

    _install_bleak(monkeypatch, Scanner)
    worker = BleWorker()
    results, statuses, finished = _collect_scan(worker)

    asyncio.run(worker._do_scan())

    assert statuses == [("scanner", "Scanning...")]
    assert results == [("AA:BB", "Trainer", ["00001826-0000-1000-8000-00805f9b34fb"])]
    assert finished == [True]
    assert worker._discovered_devices == {"AA:BB": device}


def test_connect_uses_ble_device_from_scan_on_windows_backends(monkeypatch):
    device = SimpleNamespace(address="AA:BB", name="Trainer")

    class Scanner:
        @staticmethod
        async def discover(timeout, return_adv=False):
            advertisement = SimpleNamespace(
                local_name="Trainer",
                service_uuids=["00001826-0000-1000-8000-00805f9b34fb"],
            )
            return {"AA:BB": (device, advertisement)}

    class Client:
        instance = None

        def __init__(self, target, timeout=None):
            self.target = target
            self.timeout = timeout
            self.services = _services(FTMS_INDOOR_BIKE_DATA_UUID)
            self.notify_uuids = []
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def start_notify(self, uuid, handler):
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, Scanner, Client)
    worker = BleWorker()

    asyncio.run(worker._do_scan())
    asyncio.run(worker._do_connect("AA:BB", "ftms"))

    assert Client.instance.target is device
    assert Client.instance.timeout == 20.0
    assert Client.instance.notify_uuids == [FTMS_INDOOR_BIKE_DATA_UUID]


def test_connect_retries_transient_windows_cancelled_error(monkeypatch):
    class Client:
        instances = []

        def __init__(self, address, timeout=None):
            self.address = address
            self.timeout = timeout
            self.services = _services(FTMS_INDOOR_BIKE_DATA_UUID)
            self.notify_uuids = []
            self.disconnected = False
            Client.instances.append(self)

        async def connect(self):
            if len(Client.instances) == 1:
                raise OSError("[WinError -2147023673] A operação foi cancelada pelo usuário.")

        async def disconnect(self):
            self.disconnected = True

        async def start_notify(self, uuid, handler):
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("FE:60", "ftms"))

    assert statuses == [
        ("FE:60", "Connecting..."),
        ("FE:60", "Retrying connection... (1/2)"),
        ("FE:60", "Connected"),
    ]
    assert len(Client.instances) == 2
    assert Client.instances[0].disconnected is True
    assert Client.instances[1].notify_uuids == [FTMS_INDOOR_BIKE_DATA_UUID]


def test_connect_reports_actionable_windows_cancelled_error_after_retries(monkeypatch):
    class Client:
        def __init__(self, address, timeout=None):
            self.services = _services(FTMS_INDOOR_BIKE_DATA_UUID)

        async def connect(self):
            raise OSError("[WinError -2147023673] A operação foi cancelada pelo usuário.")

        async def disconnect(self):
            pass

        async def start_notify(self, uuid, handler):
            pass

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("FE:60", "ftms"))

    assert statuses[:3] == [
        ("FE:60", "Connecting..."),
        ("FE:60", "Retrying connection... (1/2)"),
        ("FE:60", "Retrying connection... (2/2)"),
    ]
    assert statuses[3][0] == "FE:60"
    assert statuses[3][1].startswith("Error: [WinError -2147023673]")
    assert "aceite qualquer prompt de pareamento do Windows" in statuses[3][1]


def test_scan_falls_back_to_legacy_metadata(monkeypatch):
    class Scanner:
        calls = 0

        @classmethod
        async def discover(cls, timeout, return_adv=False):
            cls.calls += 1
            if return_adv:
                raise TypeError("return_adv is unsupported")
            return [
                SimpleNamespace(
                    address="CC:DD",
                    name="Heart Belt",
                    metadata={"uuids": ["0000180d-0000-1000-8000-00805f9b34fb"]},
                )
            ]

    _install_bleak(monkeypatch, Scanner)
    worker = BleWorker()
    results, statuses, finished = _collect_scan(worker)

    asyncio.run(worker._do_scan())

    assert Scanner.calls == 2
    assert statuses == [("scanner", "Scanning...")]
    assert results == [("CC:DD", "Heart Belt", ["0000180d-0000-1000-8000-00805f9b34fb"])]
    assert finished == [True]


def test_scan_legacy_device_without_metadata_emits_empty_services(monkeypatch):
    class Scanner:
        @staticmethod
        async def discover(timeout, return_adv=False):
            if return_adv:
                raise TypeError("return_adv is unsupported")
            return [SimpleNamespace(address="EE:FF", name="Cadence Sensor")]

    _install_bleak(monkeypatch, Scanner)
    worker = BleWorker()
    results, statuses, finished = _collect_scan(worker)

    asyncio.run(worker._do_scan())

    assert statuses == [("scanner", "Scanning...")]
    assert results == [("EE:FF", "Cadence Sensor", [])]
    assert finished == [True]


def test_connect_power_device_with_ftms_characteristic_subscribes_ftms(monkeypatch):
    class Client:
        instance = None

        def __init__(self, address):
            self.address = address
            self.services = _services(FTMS_INDOOR_BIKE_DATA_UUID)
            self.notify_uuids = []
            self.disconnected = False
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            self.disconnected = True

        async def start_notify(self, uuid, handler):
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("AA:BB", "power"))

    assert statuses == [("AA:BB", "Connecting..."), ("AA:BB", "Connected")]
    assert Client.instance.notify_uuids == [FTMS_INDOOR_BIKE_DATA_UUID]
    assert Client.instance.disconnected is False
    assert "AA:BB" in worker._connected_clients


def test_connect_ftms_device_with_power_characteristic_falls_back_to_power(monkeypatch):
    class Client:
        instance = None

        def __init__(self, address):
            self.address = address
            self.services = _services(POWER_MEASUREMENT_UUID)
            self.notify_uuids = []
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def start_notify(self, uuid, handler):
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("CC:DD", "ftms"))

    assert statuses == [("CC:DD", "Connecting..."), ("CC:DD", "Connected")]
    assert Client.instance.notify_uuids == [POWER_MEASUREMENT_UUID]


def test_connect_trainer_subscribes_power_and_csc_when_both_available(monkeypatch):
    class Client:
        instance = None

        def __init__(self, address):
            self.address = address
            self.services = _services(POWER_MEASUREMENT_UUID, CSC_MEASUREMENT_UUID)
            self.notify_uuids = []
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def start_notify(self, uuid, handler):
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("DD:EE", "ftms"))

    assert statuses == [("DD:EE", "Connecting..."), ("DD:EE", "Connected")]
    assert Client.instance.notify_uuids == [POWER_MEASUREMENT_UUID, CSC_MEASUREMENT_UUID]


def test_connect_subscribes_all_supported_measurements_including_hr(monkeypatch):
    class Client:
        instance = None

        def __init__(self, address):
            self.address = address
            self.services = _services(FTMS_INDOOR_BIKE_DATA_UUID, HR_MEASUREMENT_UUID)
            self.notify_uuids = []
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def start_notify(self, uuid, handler):
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("12:34", "ftms"))

    assert statuses == [("12:34", "Connecting..."), ("12:34", "Connected")]
    assert Client.instance.notify_uuids == [FTMS_INDOOR_BIKE_DATA_UUID, HR_MEASUREMENT_UUID]


def test_connect_keeps_partial_connection_when_optional_subscription_fails(monkeypatch):
    class Client:
        instance = None

        def __init__(self, address):
            self.address = address
            self.services = _services(POWER_MEASUREMENT_UUID, CSC_MEASUREMENT_UUID)
            self.notify_uuids = []
            self.disconnected = False
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            self.disconnected = True

        async def start_notify(self, uuid, handler):
            if uuid == CSC_MEASUREMENT_UUID:
                raise RuntimeError("CSC unavailable")
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("DD:EE", "ftms"))

    assert statuses == [("DD:EE", "Connecting..."), ("DD:EE", "Connected")]
    assert Client.instance.notify_uuids == [POWER_MEASUREMENT_UUID]
    assert Client.instance.disconnected is False
    assert "DD:EE" in worker._connected_clients


def test_connect_without_supported_characteristic_errors_and_disconnects(monkeypatch):
    class Client:
        instance = None

        def __init__(self, address):
            self.address = address
            self.services = _services("00001234-0000-1000-8000-00805f9b34fb")
            self.notify_uuids = []
            self.disconnected = False
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            self.disconnected = True

        async def start_notify(self, uuid, handler):
            self.notify_uuids.append(uuid)

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("EE:FF", "power"))

    assert statuses[0] == ("EE:FF", "Connecting...")
    assert statuses[1][0] == "EE:FF"
    assert statuses[1][1].startswith("Error: No supported BLE measurement characteristic found")
    assert Client.instance.notify_uuids == []
    assert Client.instance.disconnected is True
    assert "EE:FF" not in worker._connected_clients


def test_connect_does_not_emit_connected_when_subscription_fails(monkeypatch):
    class Client:
        instance = None

        def __init__(self, address):
            self.address = address
            self.services = _services(POWER_MEASUREMENT_UUID)
            self.disconnected = False
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            self.disconnected = True

        async def start_notify(self, uuid, handler):
            raise RuntimeError("Characteristic was not found")

    _install_bleak(monkeypatch, client=Client)
    worker = BleWorker()
    statuses = _collect_statuses(worker)

    asyncio.run(worker._do_connect("11:22", "power"))

    assert statuses[0] == ("11:22", "Connecting...")
    assert all(status != ("11:22", "Connected") for status in statuses)
    assert statuses[1] == ("11:22", "Error: Characteristic was not found")
    assert Client.instance.disconnected is True
    assert "11:22" not in worker._connected_clients


def test_ftms_indoor_bike_data_reads_instant_cadence_and_power():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_ftms(client, "AA:BB"))
    flags = (1 << 2) | (1 << 6)
    packet = (
        flags.to_bytes(2, "little")
        + (2500).to_bytes(2, "little")
        + (180).to_bytes(2, "little")
        + (250).to_bytes(2, "little", signed=True)
    )
    client.handler(None, bytearray(packet))

    assert data == [{"cadence": 90, "power": 250}]


def test_ftms_indoor_bike_data_uses_average_cadence_when_instant_missing():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_ftms(client, "AA:BB"))
    flags = (1 << 3) | (1 << 6)
    packet = (
        flags.to_bytes(2, "little")
        + (2500).to_bytes(2, "little")
        + (176).to_bytes(2, "little")
        + (220).to_bytes(2, "little", signed=True)
    )
    client.handler(None, bytearray(packet))

    assert data == [{"cadence": 88, "power": 220}]


def test_power_measurement_calculates_cadence_from_crank_revolutions():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB"))
    flags = 1 << 5
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (100).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )
    second = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (101).to_bytes(2, "little")
        + (2024).to_bytes(2, "little")
    )

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(second))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}]


def test_power_measurement_thinkrider_calculates_cadence_from_wheel_revolutions():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB", {"compatibility_profile": "think_x"}))
    flags = 1 << 4
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
    )
    second = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
    )

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(second))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}]


def test_power_measurement_thinkrider_flags_0034_uses_wheel_when_crank_is_static():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB", {"compatibility_profile": "think_x"}))
    flags = (1 << 2) | (1 << 4) | (1 << 5)
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (50).to_bytes(2, "little")
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
        + (100).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )
    second = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (51).to_bytes(2, "little")
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
        + (100).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(second))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}]


def test_power_measurement_flags_0034_prefers_valid_crank_over_wheel():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB", {"compatibility_profile": "think_x"}))
    flags = (1 << 2) | (1 << 4) | (1 << 5)
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (50).to_bytes(2, "little")
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
        + (100).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )
    second = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (51).to_bytes(2, "little")
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
        + (101).to_bytes(2, "little")
        + (2024).to_bytes(2, "little")
    )

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(second))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}]


def test_power_measurement_qz_wheel_fallback_uses_tacxneo2_like_profile():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB", {"compatibility_profile": "tacxneo2_like"}))
    flags = 1 << 4
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
    )
    second = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
    )

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(second))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}]


def test_power_measurement_standard_device_does_not_invent_cadence_from_wheel_revolutions():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB"))
    flags = 1 << 4
    packet = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
    )

    client.handler(None, bytearray(packet))

    assert data == [{"power": 200}]


def test_power_measurement_uses_profile_resolved_from_scan_for_wheel_cadence(monkeypatch):
    device = SimpleNamespace(address="AA:BB", name=None)

    class Scanner:
        @staticmethod
        async def discover(timeout, return_adv=False):
            advertisement = SimpleNamespace(
                local_name="THINK X2MAX",
                service_uuids=["1818"],
            )
            return {"AA:BB": (device, advertisement)}

    class Client:
        instance = None

        def __init__(self, target, timeout=None):
            self.target = target
            self.timeout = timeout
            self.services = _services(POWER_MEASUREMENT_UUID)
            self.handlers = {}
            Client.instance = self

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def start_notify(self, uuid, handler):
            self.handlers[uuid] = handler

    _install_bleak(monkeypatch, Scanner, Client)
    worker = BleWorker()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._do_scan())
    asyncio.run(worker._do_connect("AA:BB", "power", {"address": "AA:BB"}))

    flags = 1 << 4
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
    )
    second = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
    )

    Client.instance.handlers[POWER_MEASUREMENT_UUID](None, bytearray(first))
    Client.instance.handlers[POWER_MEASUREMENT_UUID](None, bytearray(second))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}]


def test_power_measurement_flags_0034_uses_qz_wheel_when_crank_is_zero():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB", {"compatibility_profile": "think_x"}))
    flags = 0x0034
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (0).to_bytes(2, "little")
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
        + (10).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )
    second = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (0).to_bytes(2, "little")
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
        + (10).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(second))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}]


def test_power_measurement_retains_cadence_on_zero_power():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_power(client, "AA:BB", {"compatibility_profile": "think_x"}))
    flags = 0x0034
    first = (
        flags.to_bytes(2, "little")
        + (200).to_bytes(2, "little", signed=True)
        + (0).to_bytes(2, "little")
        + (100).to_bytes(4, "little")
        + (1000).to_bytes(2, "little")
        + (10).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )
    moving = (
        flags.to_bytes(2, "little")
        + (205).to_bytes(2, "little", signed=True)
        + (0).to_bytes(2, "little")
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
        + (10).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )
    stopped = (
        flags.to_bytes(2, "little")
        + (0).to_bytes(2, "little", signed=True)
        + (0).to_bytes(2, "little")
        + (101).to_bytes(4, "little")
        + (2024).to_bytes(2, "little")
        + (10).to_bytes(2, "little")
        + (1000).to_bytes(2, "little")
    )

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(moving))
    client.handler(None, bytearray(stopped))

    assert data == [{"power": 200}, {"power": 205, "cadence": 60}, {"power": 0, "cadence": 60}]


def test_power_measurement_logs_missing_cadence_diagnostic(caplog):
    worker = BleWorker()
    client = NotifyClient()

    asyncio.run(worker._subscribe_power(client, "AA:BB", {"compatibility_profile": "cycling_power"}))
    packet = (0).to_bytes(2, "little") + (200).to_bytes(2, "little", signed=True)

    with caplog.at_level("INFO", logger="app.sensors.ble_worker"):
        client.handler(None, bytearray(packet))

    assert "Cadence not emitted for AA:BB from power" in caplog.text
    assert "flags=0x0000" in caplog.text


def test_csc_measurement_calculates_cadence_from_crank_revolutions():
    worker = BleWorker()
    client = NotifyClient()
    data = _collect_sensor_data(worker)

    asyncio.run(worker._subscribe_csc(client, "AA:BB"))
    flags = 0x02
    first = bytes([flags]) + (100).to_bytes(2, "little") + (1000).to_bytes(2, "little")
    second = bytes([flags]) + (101).to_bytes(2, "little") + (2024).to_bytes(2, "little")

    client.handler(None, bytearray(first))
    client.handler(None, bytearray(second))

    assert data == [{"cadence": 60}]


def test_disconnect_stops_notifications_before_disconnect():
    worker = BleWorker()
    client = MultiNotifyClient()
    worker._connected_clients["AA:BB"] = client
    worker._notify_uuids["AA:BB"] = {POWER_MEASUREMENT_UUID, CSC_MEASUREMENT_UUID}

    asyncio.run(worker._do_disconnect("AA:BB"))

    assert set(client.stopped) == {POWER_MEASUREMENT_UUID, CSC_MEASUREMENT_UUID}
    assert client.disconnected is True
    assert "AA:BB" not in worker._connected_clients
