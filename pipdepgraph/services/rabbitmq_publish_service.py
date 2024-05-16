import json

import pika
import pika.channel

from pipdepgraph import models, constants

class RabbitMqPublishService:
    def __init__(self, channel: pika.channel.Channel):
        self.channel = channel

    def publish_known_package_name(self, kpn: models.KnownPackageName):
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"{constants.RABBITMQ_KPN_RK_PREFIX}{kpn.package_name}",
            body=kpn.to_json(),
        )

    def publish_version_distribution(self, vd: models.VersionDistribution):
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"{constants.RABBITMQ_VD_RK_PREFIX}{vd.version_distribution_id}",
            body=vd.to_json(),
        )
