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

    def publish_package_name(
        self, kpn: models.PackageName | str, channel: pika.channel.Channel = None
    ):
        package_name = (
            kpn.package_name if isinstance(kpn, models.PackageName) else kpn
        )

        def _publish(channel: pika.channel.Channel):
            channel.basic_publish(
                exchange=constants.RABBITMQ_EXCHANGE,
                routing_key=f"{constants.RABBITMQ_NAMES_RK_PREFIX}{package_name}",
                body=(
                    kpn.to_json()
                    if isinstance(kpn, models.PackageName)
                    else f'"{kpn}"'
                ),
            )

        if channel:
            _publish(channel)
            return
        with self.rmq_conn_factory() as connection, connection.channel() as channel:
            _publish(channel)

    def publish_package_names(self, kpns: list[models.PackageName]):
        with self.rmq_conn_factory() as connection, connection.channel() as channel:
            for kpn in kpns:
                self.publish_package_name(kpn, channel=channel)

    def publish_distribution(
        self, vd: models.Distribution, channel: pika.channel.Channel = None
    ):
        def _publish(channel: pika.channel.Channel):
            channel.basic_publish(
                exchange=constants.RABBITMQ_EXCHANGE,
                routing_key=f"{constants.RABBITMQ_DISTS_RK_PREFIX}{vd.distribution_id}",
                body=vd.to_json(),
            )

        if channel:
            _publish(channel)
            return
        with self.rmq_conn_factory() as connection, connection.channel() as channel:
            _publish(channel)

    def publish_distributions(self, vds: list[models.Distribution]):
        with self.rmq_conn_factory() as connection, connection.channel() as channel:
            for vd in vds:
                self.publish_distribution(vd, channel=channel)

    def publish_requirement_for_reprocessing(
        self, req: models.Requirement, channel: pika.channel.Channel = None
    ):
        def _publish(channel: pika.channel.Channel):
            channel.basic_publish(
                exchange=constants.RABBITMQ_EXCHANGE,
                routing_key=f"{constants.RABBITMQ_REPROCESS_REQS_RK_PREFIX}.of.{req.distribution_id}",
                body=req.to_json(),
            )

        if channel:
            _publish(channel)
            return
        with self.rmq_conn_factory() as connection, connection.channel() as channel:
            _publish(channel)

    def publish_requirement_for_candidate_correlation(
        self, req: models.Requirement, channel: pika.channel.Channel = None
    ):
        def _publish(channel: pika.channel.Channel):
            channel.basic_publish(
                exchange=constants.RABBITMQ_EXCHANGE,
                routing_key=f"{constants.RABBITMQ_REQS_CAND_CORR_RK_PREFIX}.{req.requirement_id}",
                body=req.to_json(),
            )

        if channel:
            _publish(channel)
            return
        with self.rmq_conn_factory() as connection, connection.channel() as channel:
            _publish(channel)

    def publish_cdc_event_log_entry(
        self, event: models.EventLogEntry, channel: pika.channel.Channel = None
    ):
        def _publish(channel: pika.channel.Channel):
            channel.basic_publish(
                exchange=constants.RABBITMQ_EXCHANGE,
                routing_key=f"cdc.{event.schema}.{event.table}.{event.event_id}",
                body=event.to_json(),
            )

        if channel:
            _publish(channel)
            return
        with self.rmq_conn_factory() as connection, connection.channel() as channel:
            _publish(channel)
