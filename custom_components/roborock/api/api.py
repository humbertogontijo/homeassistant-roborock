# api.py
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
import sys
import time
from asyncio import Lock
from asyncio.exceptions import TimeoutError
from urllib.parse import urlparse

import aiohttp
import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

from custom_components.roborock.api.containers import UserData, HomeDataDevice, Status, CleanSummary, Consumable, \
    DNDTimer, CleanRecord
from custom_components.roborock.api.roborock_queue import RoborockQueue
from custom_components.roborock.api.typing import RoborockDeviceInfo, RoborockDeviceProp
from custom_components.roborock.api.util import run_in_executor

_LOGGER = logging.getLogger(__name__)
QUEUE_TIMEOUT = 4
MQTT_KEEPALIVE = 60
SESSION_EXPIRY_INTERVAL = 1 * 60


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


class VacuumError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(self.message)


class CommandVacuumError(Exception):
    def __init__(self, command: str, vacuum_error: VacuumError):
        self.message = f"{command}: {str(vacuum_error)}"
        super().__init__(self.message)


class RoborockMqttClient:

    def __init__(self, user_data: UserData, device_map: dict[str, RoborockDeviceInfo]):
        self.device_map = device_map
        rriot = user_data.rriot
        self._seq = 1
        self._random = 4711
        self._id_counter = 1
        self._salt = "TXdfu$jyZ#TZHsg4"
        self._mqtt_user = rriot.user
        self._mqtt_password = rriot.password
        self._mqtt_domain = rriot.domain
        self._hashed_user = md5hex(self._mqtt_user + ":" + self._mqtt_domain)[2:10]
        self._hashed_password = md5hex(self._mqtt_password + ":" + self._mqtt_domain)[16:]
        url = urlparse(rriot.reference.mqtt)
        self._mqtt_host = url.hostname
        self._mqtt_port = url.port
        self._mqtt_ssl = url.scheme == "ssl"
        self._endpoint = base64.b64encode(md5bin(self._mqtt_domain)[8:14]).decode()
        self._nonce = secrets.token_bytes(16)
        self._waiting_queue: dict[int, RoborockQueue] = {}
        self.is_connected = False
        self.client = self._build_client()
        self._user_data = user_data
        self._first_connection = True
        self._last_message_timestamp = time.time()
        self._mutex = Lock()

    def _build_client(self) -> mqtt.Client:
        @run_in_executor()
        async def on_connect(_client: mqtt.Client, _, __, rc, ___=None):
            connection_queue = self._waiting_queue[0]
            if rc != 0:
                await connection_queue.async_put((None, Exception("Failed to connect.")), timeout=QUEUE_TIMEOUT)
            _LOGGER.info(f"Connected to mqtt {self._mqtt_host}:{self._mqtt_port}")
            self.is_connected = True
            topic = f"rr/m/o/{self._mqtt_user}/{self._hashed_user}/#"
            (result, mid) = _client.subscribe(topic)
            if result != 0:
                await connection_queue.async_put((None, Exception("Failed to subscribe.")), timeout=QUEUE_TIMEOUT)
            _LOGGER.info(f"Subscribed to topic {topic}")
            await connection_queue.async_put(({}, None), timeout=QUEUE_TIMEOUT)

        @run_in_executor()
        async def on_message(_client, _, msg, __=None):
            try:
                self._last_message_timestamp = time.time()
                device_id = msg.topic.split("/").pop()
                data = self._decode_msg(msg.payload, self.device_map[device_id].device)
                if data.get("protocol") == 102:
                    payload = json.loads(data.get("payload").decode())
                    for data_point_number, data_point in payload.get("dps").items():
                        if data_point_number == "102":
                            data_point_response = json.loads(data_point)
                            request_id = data_point_response.get("id")
                            queue = self._waiting_queue.get(request_id)
                            error = data_point_response.get("error")
                            if queue:
                                if error:
                                    await queue.async_put((None, VacuumError(error.get("code"), error.get("message"))),
                                                          timeout=QUEUE_TIMEOUT)
                                else:
                                    result = data_point_response.get("result")
                                    if isinstance(result, list) and len(result) > 0:
                                        result = result[0]
                                    if result != "ok":
                                        await queue.async_put((result, None), timeout=QUEUE_TIMEOUT)
                        elif data_point_number == "121":
                            _LOGGER.debug(f"Remote control {data_point}")
                        else:
                            _LOGGER.debug(f"Unknown data point number received {data_point_number} with {data_point}")
                elif data.get("protocol") == 301:
                    payload = data.get("payload")[0:24]
                    [endpoint, _, request_id, _] = struct.unpack(
                        "<15sBH6s", payload
                    )
                    if endpoint.decode().startswith(self._endpoint):
                        iv = bytes(AES.block_size)
                        decipher = AES.new(self._nonce, AES.MODE_CBC, iv)
                        decrypted = unpad(decipher.decrypt(data.get("payload")[24:]), AES.block_size)
                        decrypted = gzip.decompress(decrypted)
                        queue = self._waiting_queue.get(request_id)
                        if queue:
                            if isinstance(decrypted, list):
                                decrypted = decrypted[0]
                            await queue.async_put((decrypted, None), timeout=QUEUE_TIMEOUT)
            except Exception as exception:
                _LOGGER.exception(exception)

        @run_in_executor()
        async def on_disconnect(_client: mqtt.Client, _, rc, __=None):
            _LOGGER.error(f"Roborock mqtt client disconnected (rc: {rc})")
            self.disconnect()

        client = mqtt.Client(client_id=self._hashed_user, protocol=mqtt.MQTTv5)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect

        if self._mqtt_ssl:
            client.tls_set()
        client.username_pw_set(self._hashed_user, self._hashed_password)
        client.loop_start()
        return client

    def disconnect(self):
        self.is_connected = False

    async def _connect(self):
        connection_queue = RoborockQueue()
        self._waiting_queue[0] = connection_queue
        if not self._first_connection:
            _LOGGER.debug("Reconnecting to mqtt")
            self.client.reconnect()
        else:
            _LOGGER.debug("Connecting to mqtt")
            properties = Properties(PacketTypes.CONNECT)
            properties.SessionExpiryInterval = SESSION_EXPIRY_INTERVAL
            self.client.connect(host=self._mqtt_host, port=self._mqtt_port,
                                clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                                properties=properties,
                                keepalive=MQTT_KEEPALIVE)
        try:
            (_, err) = await connection_queue.async_get(timeout=QUEUE_TIMEOUT)
            if err:
                raise err
        except TimeoutError:
            raise Exception(f"Timeout after {QUEUE_TIMEOUT} seconds waiting for mqtt connection")
        finally:
            del self._waiting_queue[0]
        if self._first_connection:
            self._first_connection = False

    async def validate_connection(self):
        async with self._mutex:
            if not self.is_connected or time.time() - self._last_message_timestamp > SESSION_EXPIRY_INTERVAL:
                await self._connect()

    def _decode_msg(self, msg, device: HomeDataDevice):
        if msg[0:3] != "1.0".encode():
            raise Exception("Unknown protocol version")
        crc32 = binascii.crc32(msg[0: len(msg) - 4])
        expected_crc32 = struct.unpack_from("!I", msg, len(msg) - 4)
        if crc32 != expected_crc32[0]:
            raise Exception(f"Wrong CRC32 {crc32}, expected {expected_crc32}")

        [version, _seq, _random, timestamp, protocol, payload_len] = struct.unpack(
            "!3sIIIHH", msg[0:19]
        )
        [payload, expected_crc32] = struct.unpack_from(f"!{payload_len}sI", msg, 19)
        if crc32 != expected_crc32:
            raise Exception(f"Wrong CRC32 {crc32}, expected {expected_crc32}")

        aes_key = md5bin(encode_timestamp(timestamp) + device.local_key + self._salt)
        decipher = AES.new(aes_key, AES.MODE_ECB)
        decrypted_payload = unpad(decipher.decrypt(payload), AES.block_size)
        return {"version": version, "timestamp": timestamp, "protocol": protocol, "payload": decrypted_payload}

    def _send_msg_raw(self, device_id, protocol, timestamp, payload):
        local_key = self.device_map[device_id].device.local_key
        aes_key = md5bin(encode_timestamp(timestamp) + local_key + self._salt)
        cipher = AES.new(aes_key, AES.MODE_ECB)
        encrypted = cipher.encrypt(pad(payload, AES.block_size))
        msg = struct.pack("3s", "1.0".encode())
        msg += struct.pack("!I", self._seq)
        msg += struct.pack("!I", self._random)
        msg += struct.pack("!I", timestamp)
        msg += struct.pack("!H", protocol)
        msg += struct.pack("!H", len(encrypted))
        msg = msg[0:19] + encrypted
        crc32 = binascii.crc32(msg)
        msg += struct.pack("!I", crc32)
        info = self.client.publish(
            f"rr/m/i/{self._mqtt_user}/{self._hashed_user}/{device_id}", msg
        )
        if info.rc != 0:
            raise Exception("Failed to publish")

    async def send_command(self, device_id: str, method: str, params: list = None, no_response=False):
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
            }
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
        if no_response:
            self._send_msg_raw(device_id, 101, timestamp, payload)
            return
        queue = RoborockQueue()
        self._waiting_queue[request_id] = queue
        self._send_msg_raw(device_id, 101, timestamp, payload)
        try:
            (response, err) = await queue.async_get(QUEUE_TIMEOUT)
            if isinstance(response, bytes):
                _LOGGER.debug(f"id={request_id} Response from {method}: {len(response)} bytes")
            else:
                _LOGGER.debug(f"id={request_id} Response from {method}: {response}")
            if err:
                raise CommandVacuumError(method, err)
            return response
        except TimeoutError:
            _LOGGER.warning(f"Timeout after {QUEUE_TIMEOUT} seconds waiting for {method} response")
            return None
        finally:
            del self._waiting_queue[request_id]

    async def get_status(self, device_id: str) -> Status:
        status = await self.send_command(device_id, "get_status")
        if isinstance(status, dict):
            return Status(status)

    async def get_dnd_timer(self, device_id: str) -> DNDTimer:
        dnd_timer = await self.send_command(device_id, "get_dnd_timer")
        if isinstance(dnd_timer, dict):
            return DNDTimer(dnd_timer)

    async def get_clean_summary(self, device_id: str) -> CleanSummary:
        clean_summary = await self.send_command(device_id, "get_clean_summary")
        if isinstance(clean_summary, dict):
            return CleanSummary(clean_summary)

    async def get_clean_record(self, device_id: str, record_id: int) -> CleanRecord:
        clean_record = await self.send_command(device_id, "get_clean_record", [record_id])
        if isinstance(clean_record, dict):
            return CleanRecord(clean_record)

    async def get_consumable(self, device_id: str) -> Consumable:
        consumable = await self.send_command(device_id, "get_consumable")
        if isinstance(consumable, dict):
            return Consumable(consumable)

    async def get_prop(self, device_id: str):
        [status, dnd_timer, clean_summary, consumable] = await asyncio.gather(
            *[self.get_status(device_id), self.get_dnd_timer(device_id), self.get_clean_summary(device_id),
              self.get_consumable(device_id)])
        last_clean_record = None
        if clean_summary and clean_summary.records and len(clean_summary.records) > 0:
            last_clean_record = await self.get_clean_record(device_id, clean_summary.records[0])
        if any([status, dnd_timer, clean_summary, consumable]):
            return RoborockDeviceProp(status, dnd_timer, clean_summary, consumable, last_clean_record)


class RoborockClient:
    def __init__(self, username: str, base_url=None) -> None:
        """Sample API Client."""
        self._username = username
        self._default_url = "https://euiot.roborock.com"
        self.base_url = base_url
        self._last_ping = time.time()
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
                raise Exception(response.get("error"))
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
            raise Exception(code_response.get("msg"))

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
                "verifycodetype": "AUTH_EMAIL_CODE"
            },
        )

        if login_response.get("code") != 200:
            raise Exception(login_response.get("msg"))
        return UserData(login_response.get("data"))

    async def get_home_data(self, user_data: UserData):
        base_url = await self._get_base_url()
        header_clientid = self._get_header_client_id()
        rriot = user_data.rriot
        home_id_request = PreparedRequest(base_url, {"header_clientid": header_clientid})
        home_id_response = await home_id_request.request(
            "get",
            "/api/v1/getHomeDetail",
            headers={"Authorization": user_data.token},
        )
        if home_id_response.get("code") != 200:
            raise Exception(home_id_response.get("msg"))
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
            raise Exception(home_response)
        home_data = home_response.get("result")
        return home_data


async def main():
    logging.basicConfig()
    _LOGGER.setLevel(logging.INFO)
    client = RoborockClient(sys.argv[1])
    await client.request_code()
    code = input("Type the code sent to your email.\n")
    user_data = await client.code_login(int(code))
    home_data = await client.get_home_data(user_data)
    mqtt_client = RoborockMqttClient(user_data, home_data)
    status = await mqtt_client.send_command(next(iter(mqtt_client.device_map.values())).device.duid, "get_status")
    print(status)


if __name__ == "__main__":
    asyncio.run(main())
