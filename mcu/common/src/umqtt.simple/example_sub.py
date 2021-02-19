import time

from umqtt.simple import MQTTClient

# Publish test messages e.g. with:
# mosquitto_pub -t foo_topic -m hello

def sub_callback(topic, msg):
    print((topic, msg))


def main(server='localhost'):
    client = MQTTClient('umqtt_client', server)
    client.set_callback(sub_callback)
    client.connect()
    client.subscribe(b'foo_topic')

    while True:
        if True:
            # Blocking wait for message
            client.wait_msg()
        else:
            # Non-blocking wait for message
            client.check_msg()
            # Then need to sleep to avoid 100% CPU usage (in a real
            # app other useful actions would be performed instead)
            time.sleep(1)

    client.disconnect()


if __name__ == '__main__':
    main()
