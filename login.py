import base64
import hashlib
import hmac
import json
import math
import secrets
import sys
import time
from pathlib import Path

import requests as requests

default_url = 'https://euiot.roborock.com'
userdata_filename = 'userdata.json'
homedata_filename = 'homedata.json'


def main():
    username = sys.argv[1]
    password = sys.argv[2]
    params = {
        'email': username,
        'needtwostepauth': 'false'
    }
    response = requests.post(default_url + '/api/v1/getUrlByEmail', params).json()
    base_url = response.get("data").get("url")

    md5 = hashlib.md5()
    md5.update(username.encode())
    md5.update('should_be_unique'.encode())
    header_clientid = base64.b64encode(md5.digest()).decode()

    if Path(userdata_filename).is_file():
        with open(userdata_filename, 'r') as f:
            user_data = json.load(f)
    else:
        user_data = requests.post(base_url + '/api/v1/login', headers={
            'header_clientid': header_clientid
        }, params={
            'username': username,
            'password': password,
            'needtwostepauth': 'false'
        }).json().get('data')
        with open(userdata_filename, 'w') as f:
            json.dump(user_data, f, indent=4)
        # Alternative without password:
        # requests.post(base_url + '/api/v1/sendEmailCode', headers={
        #             'header_clientid': header_clientid
        #         }, params={
        #             'username': username,
        #             'type': 'auth'
        #         }).json().get('data')
        # ... get code from user ...
        # requests.post(base_url + '/api/v1/loginWithCode', headers={
        #             'header_clientid': header_clientid
        #         }, params={
        #             'username': username,
        #             'verifycode': code,
        #               'verifycodetype': 'AUTH_EMAIL_CODE'
        #         }).json().get('data')

        rriot = user_data.get('rriot')
    home_id = requests.get(base_url + '/api/v1/getHomeDetail', headers={
        'header_clientid': header_clientid,
        'Authorization': user_data.get('token')
    }).json().get('data').get('rrHomeId')
    timestamp = math.floor(time.time())
    nonce = secrets.token_urlsafe(6)
    prestr = ':'.join([rriot.get('u'), rriot.get('s'), nonce, str(timestamp),
                       hashlib.md5(('/user/homes/' + str(home_id)).encode()).hexdigest(), '', ''])
    mac = base64.b64encode(hmac.new(rriot.get('h').encode(), prestr.encode(), hashlib.sha256).digest()).decode()
    home_data = requests.get(rriot.get('r').get('a') + '/user/homes/' + str(home_id), headers={
        'Authorization': f'Hawk id="{rriot.get("u")}", s="{rriot.get("s")}", ts="{timestamp}", nonce="{nonce}", '
                         f'mac="{mac}"',
    }).json().get('result')
    with open(homedata_filename, 'w') as f:
        json.dump(home_data, f, indent=4)


if __name__ == '__main__':
    main()
