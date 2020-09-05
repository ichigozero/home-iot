# MIT License
#
# Copyright (c) 2020 Gary Sentosa
# Copyright (c) 2017 Tayfun ULU
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import network
import socket
import time
import ure

AP_SSID = 'EspWifiManager'
AP_PASSWORD = 'nodemcu8266'
AP_AUTHMODE = 3  # WPA2

NETWORK_PROFILES = 'wifi.dat'

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

server_socket = None


def get_connection():
    """Return a working WLAN(STA_IF) instance or None"""

    if wlan_sta.isconnected():
        return wlan_sta

    connected = False
    try:
        # ESP connecting to WiFi takes time, wait a bit and try again:
        time.sleep(3)

        if wlan_sta.isconnected():
            return wlan_sta

        # Read known network profiles from file
        profiles = read_profiles()

        # Search WiFis in range
        wlan_sta.active(True)
        networks = wlan_sta.scan()

        AUTHMODE = {
            0: 'open',
            1: 'WEP',
            2: 'WPA-PSK',
            3: 'WPA2-PSK',
            4: 'WPA/WPA2-PSK'
        }
        for ssid, bssid, channel, rssi, authmode, hidden in sorted(
                networks,
                key=lambda x: x[3],
                reverse=True
        ):
            ssid = ssid.decode('utf-8')
            encrypted = authmode > 0
            print(
                'SSID: {} Channel: {} RSSI: {} AuthMode: {}'
                .format(ssid, channel, rssi, AUTHMODE.get(authmode, '?'))
            )

            if encrypted:
                if ssid in profiles:
                    password = profiles[ssid]
                    connected = do_connect(ssid, password)
                else:
                    print('Skipping unknown encrypted network')
            else:
                connected = do_connect(ssid, None)

            if connected:
                break

    except OSError as e:
        print('Exception', str(e))

    # start web server for connection manager:
    if not connected:
        connected = start()

    return wlan_sta if connected else None


def read_profiles():
    with open(NETWORK_PROFILES) as f:
        lines = f.readlines()

    profiles = {}

    for line in lines:
        ssid, password = line.strip('\n').split(';')
        profiles[ssid] = password

    return profiles


def write_profiles(profiles):
    lines = []

    for ssid, password in profiles.items():
        lines.append('{};{}\n'.format(ssid, password))

    with open(NETWORK_PROFILES, 'w') as f:
        f.write(''.join(lines))


def do_connect(ssid, password):
    wlan_sta.active(True)

    if wlan_sta.isconnected():
        return None

    print('Trying to connect to {}...'.format(ssid))
    wlan_sta.connect(ssid, password)

    for retry in range(100):
        connected = wlan_sta.isconnected()

        if connected:
            break

        time.sleep(0.1)
        print('.', end='')

    if connected:
        print('\nConnected. Network config: ', wlan_sta.ifconfig())
    else:
        print('\nFailed. Not Connected to: {}'.format(ssid))

    return connected


def send_header(client, status_code=200, content_length=None ):
    client.sendall('HTTP/1.0 {} OK\r\n'.format(status_code))
    client.sendall('Content-Type: text/html\r\n')

    if content_length is not None:
      client.sendall('Content-Length: {}\r\n'.format(content_length))

    client.sendall('\r\n')


def send_response(client, payload, status_code=200):
    content_length = len(payload)

    send_header(client, status_code, content_length)

    if content_length > 0:
        client.sendall(payload)

    client.close()


def handle_root(client):
    wlan_sta.active(True)
    send_header(client)

    client.sendall('''\
        <html>
            <h1 style="color: #5e9ca0; text-align: center;">
                <span style="color: #ff0000;">
                    Wi-Fi Client Setup
                </span>
            </h1>
            <form action="configure" method="post">
                <table style="margin-left: auto; margin-right: auto;">
                    <tbody>
    ''')

    ssids = sorted(ssid.decode('utf-8') for ssid, *_ in wlan_sta.scan())
    while len(ssids):
        ssid = ssids.pop(0)
        client.sendall('''\
                        <tr>
                            <td colspan="2">
                                <input
                                  type="radio" name="ssid" value="{0}"
                                />{0}
                            </td>
                        </tr>
        '''.format(ssid))

    client.sendall('''\
                        <tr>
                            <td>Password:</td>
                            <td><input name="password" type="password" /></td>
                        </tr>
                    </tbody>
                </table>
                <p style="text-align: center;">
                    <input type="submit" value="Submit" />
                </p>
            </form>
            <p>&nbsp;</p>
            <hr />
            <h5>
                <span style="color: #ff0000;">
                    Your ssid and password information will be saved into the
                    "{filename}" file in your ESP module for future usage.
                    Be careful about security!
                </span>
            </h5>
            <hr />
            <h2 style="color: #2e6c80;">
                Some useful infos:
            </h2>
        </html>
    '''.format(filename=NETWORK_PROFILES))

    client.close()


def handle_configure(client, request):
    match = ure.search('ssid=([^&]*)&password=(.*)', request)

    if match is None:
        send_response(client, 'Parameters not found', status_code=400)
        return False

    # Version 1.9 compatibility
    try:
        ssid = (
            match
            .group(1)
            .decode('utf-8')
            .replace('%3F', '?')
            .replace('%21', '!')
        )
        password = (
            match
            .group(2)
            .decode('utf-8')
            .replace('%3F', '?')
            .replace('%21', '!')
        )
    except AttributeError:
        ssid = match.group(1).replace('%3F', '?').replace('%21', '!')
        password = match.group(2).replace('%3F', '?').replace('%21', '!')

    if len(ssid) == 0:
        send_response(client, 'SSID must be provided', status_code=400)

        return False

    if do_connect(ssid, password):
        response = '''\
            <html>
                <center>
                    <br><br>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                          ESP successfully connected to WiFi network {ssid}.
                        </span>
                    </h1>
                    <br><br>
                </center>
            </html>
        '''.format(ssid=ssid)
        send_response(client, response)

        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}

        profiles[ssid] = password

        write_profiles(profiles)
        time.sleep(5)

        return True
    else:
        response = '''\
            <html>
                <center>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP could not connect to WiFi network {ssid}.
                        </span>
                    </h1>
                    <br><br>
                    <form>
                        <input
                          type="button"
                          value="Go back!"
                          onclick="history.back()"
                        ></input>
                    </form>
                </center>
            </html>
        '''.format(ssid=ssid)
        send_response(client, response)

        return False


def handle_not_found(client, url):
    send_response(client, 'Path not found: {}'.format(url), status_code=404)


def stop():
    global server_socket

    if server_socket:
        server_socket.close()
        server_socket = None


def start(port=80):
    global server_socket

    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]

    stop()

    wlan_sta.active(True)
    wlan_ap.active(True)
    wlan_ap.config(essid=AP_SSID, password=AP_PASSWORD, authmode=AP_AUTHMODE)

    server_socket = socket.socket()
    server_socket.bind(addr)
    server_socket.listen(1)

    print('Connect to WiFi ssid {}, default password: {}'
          .format(AP_SSID, AP_PASSWORD))
    print('and access the ESP via your favorite web browser at 192.168.4.1.')
    print('Listening on:', addr)

    while True:
        if wlan_sta.isconnected():
            return True

        client, addr = server_socket.accept()
        print('Client connected from', addr)

        try:
            client.settimeout(5.0)
            request = b''

            try:
                while '\r\n\r\n' not in request:
                    request += client.recv(512)
            except OSError:
                pass

            print('Request is: {}'.format(request))

            if 'HTTP' not in request:
                continue

            # Version 1.9 compatibility
            try:
                url = (
                    ure
                    .search('(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP', request)
                    .group(1)
                    .decode('utf-8')
                    .rstrip('/')
                )
            except AttributeError:
                url = (
                    ure
                    .search('(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP', request)
                    .group(1)
                    .rstrip('/')
                )

            print('URL is {}'.format(url))

            if url == '':
                handle_root(client)
            elif url == 'configure':
                handle_configure(client, request)
            else:
                handle_not_found(client, url)
        finally:
            client.close()
