import asyncio
import logging
import time

from app.core.events import Signal
from app.sensors.ble_parsers import (
    parse_csc_measurement,
    parse_ftms_indoor_bike_data,
    parse_heart_rate,
    parse_power_measurement,
    parse_rsc_measurement,
)
from app.sensors.compatibility import match_qz_profile

logger = logging.getLogger(__name__)

HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
POWER_MEASUREMENT_UUID = "00002a63-0000-1000-8000-00805f9b34fb"
CSC_SERVICE_UUID = "00001816-0000-1000-8000-00805f9b34fb"
CSC_MEASUREMENT_UUID = "00002a5b-0000-1000-8000-00805f9b34fb"
RSC_SERVICE_UUID = "00001814-0000-1000-8000-00805f9b34fb"
RSC_MEASUREMENT_UUID = "00002a53-0000-1000-8000-00805f9b34fb"
FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
FTMS_INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"

PUMP_INTERVAL_MS = 50
CONNECT_RETRIES = 2
CONNECT_RETRY_DELAY_SECONDS = 1.0
CONNECT_TIMEOUT_SECONDS = 20.0
CADENCE_RETENTION_SECONDS = 1.0

SERVICE_CHARACTERISTICS = {
    "ftms": FTMS_INDOOR_BIKE_DATA_UUID,
    "power": POWER_MEASUREMENT_UUID,
    "csc": CSC_MEASUREMENT_UUID,
    "rsc": RSC_MEASUREMENT_UUID,
    "hr": HR_MEASUREMENT_UUID,
}
CONNECT_PRIORITY = ("ftms", "power", "csc", "rsc", "hr")


class BleWorker:
    def __init__(self) -> None:
        self.sensor_data_changed = Signal(str, object)
        self.scan_result = Signal(str, str, list)
        self.connection_status = Signal(str, str)
        self.scan_finished = Signal()

        self._connected_clients: dict[str, object] = {}
        self._connecting_addresses: set[str] = set()
        self._discovered_devices: dict[str, object] = {}
        self._discovered_device_info: dict[str, dict[str, object]] = {}
        self._notify_uuids: dict[str, set[str]] = {}
        self._power_cadence_state: dict[str, tuple[int, int, float]] = {}
        self._power_wheel_cadence_state: dict[str, tuple[int, int, float]] = {}
        self._csc_cadence_state: dict[str, tuple[int, int, float]] = {}
        self._last_cadence_by_source: dict[tuple[str, str], tuple[int, float]] = {}
        self._last_cadence_diagnostic: dict[tuple[str, str], float] = {}
        self._last_cadence_source_log: dict[tuple[str, str], float] = {}
        self._disconnecting_addresses: set[str] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pump_id: str | None = None
        self._running = False
        self._stopped = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stopped = False
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._schedule_pump()

    def stop(self) -> None:
        self._running = False
        self._stopped = True
        self._cancel_pump()

        if self._loop and not self._loop.is_closed():
            try:
                self._loop.run_until_complete(self._disconnect_all())
                pending = [task for task in asyncio.all_tasks(self._loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception as exc:
                logger.debug("BLE worker shutdown error: %s", self._exception_message(exc))
            finally:
                self._loop.close()
            self._loop = None

    def request_scan(self) -> None:
        if self._loop and self._running:
            self._loop.create_task(self._do_scan())

    def request_connect(self, address: str, service: str, device_info: dict | None = None) -> bool:
        if self._loop and self._running:
            self._loop.create_task(self._do_connect(address, service, device_info))
            return True
        return False

    def request_disconnect(self, address: str) -> None:
        if self._loop and self._running:
            self._loop.create_task(self._do_disconnect(address))

    def request_disconnect_all(self) -> None:
        if self._loop and self._running:
            self._loop.create_task(self._disconnect_all())

    def _schedule_pump(self) -> None:
        from app.core.events import EventLoop
        self._pump_id = EventLoop.get().call_later(PUMP_INTERVAL_MS, self._pump_loop)

    def _cancel_pump(self) -> None:
        from app.core.events import EventLoop
        if self._pump_id:
            EventLoop.get().cancel(self._pump_id)
            self._pump_id = None

    def _pump_loop(self) -> None:
        if not self._running or not self._loop:
            return
        self._loop.call_soon(self._loop.stop)
        try:
            self._loop.run_forever()
        except Exception:
            pass
        self._schedule_pump()

    async def _do_scan(self) -> None:
        try:
            from bleak import BleakScanner
            self.connection_status.emit("scanner", "Scanning...")
            self._discovered_devices.clear()
            self._discovered_device_info.clear()
            try:
                discovered = await BleakScanner.discover(timeout=10.0, return_adv=True)
            except TypeError:
                discovered = await BleakScanner.discover(timeout=10.0)

            if isinstance(discovered, dict):
                for device, advertisement_data in discovered.values():
                    self._discovered_devices[str(device.address)] = device
                    name = device.name or getattr(advertisement_data, "local_name", None)
                    if name:
                        services = list(getattr(advertisement_data, "service_uuids", []) or [])
                        self._remember_discovered_info(device.address, name, services)
                        self.scan_result.emit(device.address, name, services)
            else:
                for device in discovered:
                    self._discovered_devices[str(device.address)] = device
                    name = device.name
                    if name:
                        metadata = getattr(device, "metadata", {}) or {}
                        services = list(metadata.get("uuids", []) or [])
                        self._remember_discovered_info(device.address, name, services)
                        self.scan_result.emit(device.address, name, services)
        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.connection_status.emit("scanner", f"Scan error: {e}")
        finally:
            self.scan_finished.emit()

    def _remember_discovered_info(self, address: str, name: str, services: list[str]) -> None:
        rule = match_qz_profile(name)
        self._discovered_device_info[str(address)] = {
            "address": str(address),
            "name": name or "",
            "services": list(services or []),
            "compatibility_profile": rule.profile if rule else "",
            "compatibility_hint": rule.hint if rule else "",
        }

    async def _do_connect(self, address: str, service: str, device_info: dict | None = None) -> None:
        if address in self._connected_clients or address in self._connecting_addresses:
            return
        self._connecting_addresses.add(address)
        client = None
        try:
            from bleak import BleakClient
            self.connection_status.emit(address, "Connecting...")
            client = await self._connect_client(BleakClient, address)
            characteristics = await self._get_characteristic_uuids(client)
            if device_info is None:
                device_info = {"address": address}
            else:
                device_info = {**device_info, "address": device_info.get("address") or address}
            device_info = self._resolve_device_info(device_info, characteristics)
            resolved_services = self._resolve_services_from_characteristics(characteristics, service)
            if not resolved_services:
                raise RuntimeError(self._unsupported_characteristics_message(characteristics))

            successful_services = []
            last_error = None
            self._connected_clients[address] = client
            for resolved_service in resolved_services:
                try:
                    await self._subscribe_service(client, address, resolved_service, device_info)
                    successful_services.append(resolved_service)
                except Exception as subscribe_error:
                    last_error = subscribe_error
                    logger.warning(
                        "Subscribe error for %s %s: %s",
                        address,
                        resolved_service,
                        self._exception_message(subscribe_error),
                    )
            if not successful_services:
                self._connected_clients.pop(address, None)
                if last_error:
                    raise last_error
                raise RuntimeError(self._unsupported_characteristics_message(characteristics))
            self.connection_status.emit(address, "Connected")

        except Exception as e:
            message = self._connect_error_message(e)
            logger.error(f"Connect error for {address}: {message}")
            if client:
                try:
                    await self._disconnect_client(address, client)
                except Exception:
                    pass
                self._connected_clients.pop(address, None)
            self.connection_status.emit(address, f"Error: {message}")
        finally:
            self._connecting_addresses.discard(address)

    async def _resolve_service(self, client, requested_service: str) -> str | None:
        services = await self._resolve_services(client, requested_service)
        return services[0] if services else None

    async def _resolve_services(self, client, requested_service: str) -> list[str]:
        characteristics = await self._get_characteristic_uuids(client)
        return self._resolve_services_from_characteristics(characteristics, requested_service)

    def _resolve_services_from_characteristics(self, characteristics: set[str], requested_service: str) -> list[str]:
        if not characteristics:
            return [requested_service] if requested_service in SERVICE_CHARACTERISTICS else []

        supported_services = [
            service
            for service in ("ftms", "power", "csc", "hr")
            if SERVICE_CHARACTERISTICS[service] in characteristics
        ]
        if supported_services:
            return supported_services

        if requested_service in SERVICE_CHARACTERISTICS:
            requested_uuid = SERVICE_CHARACTERISTICS[requested_service]
            if requested_uuid in characteristics:
                return [requested_service]

        for service in CONNECT_PRIORITY:
            if SERVICE_CHARACTERISTICS[service] in characteristics:
                return [service]
        return []

    def _unsupported_characteristics_message(self, characteristics: set[str]) -> str:
        found = ", ".join(sorted(characteristics)) if characteristics else "none"
        return f"No supported BLE measurement characteristic found (found: {found})"

    def _exception_message(self, exc: Exception) -> str:
        message = str(exc).strip()
        return message or exc.__class__.__name__

    async def _connect_client(self, bleak_client, address: str):
        last_error = None
        for attempt in range(CONNECT_RETRIES + 1):
            client = self._create_client(bleak_client, address)
            try:
                await client.connect()
                return client
            except Exception as exc:
                last_error = exc
                try:
                    await client.disconnect()
                except Exception:
                    pass
                if attempt >= CONNECT_RETRIES or not self._is_retryable_connect_error(exc):
                    raise
                self.connection_status.emit(address, f"Retrying connection... ({attempt + 1}/{CONNECT_RETRIES})")
                await asyncio.sleep(CONNECT_RETRY_DELAY_SECONDS)
        raise last_error or RuntimeError("BLE connect failed")

    def _create_client(self, bleak_client, address: str):
        target = self._discovered_devices.get(address, address)
        disconnected_callback = self._make_disconnected_callback(address)
        for kwargs in (
            {"timeout": CONNECT_TIMEOUT_SECONDS, "disconnected_callback": disconnected_callback},
            {"disconnected_callback": disconnected_callback},
            {"timeout": CONNECT_TIMEOUT_SECONDS},
            {},
        ):
            try:
                return bleak_client(target, **kwargs)
            except TypeError:
                continue
        return bleak_client(target)

    def _make_disconnected_callback(self, address: str):
        def callback(_client) -> None:
            self._handle_client_disconnected(address)

        return callback

    def _handle_client_disconnected(self, address: str) -> None:
        if self._stopped:
            return
        self._connected_clients.pop(address, None)
        self._connecting_addresses.discard(address)
        self._notify_uuids.pop(address, None)
        self._clear_device_state(address)
        if address in self._disconnecting_addresses:
            return
        self.connection_status.emit_safe(address, "Disconnected")

    def _is_retryable_connect_error(self, exc: Exception) -> bool:
        message = self._exception_message(exc).lower()
        return (
            "-2147023673" in message
            or "operation was canceled" in message
            or "operation cancelled" in message
            or "operação foi cancelada" in message
        )

    def _connect_error_message(self, exc: Exception) -> str:
        message = self._exception_message(exc)
        if self._is_retryable_connect_error(exc):
            return (
                f"{message}. O Windows cancelou a conexão BLE. Mantenha o rolo acordado, "
                "execute Scan novamente e aceite qualquer prompt de pareamento do Windows."
            )
        return message

    async def _get_characteristic_uuids(self, client) -> set[str]:
        services = getattr(client, "services", None)
        if services is None and hasattr(client, "get_services"):
            services = await client.get_services()

        uuids: set[str] = set()
        if services is None:
            return uuids

        characteristics = getattr(services, "characteristics", None)
        if isinstance(characteristics, dict):
            for characteristic in characteristics.values():
                self._add_characteristic_uuid(uuids, characteristic)
        elif characteristics:
            for characteristic in characteristics:
                self._add_characteristic_uuid(uuids, characteristic)

        try:
            service_iterable = services.values() if isinstance(services, dict) else services
            for service in service_iterable:
                for characteristic in getattr(service, "characteristics", []) or []:
                    self._add_characteristic_uuid(uuids, characteristic)
        except TypeError:
            pass

        return uuids

    def _add_characteristic_uuid(self, uuids: set[str], characteristic) -> None:
        uuid = getattr(characteristic, "uuid", characteristic)
        if uuid:
            uuids.add(str(uuid).lower())

    async def _subscribe_service(self, client, address: str, service: str, device_info: dict | None = None) -> None:
        if service == "hr":
            await self._subscribe_hr(client, address)
        elif service == "power":
            await self._subscribe_power(client, address, device_info)
        elif service == "csc":
            await self._subscribe_csc(client, address)
        elif service == "rsc":
            await self._subscribe_rsc(client, address)
        elif service == "ftms":
            await self._subscribe_ftms(client, address)
        else:
            raise RuntimeError(f"Unsupported BLE service type: {service}")

    async def _do_disconnect(self, address: str) -> None:
        client = self._connected_clients.pop(address, None)
        self._disconnecting_addresses.add(address)
        self._clear_device_state(address)
        if client:
            try:
                await self._disconnect_client(address, client)
            except Exception:
                pass
        self._disconnecting_addresses.discard(address)
        self.connection_status.emit(address, "Disconnected")

    async def _disconnect_all(self) -> None:
        for address, client in list(self._connected_clients.items()):
            self._disconnecting_addresses.add(address)
            self._clear_device_state(address)
            try:
                if getattr(client, "is_connected", True):
                    await self._disconnect_client(address, client)
            except Exception:
                pass
            self._disconnecting_addresses.discard(address)
            self.connection_status.emit(address, "Disconnected")
        self._connected_clients.clear()
        self._connecting_addresses.clear()

    async def _disconnect_client(self, address: str, client) -> None:
        for uuid in list(self._notify_uuids.get(address, set())):
            try:
                await client.stop_notify(uuid)
            except Exception as exc:
                logger.debug(
                    "Stop notify error for %s %s: %s",
                    address,
                    uuid,
                    self._exception_message(exc),
                )
        self._notify_uuids.pop(address, None)
        await client.disconnect()

    def _record_notify(self, address: str, uuid: str) -> None:
        self._notify_uuids.setdefault(address, set()).add(uuid)

    def _clear_device_state(self, address: str) -> None:
        self._power_cadence_state.pop(address, None)
        self._power_wheel_cadence_state.pop(address, None)
        self._csc_cadence_state.pop(address, None)
        self._clear_last_cadence(address)
        self._clear_cadence_diagnostics(address)

    def _is_address_active(self, address: str) -> bool:
        if self._stopped:
            return False
        if not self._running and not self._connected_clients:
            return True
        return address in self._connected_clients

    def _resolve_device_info(self, device_info: dict | None, characteristics: set[str]) -> dict:
        info = dict(device_info or {})
        discovered = self._discovered_device_info.get(str(info.get("address") or "")) or {}
        if not discovered and device_info and device_info.get("address"):
            discovered = self._discovered_device_info.get(str(device_info["address"])) or {}
        if not discovered:
            for address, details in self._discovered_device_info.items():
                if address == str(info.get("address", "")):
                    discovered = details
                    break
        for key in ("address", "name", "compatibility_profile", "compatibility_hint"):
            if not info.get(key) and discovered.get(key):
                info[key] = discovered[key]
        if not info.get("name"):
            address = str(info.get("address", ""))
            device = self._discovered_devices.get(address)
            name = getattr(device, "name", "") if device else ""
            if name:
                info["name"] = name
        if not info.get("compatibility_profile"):
            name = str(info.get("name") or "")
            rule = match_qz_profile(name)
            if rule:
                info["compatibility_profile"] = rule.profile
                info["compatibility_hint"] = info.get("compatibility_hint") or rule.hint
        if not info.get("service_type"):
            resolved = self._resolve_services_from_characteristics(characteristics, "ftms")
            if resolved:
                info["service_type"] = resolved[0]
        return info

    async def _subscribe_hr(self, client, address: str) -> None:
        def handler(_, data: bytearray) -> None:
            if not self._is_address_active(address):
                return
            hr = parse_heart_rate(data)
            if hr is not None:
                self.sensor_data_changed.emit(address, {"heart_rate": hr})

        await client.start_notify(HR_MEASUREMENT_UUID, handler)
        self._record_notify(address, HR_MEASUREMENT_UUID)

    async def _subscribe_power(self, client, address: str, device_info: dict | None = None) -> None:
        profile = ""
        if isinstance(device_info, dict):
            profile = str(device_info.get("compatibility_profile") or "")
        is_qz_wheel_fallback = profile in {"think_x", "tacxneo2_like"}

        def handler(_, data: bytearray) -> None:
            if not self._is_address_active(address):
                return
            measurement = parse_power_measurement(data)
            if measurement.power is not None:
                result = {"power": measurement.power}
                wheel_cadence = None
                crank_cadence = None
                stopped = measurement.power <= 0
                if (
                    measurement.has_wheel_data
                    and measurement.wheel_revs is not None
                    and measurement.wheel_event_time is not None
                    and is_qz_wheel_fallback
                ):
                    wheel_cadence = self._calculate_power_wheel_cadence(
                        address,
                        measurement.wheel_revs,
                        measurement.wheel_event_time,
                    )
                if (
                    measurement.has_crank_data
                    and measurement.crank_revs is not None
                    and measurement.crank_event_time is not None
                ):
                    cadence = self._calculate_power_cadence(
                        address,
                        measurement.crank_revs,
                        measurement.crank_event_time,
                    )
                    if self._is_valid_crank_cadence(cadence, wheel_cadence):
                        crank_cadence = cadence

                if stopped:
                    result["cadence"] = 0
                    self._clear_last_cadence(address)
                    self._record_cadence_source(address, "power_stop", 0)
                elif self._is_moving_cadence(crank_cadence):
                    result["cadence"] = crank_cadence
                    self._record_cadence_source(address, "power_crank", crank_cadence)
                elif self._is_moving_cadence(wheel_cadence):
                    result["cadence"] = wheel_cadence
                    self._record_cadence_source(address, "power_wheel_qz", wheel_cadence)
                if "cadence" not in result:
                    retained = self._recent_cadence(
                        address,
                        ("power_crank", "power_wheel_qz", "csc", "ftms"),
                        max_age_seconds=CADENCE_RETENTION_SECONDS,
                    )
                    if retained is not None:
                        result["cadence"] = retained
                    else:
                        self._log_missing_cadence(
                            address,
                            "power",
                            profile,
                            measurement.flags,
                            has_instant_cadence=False,
                            has_average_cadence=False,
                            has_crank_data=measurement.has_crank_data,
                            has_wheel_data=measurement.has_wheel_data,
                            truncated=measurement.truncated,
                        )
                self.sensor_data_changed.emit(address, result)

        await client.start_notify(POWER_MEASUREMENT_UUID, handler)
        self._record_notify(address, POWER_MEASUREMENT_UUID)

    def _calculate_power_cadence(self, address: str, crank_revs: int, event_time: int) -> int | None:
        now = time.monotonic()
        previous = self._power_cadence_state.get(address)
        self._power_cadence_state[address] = (crank_revs, event_time, now)
        if previous is None:
            return None

        previous_revs, previous_time, previous_seen = previous
        delta_revs = (crank_revs - previous_revs) & 0xFFFF
        delta_time = (event_time - previous_time) & 0xFFFF
        if delta_revs == 0 or delta_time == 0:
            if now - previous_seen >= 2.0:
                return 0
            return 0

        cadence = delta_revs * 1024 * 60 / delta_time
        return max(0, round(cadence))

    def _calculate_power_wheel_cadence(self, address: str, wheel_revs: int, event_time: int) -> int | None:
        now = time.monotonic()
        previous = self._power_wheel_cadence_state.get(address)
        self._power_wheel_cadence_state[address] = (wheel_revs, event_time, now)
        if previous is None:
            return None

        previous_revs, previous_time, previous_seen = previous
        delta_revs = (wheel_revs - previous_revs) & 0xFFFFFFFF
        delta_time = (event_time - previous_time) & 0xFFFF
        if delta_revs == 0 or delta_time == 0:
            if now - previous_seen >= 2.0:
                return 0
            return 0

        # QZ uses wheel revolutions as a ThinkRider/Tacx-like cadence fallback.
        cadence = delta_revs * 2048 * 60 / delta_time / 2
        return max(0, round(cadence))

    async def _subscribe_csc(self, client, address: str) -> None:
        def handler(_, data: bytearray) -> None:
            if not self._is_address_active(address):
                return
            measurement = parse_csc_measurement(data)
            result = {}
            if measurement.crank_revs is not None and measurement.crank_event_time is not None:
                cadence = self._calculate_csc_cadence(
                    address,
                    measurement.crank_revs,
                    measurement.crank_event_time,
                )
                if cadence is not None:
                    result["cadence"] = cadence
                    self._record_cadence_source(address, "csc", cadence)
            if result:
                self.sensor_data_changed.emit(address, result)

        await client.start_notify(CSC_MEASUREMENT_UUID, handler)
        self._record_notify(address, CSC_MEASUREMENT_UUID)

    async def _subscribe_rsc(self, client, address: str) -> None:
        def handler(_, data: bytearray) -> None:
            if not self._is_address_active(address):
                return
            measurement = parse_rsc_measurement(data)
            result: dict[str, int | float] = {}
            if measurement.cadence is not None:
                result["cadence"] = measurement.cadence
                self._record_cadence_source(address, "rsc", measurement.cadence)
            if measurement.speed_mps is not None:
                # Convert m/s to km/h for display
                result["speed"] = round(measurement.speed_mps * 3.6, 1)
            if result:
                self.sensor_data_changed.emit(address, result)

        await client.start_notify(RSC_MEASUREMENT_UUID, handler)
        self._record_notify(address, RSC_MEASUREMENT_UUID)

    def _calculate_csc_cadence(self, address: str, crank_revs: int, event_time: int) -> int | None:
        now = time.monotonic()
        previous = self._csc_cadence_state.get(address)
        self._csc_cadence_state[address] = (crank_revs, event_time, now)
        if previous is None:
            return None

        previous_revs, previous_time, previous_seen = previous
        delta_revs = (crank_revs - previous_revs) & 0xFFFF
        delta_time = (event_time - previous_time) & 0xFFFF
        if delta_revs == 0 or delta_time == 0:
            if now - previous_seen >= 2.0:
                return 0
            return 0

        cadence = delta_revs * 1024 * 60 / delta_time
        return max(0, round(cadence))

    async def _subscribe_ftms(self, client, address: str) -> None:
        def handler(_, data: bytearray) -> None:
            if not self._is_address_active(address):
                return
            measurement = parse_ftms_indoor_bike_data(data)
            result = measurement.values
            if "cadence" in result:
                self._record_cadence_source(address, "ftms", result["cadence"])
            if "power" in result and "cadence" not in result:
                if result["power"] <= 0:
                    result = {**result, "cadence": 0}
                    self._clear_last_cadence(address)
                    self._record_cadence_source(address, "ftms_stop", 0)
                else:
                    retained = self._recent_cadence(
                        address,
                        ("ftms", "csc", "power_crank", "power_wheel_qz"),
                        max_age_seconds=CADENCE_RETENTION_SECONDS,
                    )
                    if retained is not None:
                        result = {**result, "cadence": retained}
                    else:
                        self._log_missing_cadence(
                            address,
                            "ftms",
                            "",
                            measurement.flags,
                            has_instant_cadence=measurement.has_instant_cadence,
                            has_average_cadence=measurement.has_average_cadence,
                            has_crank_data=False,
                            has_wheel_data=False,
                            truncated=measurement.truncated,
                        )
            if result:
                self.sensor_data_changed.emit(address, result)

        await client.start_notify(FTMS_INDOOR_BIKE_DATA_UUID, handler)
        self._record_notify(address, FTMS_INDOOR_BIKE_DATA_UUID)

    def _is_valid_cadence(self, cadence: int | None) -> bool:
        return cadence is not None and 0 <= cadence <= 220

    def _is_moving_cadence(self, cadence: int | None) -> bool:
        return cadence is not None and 0 < cadence <= 220

    def _is_valid_crank_cadence(self, cadence: int | None, fallback_cadence: int | None) -> bool:
        if not self._is_valid_cadence(cadence):
            return False
        if cadence == 0:
            return False
        return True

    def _record_cadence_source(self, address: str, source: str, cadence: int) -> None:
        now = time.monotonic()
        self._last_cadence_by_source[(address, source)] = (cadence, now)
        if source.endswith("_stop"):
            logger.debug("Cadence emitted for %s from %s: rpm=%s", address, source, cadence)
            return
        key = (address, source)
        if now - self._last_cadence_source_log.get(key, 0) >= 10.0:
            self._last_cadence_source_log[key] = now
            logger.info("Cadence emitted for %s from %s: rpm=%s", address, source, cadence)

    def _recent_cadence(self, address: str, sources: tuple[str, ...], max_age_seconds: float = 2.5) -> int | None:
        now = time.monotonic()
        best: tuple[int, float] | None = None
        for source in sources:
            candidate = self._last_cadence_by_source.get((address, source))
            if not candidate:
                continue
            cadence, seen_at = candidate
            if now - seen_at > max_age_seconds:
                continue
            if best is None or seen_at > best[1]:
                best = (cadence, seen_at)
        return best[0] if best else None

    def _clear_last_cadence(self, address: str) -> None:
        for key in list(self._last_cadence_by_source):
            if key[0] == address:
                self._last_cadence_by_source.pop(key, None)
        for key in list(self._last_cadence_source_log):
            if key[0] == address:
                self._last_cadence_source_log.pop(key, None)

    def _log_missing_cadence(
        self,
        address: str,
        source: str,
        profile: str,
        flags: int,
        *,
        has_instant_cadence: bool,
        has_average_cadence: bool,
        has_crank_data: bool,
        has_wheel_data: bool,
        truncated: bool,
    ) -> None:
        key = (address, source)
        now = time.monotonic()
        if now - self._last_cadence_diagnostic.get(key, 0) < 10.0:
            return
        self._last_cadence_diagnostic[key] = now
        logger.info(
            "Cadence not emitted for %s from %s: profile=%s flags=0x%04x "
            "instant_cadence=%s avg_cadence=%s crank=%s wheel=%s truncated=%s subscribed=%s",
            address,
            source,
            profile or "none",
            flags,
            has_instant_cadence,
            has_average_cadence,
            has_crank_data,
            has_wheel_data,
            truncated,
            sorted(self._notify_uuids.get(address, set())),
        )

    def _clear_cadence_diagnostics(self, address: str) -> None:
        for key in list(self._last_cadence_diagnostic):
            if key[0] == address:
                self._last_cadence_diagnostic.pop(key, None)
