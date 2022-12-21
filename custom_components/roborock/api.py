# api.py
import asyncio
import base64
import binascii
import functools
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
from queue import Queue, Empty
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

_LOGGER = logging.getLogger(__name__)
QUEUE_TIMEOUT = 4

STATE_CODES = {
    1: "Starting",
    2: "Charger disconnected",
    3: "Idle",
    4: "Remote control active",
    5: "Cleaning",
    6: "Returning home",
    7: "Manual mode",
    8: "Charging",
    9: "Charging problem",
    10: "Paused",
    11: "Spot cleaning",
    12: "Error",
    13: "Shutting down",
    14: "Updating",
    15: "Docking",
    16: "Going to target",
    17: "Zoned cleaning",
    18: "Segment cleaning",
    22: "Emptying the bin",  # on s7+, see #1189
    23: "Washing the mop",  # on a46, #1435
    26: "Going to wash the mop",  # on a46, #1435
    100: "Charging complete",
    101: "Device offline",
}

FAN_SPEED_CODES = {
    105: "Off",
    101: "Silent",
    102: "Balanced",
    103: "Turbo",
    104: "Max",
    106: "Custom",
    108: "Max+"
}

MOP_MODE_CODES = {
    300: "Standard",
    301: "Deep",
    302: "Custom",
    303: "Deep+"
}

MOP_INTENSITY_CODES = {
    200: "Off",
    201: "Mild",
    202: "Moderate",
    203: "Intense",
    204: "Custom"
}

ERROR_CODES = {
    1: "LiDAR turret or laser blocked. Check for obstruction and retry.",
    2: "Bumper stuck. Clean it and lightly tap to release it.",
    3: "Wheels suspended. Move robot and restart.",
    4: "Cliff sensor error. Clean cliff sensors, move robot away from drops and restart.",
    5: "Main brush jammed. Clean main brush and bearings.",
    6: "Side brush jammed. Remove and clean side brush.",
    7: "Wheels iammed. Move the robot and restart.",
    8: "Robot trapped. Clear obstacles surrounding robot.",
    9: "No dustbin. Install dustbin and filter.",
    12: "Low battery. Recharge and retry.",
    13: "Charging error. Clean charging contacts and retry.",
    14: "Battery error.",
    15: "Wall sensor dirty. Clean wall sensor.",
    16: "Robot tilted. Move to level ground and restart.",
    17: "Side brush error. Reset robot.",
    18: "Fan error. Reset robot.",
    21: "Vertical bumper pressed. Move robot and retry.",
    22: "Dock locator error. Clean and retry.",
    23: "Could not return to dock. Clean dock location beacon and retry.",
    27: "VibraRise system jammed. Check for obstructions.",
    28: "Robot on carpet. Move robot to floor and retry.",
    29: "Filter blocked or wet. Clean, dry, and retry.",
    30: "No-go zone or Invisible Wall detected. Move robot from this area.",
    31: "Cannot cross carpet. Move robot across carpet and restart.",
    32: "Internal error. Reset the robot."
}

ATTR_STATE = "state"
ATTR_FAN_SPEED = "fan_power"
ATTR_MOP_MODE = "mop_mode"
ATTR_MOP_INTENSITY = "water_box_mode"
ATTR_ERROR_CODE = "error_code"


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
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            functools.partial(
                requests.request,
                method,
                _url,
                params=params,
                data=data,
                headers=_headers,
            ),
        )
        return response


class VacuumError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(self.message)


class CommandVacuumError(Exception):
    def __init__(self, command: str, vacuum_error: VacuumError):
        self.message = f'{command}: {str(vacuum_error)}'
        super().__init__(self.message)


class RoborockMqttClient:
    def __init__(self, rriot: dict, local_keys: dict):
        self._hashed_password = None
        self._hashed_user = None
        self.client: mqtt.Client = None
        self._seq = 1
        self._random = 4711
        self._id_counter = 1
        self._salt = "TXdfu$jyZ#TZHsg4"
        self._mqtt_user = rriot.get("u")
        self._mqtt_password = rriot.get("s")
        self._mqtt_domain = rriot.get("k")
        url = urlparse(rriot.get("r").get("m"))
        self._mqtt_host = url.hostname
        self._mqtt_port = url.port
        self._mqtt_ssl = url.scheme == "ssl"
        self._local_keys = local_keys
        self._endpoint = base64.b64encode(md5bin(self._mqtt_domain)[8:14]).decode()
        self._nonce = secrets.token_bytes(16)
        self._waiting_queue: dict[int, Queue] = {}

    def connect(self):
        self._hashed_user = md5hex(self._mqtt_user + ":" + self._mqtt_domain)[2:10]
        self._hashed_password = md5hex(self._mqtt_password + ":" + self._mqtt_domain)[
                                16:
                                ]
        client = mqtt.Client()

        def on_connect(_client: mqtt.Client, userdata, flags, rc):
            if rc != 0:
                raise Exception("Failed to connect.")
            _LOGGER.info(f'Connected to mqtt {self._mqtt_host}:{self._mqtt_port}')
            (result, mid) = _client.subscribe(
                f"rr/m/o/{self._mqtt_user}/{self._hashed_user}/#"
            )
            if result != 0:
                raise Exception("Failed to subscribe.")

        def on_message(_client, userdata, msg):
            try:
                device_id = msg.topic.split("/").pop()
                data = self._decode_msg(msg.payload, self._local_keys.get(device_id))
                if data.get('protocol') == 102:
                    payload = json.loads(data.get("payload").decode())
                    raw_dps = payload.get('dps').get("102")
                    if raw_dps is not None:
                        dps = json.loads(raw_dps)
                        request_id = dps.get("id")
                        queue = self._waiting_queue.get(request_id)
                        error = dps.get("error")
                        if queue is not None:
                            if error is not None:
                                queue.put(VacuumError(error.get("code"), error.get("message")), timeout=QUEUE_TIMEOUT)
                            else:
                                result = dps.get("result")
                                if isinstance(result, list):
                                    result = result[0]
                                if result != "ok":
                                    queue.put(result, timeout=QUEUE_TIMEOUT)
                elif data.get('protocol') == 301:
                    payload = data.get("payload")[0:24]
                    [endpoint, unknown1, request_id, unknown2] = struct.unpack(
                        "<15sBH6s", payload
                    )
                    if endpoint.decode().startswith(self._endpoint):
                        iv = bytes(AES.block_size)
                        decipher = AES.new(self._nonce, AES.MODE_CBC, iv)
                        decrypted = unpad(decipher.decrypt(data.get("payload")[24:]), AES.block_size)
                        decrypted = gzip.decompress(decrypted)
                        queue = self._waiting_queue[request_id]
                        if queue is not None:
                            if isinstance(decrypted, list):
                                decrypted = decrypted[0]
                            queue.put(decrypted)
                elif data.get('protocol') == 121:
                    _LOGGER.debug("Remote control")
            except Exception as e:
                _LOGGER.exception(e)

        def on_subscribe(_client, userdata, mid, granted_qos):
            _LOGGER.info("Roborock subscribed to mqtt")

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_subscribe = on_subscribe

        if self._mqtt_ssl:
            client.tls_set()
        client.username_pw_set(self._hashed_user, self._hashed_password)
        client.connect(host=self._mqtt_host, port=self._mqtt_port, keepalive=30)
        client.loop_start()
        self.client = client

    def _decode_msg(self, msg, local_key):
        if msg[0:3] != "1.0".encode():
            raise Exception("Unknown protocol version")
        crc32 = binascii.crc32(msg[0: len(msg) - 4])
        expected_crc32 = struct.unpack_from("!I", msg, len(msg) - 4)
        if crc32 != expected_crc32[0]:
            raise Exception(f"Wrong CRC32 {crc32}, expected {expected_crc32}")

        [version, _seq, _random, timestamp, protocol, payload_len] = struct.unpack(
            "!3sIIIHH", msg[0:19]
        )
        [payload, crc32] = struct.unpack_from(f"!{payload_len}sI", msg, 19)
        aes_key = md5bin(encode_timestamp(timestamp) + local_key + self._salt)
        decipher = AES.new(aes_key, AES.MODE_ECB)
        decrypted_payload = unpad(decipher.decrypt(payload), AES.block_size)
        return {'version': version, 'timestamp': timestamp, 'protocol': protocol, 'payload': decrypted_payload}

    def _send_msg_raw(self, device_id, protocol, timestamp, payload):
        local_key = self._local_keys.get(device_id)
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

    def send_request(self, device_id: str, method: str, params: list, secure=False):
        timestamp = math.floor(time.time())
        request_id = self._id_counter
        self._id_counter += 1
        inner = {"id": request_id, "method": method, "params": params or []}
        if secure:
            inner["security"] = {
                "endpoint": self._endpoint,
                "nonce": self._nonce.hex().upper(),
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
        _LOGGER.debug(f"Requesting method {method} with {params}")
        self._send_msg_raw(device_id, 101, timestamp, payload)
        queue = Queue()
        self._waiting_queue[request_id] = queue
        try:
            response = queue.get(timeout=QUEUE_TIMEOUT)
            if isinstance(response, bytes):
                _LOGGER.debug(f"Response from {method}: {len(response)} bytes")
            else:
                _LOGGER.debug(f"Response from {method}: {response}")
            if isinstance(response, VacuumError):
                raise CommandVacuumError(method, response)
            return response
        except Empty as e:
            return None


class RoborockClient:
    def __init__(self, username: str, password: str) -> None:
        """Sample API Client."""
        self._username = username
        self._password = password
        self.devices = []
        self._default_url = "https://euiot.roborock.com"
        self._mqtt_client: RoborockMqttClient = None

    async def _get_base_url(self):
        url_request = PreparedRequest(self._default_url)
        response = (
            await url_request.request(
                "post",
                "/api/v1/getUrlByEmail",
                params={"email": self._username, "needtwostepauth": "false"},
            )
        ).json()
        return response.get("data").get("url")

    async def login(self):
        # Scan for Roborock devices.
        base_url = await self._get_base_url()

        md5 = hashlib.md5()
        md5.update(self._username.encode())
        md5.update("should_be_unique".encode())
        header_clientid = base64.b64encode(md5.digest()).decode()

        login_request = PreparedRequest(base_url, {"header_clientid": header_clientid})

        user_data = (
            (
                await login_request.request(
                    "post",
                    "/api/v1/login",
                    params={
                        "username": self._username,
                        "password": self._password,
                        "needtwostepauth": "false",
                    },
                )
            )
            .json()
            .get("data")
        )

        rriot = user_data.get("rriot")

        home_id = (
            (
                await login_request.request(
                    "get",
                    "/api/v1/getHomeDetail",
                    headers={"Authorization": user_data.get("token")},
                )
            )
            .json()
            .get("data")
            .get("rrHomeId")
        )
        timestamp = math.floor(time.time())
        nonce = secrets.token_urlsafe(6)
        prestr = ":".join(
            [
                rriot.get("u"),
                rriot.get("s"),
                nonce,
                str(timestamp),
                hashlib.md5(("/user/homes/" + str(home_id)).encode()).hexdigest(),
                "",
                "",
            ]
        )
        mac = base64.b64encode(
            hmac.new(rriot.get("h").encode(), prestr.encode(), hashlib.sha256).digest()
        ).decode()
        home_request = PreparedRequest(
            rriot.get("r").get("a"),
            {
                "Authorization": f'Hawk id="{rriot.get("u")}", s="{rriot.get("s")}", ts="{timestamp}", nonce="{nonce}", '
                                 f'mac="{mac}"',
            },
        )
        home_data = (
            (await home_request.request("get", "/user/homes/" + str(home_id)))
            .json()
            .get("result")
        )
        self.devices = []
        for device in home_data.get("devices") + home_data.get("receivedDevices"):
            product = next(
                (product for product in home_data.get("products") if product.get("id") == device.get("productId")), {})
            device.update({"model": product.get("model")})
            self.devices.append(device)
        local_keys = {
            device.get("duid"): device.get("localKey") for device in self.devices
        }
        self._mqtt_client = RoborockMqttClient(rriot, local_keys)

    def connect_to_mqtt(self):
        if self._mqtt_client is not None:
            self._mqtt_client.connect()
        else:
            raise Exception("You need to login first")

    def send_request(self, device_id: str, method: str, params: list, secure=False):
        if self._mqtt_client is not None:
            return self._mqtt_client.send_request(device_id, method, params, secure)
        else:
            raise Exception("You need to login first")


async def main():
    logging.basicConfig()
    _LOGGER.setLevel(logging.INFO)
    client = RoborockClient(sys.argv[1], sys.argv[2])
    await client.login()
    client.connect_to_mqtt()
    status = client.send_request(client.devices[0].get("duid"), "get_status", [], True)
    print(status)


if __name__ == "__main__":
    asyncio.run(main())
