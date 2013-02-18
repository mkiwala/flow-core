from flow.protocol import codec
import logging
import pika

from flow.brokers.base import BrokerBase

LOG = logging.getLogger()


class BlockingAmqpBroker(BrokerBase):
    def __init__(self, amqp_url=None):
        self.amqp_url = amqp_url

    def connect(self):
        self.connection = pika.BlockingConnection(
                pika.URLParameters(self.amqp_url))
        self.channel = self.connection.channel()

    def disconnect(self):
        self.connection.close()

    def create_bound_temporary_queue(self, exchange_name, topic, queue_name):
        self.create_temporary_queue(queue_name)

        self.channel.queue_bind(queue_name, exchange_name, topic)

    def create_temporary_queue(self, queue_name):
        self.channel.queue_declare(queue_name,
                durable=False, auto_delete=True, exclusive=True)


    def raw_publish(self, exchange_name, routing_key, encoded_message):
        self.channel.basic_publish(exchange_name,
                routing_key, encoded_message)

    def get(self, queue_name):
        return self.raw_get(queue_name, decoder=codec.decode)

    def raw_get(self, queue_name, decoder=lambda x: x):
        for frame, header, body in self.channel.consume(queue_name):
            message = decoder(body)
            self.channel.basic_ack(frame.delivery_tag)
            break

        # XXX This if statement is a workaround for a bug in pika
        # pika.adapters.blocking_connection, line 508:
        # +         messages = []
        if self.channel._generator_messages:
            self.channel.cancel()

        return message
