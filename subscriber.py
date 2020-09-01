import datetime
import functools
import json
import logging
import os
import uuid

import click
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient


try:
    db_client = InfluxDBClient(
        host=os.environ.get('INFLUXDB_HOST') or 'localhost',
        port=os.environ.get('INFLUXDB_PORT') or 8086,
        username=os.environ.get('INFLUXDB_USER') or 'root',
        password=os.environ.get('INFLUXDB_PASSWORD') or 'root',
        database=os.environ['INFLUXDB_DBNAME']
    )
except KeyError:
    logging.exception('INFLUXDB_DBNAME environment variable not set')


@click.group()
def main():
    pass


def subscribe_mqtt(function):
    @functools.wraps(function)
    def wrapper(broker, topic, verbose, *args, **kwargs):
        def _on_connect(client, userdata, flags, rc):
            logging.info('Connected with result code %d', rc)
            client.subscribe(topic)

        def _on_message(client, userdata, message):
            message_received = message.payload.decode('utf-8')

            logging.debug('Message topic: %s', message.topic)
            logging.debug('Message QoS: %s', message.qos)
            logging.debug('Message retain flag: %s', message.retain)
            logging.debug('Message received: %s', message_received)

            decoded_message = json.loads(message_received)
            data_summary = {
                'measurement': message.topic,
                'time': datetime.datetime.utcnow().isoformat()
            }
            data_summary.update(
                function(broker, topic, verbose, decoded_message))

            logging.debug('Data summary: %s', [data_summary])
            db_client.write_points([data_summary])
            logging.debug('Data summary has been written into database')

        if verbose:
            logging.basicConfig(level=logging.DEBUG)

        client = mqtt.Client('home-iot-{}'.format(uuid.uuid4()))
        client.on_connect = _on_connect
        client.on_message = _on_message
        client.connect(broker)

        client.loop_forever()

    return wrapper


@main.command()
@click.argument('broker')
@click.argument('topic')
@click.option('--verbose', '-v', is_flag=True)
@subscribe_mqtt
def thermometer(broker, topic, verbose, decoded_message):
    return {
        'fields': {
            'temperature': float(decoded_message.get('temperature')),
            'humidity': float(decoded_message.get('humidity')),
            'heat_index': float(decoded_message.get('heat_index')),
            'dew_point': float(decoded_message.get('dew_point')),
        }
    }


@main.command()
@click.argument('broker')
@click.argument('topic')
@click.option('--verbose', '-v', is_flag=True)
@subscribe_mqtt
def seismometer(broker, topic, verbose, decoded_message):
    return {
        'fields': {
            'seismic_scale': float(decoded_message.get('seismic_scale')),
            'x_acceleration': float(decoded_message.get('x_acceleration')),
            'y_acceleration': float(decoded_message.get('y_acceleration')),
            'z_acceleration': float(decoded_message.get('z_acceleration')),
        }
    }


if __name__ == '__main__':
    main()
