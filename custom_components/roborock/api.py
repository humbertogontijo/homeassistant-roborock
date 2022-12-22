# api.py
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
from queue import Queue, Empty
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

_LOGGER = logging.getLogger(__name__)
QUEUE_TIMEOUT = 4
MQTT_KEEPALIVE = 60

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

    def request(
            self, method: str, url: str, params=None, data=None, headers=None
    ):
        _url = "/".join(s.strip("/") for s in [self.base_url, url])
        _headers = {**self.base_headers, **(headers or {})}
        response = requests.request(
            method,
            _url,
            params=params,
            data=data,
            headers=_headers,
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
    def __init__(self, user_data: dict, home_data: dict):
        self.devices = []
        for device in home_data.get("devices") + home_data.get("receivedDevices"):
            product = next(
                (product for product in home_data.get("products") if product.get("id") == device.get("productId")), {})
            device.update({"model": product.get("model")})
            self.devices.append(device)
        local_keys = {
            device.get("duid"): device.get("localKey")
            for device in
            home_data.get("devices") + home_data.get("receivedDevices")
        }
        rriot = user_data.get("rriot")
        self.client: mqtt.Client = None
        self._seq = 1
        self._random = 4711
        self._id_counter = 1
        self._salt = "TXdfu$jyZ#TZHsg4"
        self._mqtt_user = rriot.get("u")
        self._mqtt_password = rriot.get("s")
        self._mqtt_domain = rriot.get("k")
        self._hashed_user = md5hex(self._mqtt_user + ":" + self._mqtt_domain)[2:10]
        self._hashed_password = md5hex(self._mqtt_password + ":" + self._mqtt_domain)[16:]
        url = urlparse(rriot.get("r").get("m"))
        self._mqtt_host = url.hostname
        self._mqtt_port = url.port
        self._mqtt_ssl = url.scheme == "ssl"
        self._local_keys = local_keys
        self._endpoint = base64.b64encode(md5bin(self._mqtt_domain)[8:14]).decode()
        self._nonce = secrets.token_bytes(16)
        self._waiting_queue: dict[int, Queue] = {}

    def disconnect(self):
        if self.client:
            self.client.disconnect()
            self.client.loop_stop()

    def connect(self):
        client = mqtt.Client()
        queue = Queue()
        def on_connect(_client: mqtt.Client, userdata, flags, rc):
            if rc != 0:
                queue.put((None, Exception("Failed to connect.")), timeout=QUEUE_TIMEOUT)
            _LOGGER.info(f'Connected to mqtt {self._mqtt_host}:{self._mqtt_port}')
            topic = f"rr/m/o/{self._mqtt_user}/{self._hashed_user}/#"
            (result, mid) = _client.subscribe(topic)
            if result != 0:
                queue.put((None, Exception("Failed to subscribe.")), timeout=QUEUE_TIMEOUT)
            queue.put(({}, None), timeout=QUEUE_TIMEOUT)
            _LOGGER.info(f'Subscribed to topic {topic}')

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
                                queue.put((None, VacuumError(error.get("code"), error.get("message"))),
                                          timeout=QUEUE_TIMEOUT)
                            else:
                                result = dps.get("result")
                                if isinstance(result, list):
                                    result = result[0]
                                if result != "ok":
                                    queue.put((result, None), timeout=QUEUE_TIMEOUT)
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
                            queue.put((decrypted, None))
                elif data.get('protocol') == 121:
                    _LOGGER.debug("Remote control")
            except Exception as e:
                _LOGGER.exception(e)

        def on_subscribe(_client, userdata, mid, granted_qos):
            _LOGGER.info("Roborock subscribed to mqtt")

        def on_disconnect(_client: mqtt.Client, userdata, rc):
            _LOGGER.error(f"Roborock mqtt client disconnected (rc: {rc})")

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_subscribe = on_subscribe
        client.on_disconnect = on_disconnect

        if self._mqtt_ssl:
            client.tls_set()
        client.username_pw_set(self._hashed_user, self._hashed_password)
        client.connect(host=self._mqtt_host, port=self._mqtt_port, keepalive=MQTT_KEEPALIVE)
        client.loop_start()
        self.client = client
        try:
            (_, err) = queue.get(timeout=QUEUE_TIMEOUT)
            if err:
                raise err
        except Empty as e:
            self.client.disconnect()
            raise Exception(f"Timeout after {QUEUE_TIMEOUT} seconds waiting for mqtt connection")

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
        queue = Queue()
        self._waiting_queue[request_id] = queue
        self._send_msg_raw(device_id, 101, timestamp, payload)
        try:
            (response, err) = queue.get(timeout=QUEUE_TIMEOUT)
            if isinstance(response, bytes):
                _LOGGER.debug(f"Response from {method}: {len(response)} bytes")
            else:
                _LOGGER.debug(f"Response from {method}: {response}")
            if err:
                raise CommandVacuumError(method, err)
            return response
        except Empty as e:
            _LOGGER.warning(f"Timeout after {QUEUE_TIMEOUT} seconds waiting for {method} response")
            return None


class RoborockClient:
    def __init__(self, username: str) -> None:
        """Sample API Client."""
        self._username = username
        self._default_url = "https://euiot.roborock.com"
        self._base_url = None
        self._last_ping = time.time()

    def _get_base_url(self):
        if self._base_url is None:
            url_request = PreparedRequest(self._default_url)
            response = url_request.request(
                "post",
                "/api/v1/getUrlByEmail",
                params={"email": self._username, "needtwostepauth": "false"},
            ).json()
            self._base_url = response.get("data").get("url")
        return self._base_url

    def _get_header_client_id(self):
        md5 = hashlib.md5()
        md5.update(self._username.encode())
        md5.update("should_be_unique".encode())
        return base64.b64encode(md5.digest()).decode()

    def request_code(self):
        base_url = self._get_base_url()
        header_clientid = self._get_header_client_id()
        code_request = PreparedRequest(base_url, {"header_clientid": header_clientid})

        code_response = (
            code_request.request(
                "post",
                "/api/v1/sendEmailCode",
                params={
                    "username": self._username,
                    "type": "auth",
                },
            )
            .json()
        )

        if code_response.get('code') != 200:
            raise Exception(code_response.get("msg"))

    def code_login(self, code):
        user_data = self._get_user_data(code)
        home_data = self._get_home_data(user_data)
        return {"user_data": user_data, "home_data": home_data}


    def _get_user_data(self, code):
        base_url = self._get_base_url()
        header_clientid = self._get_header_client_id()

        login_request = PreparedRequest(base_url, {"header_clientid": header_clientid})
        login_response = (
            login_request.request(
                "post",
                "/api/v1/loginWithCode",
                params={
                    "username": self._username,
                    "verifycode": code,
                    "verifycodetype": "AUTH_EMAIL_CODE"
                },
            )
            .json()
        )

        if login_response.get('code') != 200:
            raise Exception(login_response.get("msg"))
        return login_response.get("data")

    def _get_home_data(self, user_data):
        base_url = self._get_base_url()
        header_clientid = self._get_header_client_id()
        rriot = user_data.get("rriot")
        home_id_request = PreparedRequest(base_url, {"header_clientid": header_clientid})
        home_id_response = home_id_request.request(
            "get",
            "/api/v1/getHomeDetail",
            headers={"Authorization": user_data.get("token")},
        ).json()
        if home_id_response.get('code') != 200:
            raise Exception(home_id_response.get("msg"))
        home_id = home_id_response.get("data").get("rrHomeId")
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
        home_response = home_request.request("get", "/user/homes/" + str(home_id)).json()
        if not home_response.get('success'):
            raise Exception(home_response)
        home_data = home_response.get("result")
        return home_data


def main():
    logging.basicConfig()
    _LOGGER.setLevel(logging.INFO)
    client = RoborockClient(sys.argv[1])
    client.request_code()
    code = input('Type the code sent to your email.\n')
    login_data = client.code_login(int(code))
    user_data = login_data.get("user_data")
    home_data = login_data.get("home_data")
    mqtt_client = RoborockMqttClient(user_data, home_data)
    mqtt_client.connect()
    status = mqtt_client.send_request(mqtt_client.devices[0].get("duid"), "get_status", [], True)
    print(status)


if __name__ == "__main__":
    main()
