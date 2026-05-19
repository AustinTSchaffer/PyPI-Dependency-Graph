from collections.abc import Callable

import msgspec.json
import pika
import pika.adapters.blocking_connection
import pika.channel
import pika.connection

from pipdepgraph import models, constants


class RabbitMqPublishService:
    def __init__(self, channel: pika.channel.Channel):
        self.channel = channel

    def publish_package_name(self, kpn: models.Package | str):
        package_name = kpn.name if isinstance(kpn, models.Package) else kpn
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"{constants.RABBITMQ_NAMES_RK_PREFIX}{package_name}",
            body=msgspec.json.encode(kpn),
        )

    def publish_package_names(self, kpns: list[models.Package]):
        for kpn in kpns:
            self.publish_package_name(kpn)

    def publish_distribution(self, vd: models.Distribution):
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"{constants.RABBITMQ_DISTS_RK_PREFIX}{vd.distribution_id}",
            body=msgspec.json.encode(vd),
        )

    def publish_distributions(self, vds: list[models.Distribution]):
        for vd in vds:
            self.publish_distribution(vd)

    def publish_requirement_for_candidate_correlation(self, req: models.Requirement):
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"{constants.RABBITMQ_REQS_CAND_CORR_RK_PREFIX}.{req.requirement_id}",
            body=msgspec.json.encode(req),
        )

    def publish_requirement_dict_for_candidate_correlation(self, req: dict):
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"{constants.RABBITMQ_REQS_CAND_CORR_RK_PREFIX}.{req['requirement_id']}",
            body=msgspec.json.encode(req),
        )

    def publish_version_dict_for_candidate_correlation(self, version: dict):
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"{constants.RABBITMQ_VERS_CAND_CORR_RK_PREFIX}.{version['version_id']}",
            body=msgspec.json.encode(version),
        )

    def publish_cdc_event_log_entry(self, event: models.EventLogEntry):
        self.channel.basic_publish(
            exchange=constants.RABBITMQ_EXCHANGE,
            routing_key=f"cdc.{event.schema}.{event.table}.{event.event_id}",
            body=msgspec.json.encode(event),
        )
