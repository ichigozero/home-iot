import usocket as socket
import ustruct as struct
from ubinascii import hexlify


class MQTTException(Exception):
    pass


class MQTTClient:
    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl=False,
        ssl_params={}
    ):
        if port == 0:
            port = 8883 if ssl else 1883

        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.pid = 0
        self.call_back = None
        self.user = user
        self.password = password
        self.keepalive = keepalive
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0  # Quality of Service
        self.lw_retain = False

    def _send_str(self, s):
        self.sock.write(struct.pack('!H', len(s)))
        self.sock.write(s)

    def _recv_len(self):
        n = 0
        sh = 0

        while 1:
            b = self.sock.read(1)[0]
            n |= (b & 0x7f) << sh

            if not b & 0x80:
                return n

            sh += 7

    def set_callback(self, function):
        self.call_back = function

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic

        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_session=True):
        self.sock = socket.socket()
        address = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock.connect(address)

        if self.ssl:
            import ussl
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)

        premsg = bytearray(b'\x10\0\0\0\0\0')
        msg = bytearray(b'\x04MQTT\x04\x02\0\0')

        size = 10 + 2 + len(self.client_id)
        msg[6] = clean_session << 1

        if self.user is not None:
            size += 2 + len(self.user) + 2 + len(self.password)
            msg[6] |= 0xC0

        if self.keepalive:
            assert self.keepalive < 65536

            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF

        if self.lw_topic:
            size += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
            msg[6] |= self.lw_retain << 5

        i = 1
        while size > 0x7f:
            premsg[i] = (size & 0x7f) | 0x80
            size >>= 7
            i += 1

        premsg[i] = size

        self.sock.write(premsg, i + 2)
        self.sock.write(msg)
        self._send_str(self.client_id)

        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)

        if self.user is not None:
            self._send_str(self.user)
            self._send_str(self.password)

        response = self.sock.read(4)

        assert response[0] == 0x20 and response[1] == 0x02

        if response[3] != 0:
            raise MQTTException(response[3])

        return response[2] & 1

    def disconnect(self):
        self.sock.write(b'\xe0\0')
        self.sock.close()

    def ping(self):
        self.sock.write(b'\xc0\0')

    def publish(self, topic, msg, retain=False, qos=0):
        packet = bytearray(b'\x30\0\0\0')
        packet[0] |= qos << 1 | retain
        size = 2 + len(topic) + len(msg)

        if qos > 0:
            size += 2

        assert size < 2097152

        i = 1
        while size > 0x7f:
            packet[i] = (size & 0x7f) | 0x80
            size >>= 7
            i += 1

        packet[i] = size

        self.sock.write(packet, i + 1)
        self._send_str(topic)

        if qos > 0:
            self.pid += 1
            pid = self.pid
            struct.pack_into('!H', packet, 0, pid)
            self.sock.write(packet, 2)

        self.sock.write(msg)

        if qos == 1:
            while 1:
                op = self.wait_msg()
                if op == 0x40:
                    size = self.sock.read(1)

                    assert size == b'\x02'

                    rcv_pid = self.sock.read(2)
                    rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]

                    if pid == rcv_pid:
                        return
        elif qos == 2:
            assert 0

    def subscribe(self, topic, qos=0):
        assert self.call_back is not None, 'Subscribe callback is not set'

        packet = bytearray(b'\x82\0\0\0')
        self.pid += 1

        struct.pack_into('!BH', packet, 1, 2 + 2 + len(topic) + 1, self.pid)
        self.sock.write(packet)
        self._send_str(topic)
        self.sock.write(qos.to_bytes(1, 'little'))

        while 1:
            op = self.wait_msg()

            if op == 0x90:
                response = self.sock.read(4)

                assert response[1] == packet[2] and response[2] == packet[3]

                if response[3] == 0x80:
                    raise MQTTException(response[3])
                return

    def wait_msg(self):
        '''
        Wait for a single incoming MQTT message and process it.
        Subscribed messages are delivered to a callback previously
        set by .set_callback() method. Other (internal) MQTT
        messages processed internally.
        '''
        response = self.sock.read(1)
        self.sock.setblocking(True)

        if response is None:
            return None

        if response == b'':
            raise OSError(-1)

        if response == b'\xd0':  # PINGRESP
            size = self.sock.read(1)[0]

            assert size == 0
            return None

        op = response[0]

        if op & 0xf0 != 0x30:
            return op

        size = self._recv_len()
        topic_length = self.sock.read(2)
        topic_length = (topic_length[0] << 8) | topic_length[1]
        topic = self.sock.read(topic_length)
        size -= topic_length + 2

        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            size -= 2

        msg = self.sock.read(size)
        self.call_back(topic, msg)

        if op & 6 == 2:
            packet = bytearray(b'\x40\x02\0\0')
            struct.pack_into('!H', packet, 2, pid)
            self.sock.write(packet)
        elif op & 6 == 4:
            assert 0

    def check_msg(self):
        '''
        Checks whether a pending message from server is available.
        If not, returns immediately with None. Otherwise, does
        the same processing as wait_msg.
        '''
        self.sock.setblocking(False)

        return self.wait_msg()
