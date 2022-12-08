import base64
import binascii
import hashlib
import json
import math
import secrets
import struct
import time
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

userdata_filename = 'userdata.json'
homedata_filename = 'homedata.json'


def main():
    def on_connect(_client: mqtt.Client, userdata, flags, rc):
        if rc != 0:
            raise Exception("Failed to connect.")
        (result, mid) = _client.subscribe(f'rr/m/o/{rriot.get("u")}/{mqtt_user}/#')
        if result != 0:
            raise Exception("Failed to subscribe.")

    def on_message(_client, userdata, msg):
        device_id = msg.topic.split('/').pop()
        data = _decode_msg(msg.payload, local_keys.get(device_id))
        print(msg.topic + " " + str(data))

    def on_subscribe(_client, userdata, mid, granted_qos):
        device_id = devices[0].get('duid')
        send_request(device_id, 'get_prop', ['get_status'])
        # send_request(device_id, 'get_map_v1', [], True)
        # send_request(device_id, 'app_start', [], True)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_subscribe = on_subscribe

    url = urlparse(rriot.get('r').get('m'))
    if url.scheme == 'ssl':
        client.tls_set()
    client.username_pw_set(mqtt_user, mqtt_password)
    client.connect(
        host=url.hostname,
        port=url.port,
        keepalive=30
    )
    client.loop_forever()


def _decode_msg(msg, local_key):
    if msg[0:3] != '1.0'.encode():
        raise Exception('Unknown protocol version')
    crc32 = binascii.crc32(msg[0:len(msg) - 4])
    expected_crc32 = struct.unpack_from("!I", msg, len(msg) - 4)
    if crc32 != expected_crc32[0]:
        raise Exception(f'Wrong CRC32 {crc32}, expected {expected_crc32}')

    [version, _seq, _random, timestamp, protocol, payload_len] = struct.unpack('!3sIIIHH', msg[0:19])
    [payload, crc32] = struct.unpack_from(f'!{payload_len}sI', msg, 19)
    aes_key = md5bin(_encode_timestamp(timestamp) + local_key + salt)
    decipher = AES.new(aes_key, AES.MODE_ECB)
    decrypter_payload = decipher.decrypt(pad(payload, len(aes_key)))
    return json.loads(decrypter_payload[0:len(decrypter_payload) - 27].decode())


def _encode_timestamp(_timestamp: int):
    hex_value = f'{_timestamp:x}'.zfill(8)
    return ''.join(list(map(lambda idx: hex_value[idx], [5, 6, 3, 7, 1, 2, 0, 4])))


def send_msg_raw(device_id, protocol, _timestamp, payload):
    global seq
    global random
    local_key = local_keys.get(device_id)
    aes_key = md5bin(_encode_timestamp(_timestamp) + local_key + salt)
    cipher = AES.new(aes_key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(payload, len(aes_key)))
    msg = struct.pack('3s', '1.0'.encode())
    msg += struct.pack('!I', seq)
    msg += struct.pack('!I', random)
    msg += struct.pack('!I', _timestamp)
    msg += struct.pack('!H', protocol)
    msg += struct.pack('!H', len(encrypted))
    msg = msg[0:19] + encrypted
    crc32 = binascii.crc32(msg)
    msg += struct.pack('!I', crc32)
    info = client.publish(f'rr/m/i/{rriot.get("u")}/{mqtt_user}/{device_id}', msg)
    if info.rc != 0:
        raise Exception("Failed to publish")


def send_request(device_id, method, params, secure=False):
    global id_counter
    _timestamp = math.floor(time.time())
    request_id = id_counter
    id_counter += 1
    inner = {'id': request_id, 'method': method, 'params': params}
    if secure:
        inner.security = {endpoint: endpoint, nonce: f'{nonce:x}'.upper()}
    payload = bytes(json.dumps({'t': _timestamp, 'dps': {'101': json.dumps(inner, separators=(',', ':'))}},
                               separators=(',', ':')).encode())
    send_msg_raw(device_id, 101, _timestamp, payload)


def md5hex(message: str):
    md5 = hashlib.md5()
    md5.update(message.encode())
    return md5.hexdigest()


def md5bin(message: str):
    md5 = hashlib.md5()
    md5.update(message.encode())
    return md5.digest()


seq = 1
random = 4711
id_counter = 1

with open(userdata_filename, 'r') as f:
    user_data = json.load(f)
    rriot = user_data.get('rriot')
with open(homedata_filename, 'r') as f:
    home_data = json.load(f)
devices = home_data.get('devices') + home_data.get('receivedDevices')
local_keys = dict(map(lambda device: tuple([device.get('duid'), device.get('localKey')]), devices))
endpoint = base64.b64encode(md5bin(rriot.get('k'))[8: 14]).decode()
nonce = secrets.token_bytes(16)
salt = 'TXdfu$jyZ#TZHsg4'
# [version, _seq, _random, timestamp, protocol, payload_len, payload, crc32] = struct.unpack('!s3iiihhs9i', data)
# [endpoint, unknown1, id, unknown2] = struct.unpack('<15sch6s', data)
mqtt_user = md5hex(rriot.get('u') + ':' + rriot.get('k'))[2: 10]
mqtt_password = md5hex(rriot.get('s') + ':' + rriot.get('k'))[16:]
client = mqtt.Client()

if __name__ == '__main__':
    main()
