import logging
import asyncio
import time

from pipdepgraph import constants, models
from pipdepgraph.core import common, rabbitmq

from pipdepgraph.services import rabbitmq_publish_service

from pipdepgraph.repositories import (
    cdc_repository,
)

logger = logging.getLogger("pipdepgraph.entrypoints.cdc.publisher")


async def main():
    logger.info("Initializing DB pool")
    async with (
        common.initialize_async_connection_pool() as db_pool,
    ):
        with (
            rabbitmq.initialize_rabbitmq_connection() as connection,
            connection.channel() as channel,
        ):
            rabbitmq.declare_rabbitmq_infrastructure(channel)

        logger.info("Initializing repositories")
        cdcr = cdc_repository.CdcRepository(db_pool)

        logger.info("Initializing services")
        rmq_pub = rabbitmq_publish_service.RabbitMqPublishService(rabbitmq.initialize_rabbitmq_connection)

        logger.info("Running.")
        while True:
            logger.info("Polling event log for new events.")

            with (
                rabbitmq.initialize_rabbitmq_connection() as connection,
                connection.channel() as channel,
            ):
                async for event in cdcr.iter_event_log():
                    logger.debug("Publishing event: %s", event)
                    rmq_pub.publish_cdc_event_log_entry(event, channel)

            logger.info("Event log drained. Waiting 10 seconds.")
            time.sleep(10)

if __name__ == "__main__":
    common.initialize_logger()
    asyncio.run(main())
