# Copyright (c) 2018 Ultimaker
# !/usr/bin/env python
# -*- coding: utf-8 -*-
from mongoOperator.models.BaseModel import BaseModel
from mongoOperator.models.fields import StringField


class V1MongoClusterConfigurationSpecBackups(BaseModel):
    """
    Model for the `spec.backups` field of the V1MongoClusterConfiguration.
    """
    restore_from = StringField(required=False)
    cron = StringField(required=False)
