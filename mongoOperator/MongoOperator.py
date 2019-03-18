# Copyright (c) 2018 Ultimaker
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import logging
import threading

from mongoOperator.ClusterManager import ClusterManager


class MongoOperator:
    """
    The Mongo operator manages MongoDB replica sets and backups in a Kubernetes cluster.
    """

    def __init__(self, sleep_per_run: float = 5.0) -> None:
        """
        :param sleep_per_run: How many seconds we should sleep after each run.
        """
        self._sleep_per_run = sleep_per_run

    def run_forever(self) -> None:
        """
        Runs the mongo operator forever (until a kill command is received).
        """

        clusterManager = ClusterManager()

        thread = threading.Thread(target=clusterManager.checkAndBackupIfNeeded)
        thread.start()
        logging.info("Scheduled backup check every 10 seconds,")

        logging.info("Starting operator ioloop processing events")
        try:
            ioloop = asyncio.get_event_loop()

            ioloop.create_task(clusterManager.pods())
            ioloop.create_task(clusterManager.statefulsets())
            ioloop.run_forever()
        except KeyboardInterrupt:
            logging.info("Application interrupted...")
        logging.info("Done running operator")

