from umqtt.simple import MQTTClient

# Test reception e.g. with:
# mosquitto_sub -t foo_topic

def main(server='localhost'):
    client = MQTTClient('umqtt_client', server)
    client.connect()
    client.publish(b'foo_topic', b'hello')
    client.disconnect()


if __name__ == '__main__':
    main()
