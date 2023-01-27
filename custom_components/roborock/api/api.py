"""The Roborock api."""
from __future__ import annotations

import asyncio
import base64
import binascii
import gzip
import hashlib
import hmac
import json
import logging
import math
import secrets
import struct
import threading
import time
from asyncio import Lock
from asyncio.exceptions import TimeoutError, CancelledError
from urllib.parse import urlparse

import aiohttp
import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from custom_components.roborock.api.containers import (
    UserData,
    HomeDataDevice,
    Status,
    CleanSummary,
    Consumable,
    DNDTimer,
    CleanRecord,
    HomeData,
    MultiMapsList,
)
from custom_components.roborock.api.exceptions import (
    RoborockException,
    CommandVacuumError,
    VacuumError,
    RoborockTimeout,
)
from custom_components.roborock.api.roborock_queue import RoborockQueue
from custom_components.roborock.api.typing import (
    RoborockDeviceInfo,
    RoborockDeviceProp,
    RoborockCommand,
)
from custom_components.roborock.api.util import run_in_executor

_LOGGER = logging.getLogger(__name__)
QUEUE_TIMEOUT = 4
MQTT_KEEPALIVE = 60


def md5hex(message: str):
    md5 = hashlib.md5()
    md5.update(message.encode())
    return md5.hexdigest()


def md5bin(message: str):
    md5 = hashlib.md5()
    md5.update(message.encode())
    return md5.digest()


def encode_timestamp(_timestamp: int):
    hex_value = f"{_timestamp:x}".zfill(8)
    return "".join(list(map(lambda idx: hex_value[idx], [5, 6, 3, 7, 1, 2, 0, 4])))


class PreparedRequest:
    def __init__(self, base_url: str, base_headers: dict = None):
        self.base_url = base_url
        self.base_headers = base_headers or {}

    async def request(
            self, method: str, url: str, params=None, data=None, headers=None
    ):
        _url = "/".join(s.strip("/") for s in [self.base_url, url])
        _headers = {**self.base_headers, **(headers or {})}
        async with aiohttp.ClientSession() as session:
            async with session.request(
                    method,
                    _url,
                    params=params,
                    data=data,
                    headers=_headers,
            ) as resp:
                return await resp.json()


COMMANDS_WITH_BINARY_RESPONSE = [
    RoborockCommand.GET_MAP_V1,
]


class RoborockMqttClient(mqtt.Client):
    _thread: threading.Thread

    def __init__(self, user_data: UserData, device_map: dict[str, RoborockDeviceInfo]):
        rriot = user_data.rriot
        self._mqtt_user = rriot.user
        self._mqtt_domain = rriot.domain
        self._hashed_user = md5hex(self._mqtt_user + ":" + self._mqtt_domain)[2:10]
        super().__init__(client_id=self._hashed_user, protocol=mqtt.MQTTv5)
        url = urlparse(rriot.reference.mqtt)
        self._mqtt_host = url.hostname
        self._mqtt_port = url.port
        self._mqtt_ssl = url.scheme == "ssl"
        if self._mqtt_ssl:
            super().tls_set()
        self._mqtt_password = rriot.password
        self._hashed_password = md5hex(self._mqtt_password + ":" + self._mqtt_domain)[16:]
        super().username_pw_set(self._hashed_user, self._hashed_password)
        self.device_map = device_map
        self._seq = 1
        self._random = 4711
        self._id_counter = 2
        self._salt = "TXdfu$jyZ#TZHsg4"
        self._endpoint = base64.b64encode(md5bin(self._mqtt_domain)[8:14]).decode()
        self._nonce = secrets.token_bytes(16)
        self._waiting_queue: dict[int, RoborockQueue] = {}
        self._mutex = Lock()
        self._last_device_msg_in = mqtt.time_func()
        self._last_mqtt_msg_in = mqtt.time_func()

    def __del__(self):
        self.sync_disconnect()

    @run_in_executor()
    async def on_connect(self, _client, _, __, rc, ___=None):
        connection_queue = self._waiting_queue.get(0)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            message = f"Failed to connect (rc: {rc})"
            _LOGGER.error(message)
            if connection_queue:
                await connection_queue.async_put(
                    (None, RoborockException(message)), timeout=QUEUE_TIMEOUT
                )
            return
        _LOGGER.info(f"Connected to mqtt {self._mqtt_host}:{self._mqtt_port}")
        topic = f"rr/m/o/{self._mqtt_user}/{self._hashed_user}/#"
        (result, mid) = self.subscribe(topic)
        if result != 0:
            message = f"Failed to subscribe (rc: {result})"
            _LOGGER.error(message)
            if connection_queue:
                await connection_queue.async_put(
                    (None, RoborockException(message)), timeout=QUEUE_TIMEOUT
                )
            return
        _LOGGER.info(f"Subscribed to topic {topic}")
        if connection_queue:
            await connection_queue.async_put((True, None), timeout=QUEUE_TIMEOUT)

    @run_in_executor()
    async def on_message(self, _client, _, msg, __=None):
        try:
            device_id = msg.topic.split("/").pop()
            self._last_device_msg_in = mqtt.time_func()
            data = self._decode_msg(msg.payload, self.device_map[device_id].device)
            protocol = data.get("protocol")
            if protocol == 102:
                payload = json.loads(data.get("payload").decode())
                for data_point_number, data_point in payload.get("dps").items():
                    if data_point_number == "102":
                        data_point_response = json.loads(data_point)
                        request_id = data_point_response.get("id")
                        queue = self._waiting_queue.get(request_id)
                        if queue:
                            if queue.protocol == protocol:
                                error = data_point_response.get("error")
                                if error:
                                    await queue.async_put(
                                        (
                                            None,
                                            VacuumError(
                                                error.get("code"), error.get("message")
                                            ),
                                        ),
                                        timeout=QUEUE_TIMEOUT,
                                    )
                                else:
                                    result = data_point_response.get("result")
                                    if isinstance(result, list) and len(result) > 0:
                                        result = result[0]
                                    await queue.async_put(
                                        (result, None), timeout=QUEUE_TIMEOUT
                                    )
                        elif request_id < self._id_counter:
                            _LOGGER.debug(
                                f"id={request_id} Ignoring response: {data_point_response}"
                            )
                    elif data_point_number == "121":
                        _LOGGER.debug(f"Remote control {data_point}")
                    else:
                        _LOGGER.debug(
                            f"Unknown data point number received {data_point_number} with {data_point}"
                        )
            elif protocol == 301:
                payload = data.get("payload")[0:24]
                [endpoint, _, request_id, _] = struct.unpack("<15sBH6s", payload)
                if endpoint.decode().startswith(self._endpoint):
                    iv = bytes(AES.block_size)
                    decipher = AES.new(self._nonce, AES.MODE_CBC, iv)
                    decrypted = unpad(
                        decipher.decrypt(data.get("payload")[24:]), AES.block_size
                    )
                    decrypted = gzip.decompress(decrypted)
                    queue = self._waiting_queue.get(request_id)
                    if queue:
                        if isinstance(decrypted, list):
                            decrypted = decrypted[0]
                        await queue.async_put((decrypted, None), timeout=QUEUE_TIMEOUT)
        except Exception as ex:
            _LOGGER.exception(ex)

    @run_in_executor()
    async def on_disconnect(self, _client: mqtt.Client, _, rc, __=None):
        connection_queue = self._waiting_queue.get(1)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            message = f"Roborock mqtt client disconnected (rc: {rc})"
            _LOGGER.error(message)
            await self.async_disconnect()
            if connection_queue:
                await connection_queue.async_put(
                    (None, RoborockException(message)), timeout=QUEUE_TIMEOUT
                )
            return
        if connection_queue:
            await connection_queue.async_put(
                (True, None), timeout=QUEUE_TIMEOUT
            )

    @property
    def _last_msg_in(self):
        if self._last_mqtt_msg_in - self._last_device_msg_in > self._keepalive * 2:
            # Give up on retrying
            return self._last_mqtt_msg_in
        return self._last_device_msg_in

    @_last_msg_in.setter
    def _last_msg_in(self, value):
        self._last_mqtt_msg_in = value

    def sync_stop_loop(self):
        if self._thread:
            _LOGGER.info("Stopping mqtt loop")
            super().loop_stop()

    def sync_start_loop(self):
        if not self._thread or not self._thread.is_alive():
            self.sync_stop_loop()
            _LOGGER.info("Starting mqtt loop")
            super().loop_start()

    def sync_disconnect(self):
        rc = -1
        self.sync_stop_loop()
        if self.is_connected():
            _LOGGER.info("Disconnecting from mqtt")
            rc = super().disconnect()
            if rc != 0:
                raise RoborockException(f"Failed to disconnect (rc:{rc})")
            return rc == mqtt.MQTT_ERR_SUCCESS
        return rc == mqtt.MQTT_ERR_SUCCESS

    def sync_connect(self):
        rc = -1
        self.sync_start_loop()
        if not self.is_connected():
            _LOGGER.info("Connecting to mqtt")
            rc = super().connect(
                host=self._mqtt_host,
                port=self._mqtt_port,
                keepalive=MQTT_KEEPALIVE
            )
            if rc != mqtt.MQTT_ERR_SUCCESS:
                raise RoborockException(f"Failed to connect (rc:{rc})")
            return rc == mqtt.MQTT_ERR_SUCCESS
        return rc == mqtt.MQTT_ERR_SUCCESS

    async def _async_response(self, request_id: int, protocol_id: int = 0):
        try:
            queue = RoborockQueue(protocol_id)
            self._waiting_queue[request_id] = queue
            (response, err) = await queue.async_get(QUEUE_TIMEOUT)
            return response, err
        except (TimeoutError, CancelledError):
            raise RoborockTimeout(
                f"Timeout after {QUEUE_TIMEOUT} seconds waiting for response"
            ) from None
        finally:
            del self._waiting_queue[request_id]

    async def async_disconnect(self):
        async with self._mutex:
            disconnecting = self.sync_disconnect()
            if disconnecting:
                (response, err) = await self._async_response(1)
                if err:
                    raise RoborockException(err) from err
                return response

    async def async_connect(self):
        async with self._mutex:
            connecting = self.sync_connect()
            if connecting:
                (response, err) = await self._async_response(0)
                if err:
                    raise RoborockException(err) from err
                return response

    async def validate_connection(self):
        await self.async_connect()

    def _decode_msg(self, msg, device: HomeDataDevice):
        if msg[0:3] != "1.0".encode():
            raise RoborockException("Unknown protocol version")
        crc32 = binascii.crc32(msg[0: len(msg) - 4])
        expected_crc32 = struct.unpack_from("!I", msg, len(msg) - 4)
        if crc32 != expected_crc32[0]:
            raise RoborockException(f"Wrong CRC32 {crc32}, expected {expected_crc32}")

        [version, _seq, _random, timestamp, protocol, payload_len] = struct.unpack(
            "!3sIIIHH", msg[0:19]
        )
        [payload, expected_crc32] = struct.unpack_from(f"!{payload_len}sI", msg, 19)
        if crc32 != expected_crc32:
            raise RoborockException(f"Wrong CRC32 {crc32}, expected {expected_crc32}")

        aes_key = md5bin(encode_timestamp(timestamp) + device.local_key + self._salt)
        decipher = AES.new(aes_key, AES.MODE_ECB)
        decrypted_payload = unpad(decipher.decrypt(payload), AES.block_size)
        return {
            "version": version,
            "timestamp": timestamp,
            "protocol": protocol,
            "payload": decrypted_payload,
        }

    def _send_msg_raw(self, device_id, protocol, timestamp, payload):
        local_key = self.device_map[device_id].device.local_key
        aes_key = md5bin(encode_timestamp(timestamp) + local_key + self._salt)
        cipher = AES.new(aes_key, AES.MODE_ECB)
        encrypted = cipher.encrypt(pad(payload, AES.block_size))
        msg = struct.pack(
            "!3sIIIHH",
            "1.0".encode(),
            self._seq,
            self._random,
            timestamp,
            protocol,
            len(encrypted),
        )
        msg = msg[0:19] + encrypted
        crc32 = binascii.crc32(msg)
        msg += struct.pack("!I", crc32)
        info = self.publish(
            f"rr/m/i/{self._mqtt_user}/{self._hashed_user}/{device_id}", msg
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RoborockException(f"Failed to publish (rc: {info.rc})")

    async def send_command(
            self, device_id: str, method: RoborockCommand, params: list = None
    ):
        await self.validate_connection()
        timestamp = math.floor(time.time())
        request_id = self._id_counter
        self._id_counter = (self._id_counter + 1) % 32767
        inner = {
            "id": request_id,
            "method": method,
            "params": params or [],
            "security": {
                "endpoint": self._endpoint,
                "nonce": self._nonce.hex().upper(),
            },
        }
        payload = bytes(
            json.dumps(
                {
                    "t": timestamp,
                    "dps": {"101": json.dumps(inner, separators=(",", ":"))},
                },
                separators=(",", ":"),
            ).encode()
        )
        _LOGGER.debug(f"id={request_id} Requesting method {method} with {params}")
        request_protocol = 101
        response_protocol = 301 if method in COMMANDS_WITH_BINARY_RESPONSE else 102
        self._send_msg_raw(device_id, request_protocol, timestamp, payload)
        (response, err) = await self._async_response(request_id, response_protocol)
        if err:
            raise CommandVacuumError(method, err) from err
        if response_protocol == 301:
            _LOGGER.debug(
                f"id={request_id} Response from {method}: {len(response)} bytes"
            )
        else:
            _LOGGER.debug(f"id={request_id} Response from {method}: {response}")
        return response

    async def get_status(self, device_id: str) -> Status:
        status = await self.send_command(device_id, RoborockCommand.GET_STATUS)
        if isinstance(status, dict):
            return Status(status)

    async def get_dnd_timer(self, device_id: str) -> DNDTimer:
        dnd_timer = await self.send_command(device_id, RoborockCommand.GET_DND_TIMER)
        if isinstance(dnd_timer, dict):
            return DNDTimer(dnd_timer)

    async def get_clean_summary(self, device_id: str) -> CleanSummary:
        clean_summary = await self.send_command(
            device_id, RoborockCommand.GET_CLEAN_SUMMARY
        )
        if isinstance(clean_summary, dict):
            return CleanSummary(clean_summary)
        elif isinstance(clean_summary, bytes):
            return CleanSummary({"clean_time": clean_summary})

    async def get_clean_record(self, device_id: str, record_id: int) -> CleanRecord:
        clean_record = await self.send_command(
            device_id, RoborockCommand.GET_CLEAN_RECORD, [record_id]
        )
        if isinstance(clean_record, dict):
            return CleanRecord(clean_record)

    async def get_consumable(self, device_id: str) -> Consumable:
        consumable = await self.send_command(device_id, RoborockCommand.GET_CONSUMABLE)
        if isinstance(consumable, dict):
            return Consumable(consumable)

    async def get_prop(self, device_id: str):
        [status, dnd_timer, clean_summary, consumable] = await asyncio.gather(
            *[
                self.get_status(device_id),
                self.get_dnd_timer(device_id),
                self.get_clean_summary(device_id),
                self.get_consumable(device_id),
            ]
        )
        last_clean_record = None
        if clean_summary and clean_summary.records and len(clean_summary.records) > 0:
            last_clean_record = await self.get_clean_record(
                device_id, clean_summary.records[0]
            )
        if any([status, dnd_timer, clean_summary, consumable]):
            return RoborockDeviceProp(
                status, dnd_timer, clean_summary, consumable, last_clean_record
            )

    async def get_multi_maps_list(self, device_id):
        multi_maps_list = await self.send_command(
            device_id, RoborockCommand.GET_MULTI_MAPS_LIST
        )
        if isinstance(multi_maps_list, dict):
            return MultiMapsList(multi_maps_list)

    async def get_map_v1(self, device_id):
        return await self.send_command(device_id, RoborockCommand.GET_MAP_V1)


class RoborockClient:
    def __init__(self, username: str, base_url=None) -> None:
        """Sample API Client."""
        self._username = username
        self._default_url = "https://euiot.roborock.com"
        self.base_url = base_url
        self._device_identifier = secrets.token_urlsafe(16)

    async def _get_base_url(self):
        if not self.base_url:
            url_request = PreparedRequest(self._default_url)
            response = await url_request.request(
                "post",
                "/api/v1/getUrlByEmail",
                params={"email": self._username, "needtwostepauth": "false"},
            )
            if response.get("code") != 200:
                raise RoborockException(response.get("error"))
            self.base_url = response.get("data").get("url")
        return self.base_url

    def _get_header_client_id(self):
        md5 = hashlib.md5()
        md5.update(self._username.encode())
        md5.update(self._device_identifier.encode())
        return base64.b64encode(md5.digest()).decode()

    async def request_code(self):
        base_url = await self._get_base_url()
        header_clientid = self._get_header_client_id()
        code_request = PreparedRequest(base_url, {"header_clientid": header_clientid})

        code_response = await code_request.request(
            "post",
            "/api/v1/sendEmailCode",
            params={
                "username": self._username,
                "type": "auth",
            },
        )

        if code_response.get("code") != 200:
            raise RoborockException(code_response.get("msg"))

    async def pass_login(self, password: str):
        base_url = await self._get_base_url()
        header_clientid = self._get_header_client_id()

        login_request = PreparedRequest(base_url, {"header_clientid": header_clientid})
        login_response = await login_request.request(
            "post",
            "/api/v1/login",
            params={
                "username": self._username,
                "password": password,
                "needtwostepauth": "false",
            },
        )

        if login_response.get("code") != 200:
            raise RoborockException(login_response.get("msg"))
        return UserData(login_response.get("data"))

    async def code_login(self, code):
        base_url = await self._get_base_url()
        header_clientid = self._get_header_client_id()

        login_request = PreparedRequest(base_url, {"header_clientid": header_clientid})
        login_response = await login_request.request(
            "post",
            "/api/v1/loginWithCode",
            params={
                "username": self._username,
                "verifycode": code,
                "verifycodetype": "AUTH_EMAIL_CODE",
            },
        )

        if login_response.get("code") != 200:
            raise RoborockException(login_response.get("msg"))
        return UserData(login_response.get("data"))

    async def get_home_data(self, user_data: UserData):
        base_url = await self._get_base_url()
        header_clientid = self._get_header_client_id()
        rriot = user_data.rriot
        home_id_request = PreparedRequest(
            base_url, {"header_clientid": header_clientid}
        )
        home_id_response = await home_id_request.request(
            "get",
            "/api/v1/getHomeDetail",
            headers={"Authorization": user_data.token},
        )
        if home_id_response.get("code") != 200:
            raise RoborockException(home_id_response.get("msg"))
        home_id = home_id_response.get("data").get("rrHomeId")
        timestamp = math.floor(time.time())
        nonce = secrets.token_urlsafe(6)
        prestr = ":".join(
            [
                rriot.user,
                rriot.password,
                nonce,
                str(timestamp),
                hashlib.md5(("/user/homes/" + str(home_id)).encode()).hexdigest(),
                "",
                "",
            ]
        )
        mac = base64.b64encode(
            hmac.new(rriot.h_unknown.encode(), prestr.encode(), hashlib.sha256).digest()
        ).decode()
        home_request = PreparedRequest(
            rriot.reference.api,
            {
                "Authorization": f'Hawk id="{rriot.user}", s="{rriot.password}", ts="{timestamp}", nonce="{nonce}", '
                                 f'mac="{mac}"',
            },
        )
        home_response = await home_request.request("get", "/user/homes/" + str(home_id))
        if not home_response.get("success"):
            raise RoborockException(home_response)
        home_data = home_response.get("result")
        return HomeData(home_data)
