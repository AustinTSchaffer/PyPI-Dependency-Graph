import json
import threading
from collections.abc import Callable

import pika
import pika.adapters.blocking_connection
import pika.channel
import pika.connection

from pipdepgraph import models, constants

class RabbitMqPublishService:
    def __init__(self, rmq_conn_factory: Callable[[], pika.BlockingConnection]):
        self.rmq_conn_factory = rmq_conn_factory

    def publish_known_package_name(self, kpn: models.KnownPackageName):
        with (
            self.rmq_conn_factory() as connection,
            connection.channel() as channel
        ):
            channel: pika.channel.Channel
            channel.basic_publish(
                exchange=constants.RABBITMQ_EXCHANGE,
                routing_key=f"{constants.RABBITMQ_KPN_RK_PREFIX}{kpn.package_name}",
                body=kpn.to_json(),
            )

    def publish_known_package_names(self, kpns: list[models.KnownPackageName]):
        with (
            self.rmq_conn_factory() as connection,
            connection.channel() as channel
        ):
            channel: pika.channel.Channel
            for kpn in kpns:
                channel.basic_publish(
                    exchange=constants.RABBITMQ_EXCHANGE,
                    routing_key=f"{constants.RABBITMQ_KPN_RK_PREFIX}{kpn.package_name}",
                    body=kpn.to_json(),
                )

    def publish_version_distribution(self, vd: models.VersionDistribution):
        with (
            self.rmq_conn_factory() as connection,
            connection.channel() as channel
        ):
            channel: pika.channel.Channel
            channel.basic_publish(
                exchange=constants.RABBITMQ_EXCHANGE,
                routing_key=f"{constants.RABBITMQ_VD_RK_PREFIX}{vd.version_distribution_id}",
                body=vd.to_json(),
            )

    def publish_version_distributions(self, vds: list[models.VersionDistribution]):
        with (
            self.rmq_conn_factory() as connection,
            connection.channel() as channel
        ):
            channel: pika.channel.Channel
            for vd in vds:
                channel.basic_publish(
                    exchange=constants.RABBITMQ_EXCHANGE,
                    routing_key=f"{constants.RABBITMQ_VD_RK_PREFIX}{vd.version_distribution_id}",
                    body=vd.to_json(),
                )
