from flow.protocol.exceptions import InvalidMessageException
from pika.spec import Basic

from flow.brokers.base import BrokerBase

import logging
import pika
import signal

LOG = logging.getLogger(__name__)

TERMINATION_SIGNALS = [signal.SIGINT, signal.SIGTERM]


class StrategicAmqpBroker(BrokerBase):
    def __init__(self, prefetch_count=None, acking_strategy=None,
            **connection_params):
        self.prefetch_count = prefetch_count
        self.acking_strategy = acking_strategy
        self.connection_params = connection_params

        self._publish_properties = pika.BasicProperties(delivery_mode=2)

        self._listeners = {}
        self.acking_strategy.register_broker(self)


    def _reset_state(self):
        LOG.debug("Resetting broker state.")
        self._last_publish_tag = 0
        self._last_receive_tag = 0

        self.acking_strategy.reset()

    def ack_if_able(self):
        ackable_tags, multiple = self.acking_strategy.pop_ackable_receive_tags()
        LOG.debug('Found %d ackable tags (multiple = %s)',
                len(ackable_tags), multiple)
        if ackable_tags:
            self.ack(ackable_tags[0], multiple=multiple)
            for tag in ackable_tags[1:]:
                self.ack(tag)

    def ack(self, receive_tag, multiple=False):
        LOG.debug('Acking message (%d), multiple = %s', receive_tag, multiple)
        self._channel.basic_ack(receive_tag, multiple=multiple)

    def reject(self, receive_tag):
        LOG.debug('Rejecting message (%d)', receive_tag)
        self.acking_strategy.remove_receive_tag(receive_tag)
        self._channel.basic_reject(receive_tag, requeue=False)


    def register_handler(self, handler):
        queue_name = handler.queue_name
        message_class = handler.message_class

        LOG.debug('Registering handler (%s) listening for (%s) on queue (%s)',
                handler, message_class.__name__, queue_name)

        listener = AmqpListener(delivery_callback=handler,
                message_class=message_class, broker=self)
        self._listeners[queue_name] = listener


    def raw_publish(self, exchange_name, routing_key, encoded_message):
        receive_tag = self._last_receive_tag

        self._last_publish_tag += 1
        publish_tag = self._last_publish_tag
        LOG.debug("Publishing message (%d) to routing key (%s): %s",
                publish_tag, routing_key, encoded_message)

        self.acking_strategy.add_publish_tag(receive_tag=receive_tag,
                publish_tag=publish_tag)

        self._channel.basic_publish(exchange=exchange_name,
                routing_key=routing_key, body=encoded_message,
                properties=self._publish_properties)


    def connect_and_listen(self):
        self.connect()

    def connect(self):
        params = pika.ConnectionParameters(**self.connection_params)
        set_termination_signal_handler(raise_handler)

        self._connection = pika.SelectConnection(
                params, self._on_connection_open)

        try:
            self._begin_ioloop()
        except KeyboardInterrupt:
            self.disconnect()
        except pika.exceptions.ConnectionClosed:
            LOG.exception('Disconnected from AMQP server: %s')

    def disconnect(self):
        LOG.info("Closing AMQP connection.")
        self._connection.close()
        self._begin_ioloop()

    def _begin_ioloop(self):
        interrupted = True
        while interrupted:
            try:
                self._connection.ioloop.start()
                interrupted = False
            except IOError:
                LOG.warning('IO interrupted, continuing')


    def _on_connection_open(self, connection):
        connection.channel(self._on_channel_open)

    def _on_channel_open(self, channel):
        self._channel = channel
        LOG.debug('Channel open')
        self._reset_state()

        if self.prefetch_count:
            self._channel.basic_qos(prefetch_count=self.prefetch_count)

        self.acking_strategy.on_channel_open(channel)

        for queue_name, listener in self._listeners.iteritems():
            LOG.debug('Beginning consumption on queue (%s)', queue_name)
            self._channel.basic_consume(listener, queue_name)


    def set_last_receive_tag(self, receive_tag):
        LOG.debug('Received message (%d)', receive_tag)
        self._last_receive_tag = receive_tag
        self.acking_strategy.add_receive_tag(receive_tag)


def set_termination_signal_handler(handler):
    for sig in TERMINATION_SIGNALS:
        signal.signal(sig, handler)

def raise_handler(*args):
    LOG.info("Caught signal %s, exitting.", args)
    set_termination_signal_handler(null_handler)
    raise KeyboardInterrupt('Caught Signal')

def null_handler(*args):
    LOG.warning("Caught signal %s while trying to exit.", args)


class AmqpListener(object):
    def __init__(self, broker=None, message_class=None, delivery_callback=None):
        self.broker = broker
        self.message_class = message_class
        self.delivery_callback = delivery_callback

    def __call__(self, channel, basic_deliver, properties, encoded_message):
        broker = self.broker

        delivery_tag = basic_deliver.delivery_tag
        broker.set_last_receive_tag(delivery_tag)
        LOG.debug('Received message (%d), properties = %s',
                delivery_tag, properties)

        try:
            message = self.message_class.decode(encoded_message)
            self.delivery_callback(message)

            LOG.debug('Checking for ack after handler (%d)', delivery_tag)
            broker.ack_if_able()

        # KeyboardInterrupt must be passed up the stack so we can terminate
        except KeyboardInterrupt:
            raise

        except InvalidMessageException as e:
            LOG.exception('Invalid message.  Properties = %s, message = %s',
                    properties, encoded_message)
            broker.reject(delivery_tag)
        except:
            LOG.exception('Unexpected error handling message.')
            broker.reject(delivery_tag)
