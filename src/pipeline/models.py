#!/usr/bin/python2.5
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Datastore models used by the Google App Engine Pipeline API."""

import json

from google.appengine.ext import ndb

# Relative imports
import util


class _PipelineRecord(ndb.Model):
  """Represents a Pipeline.

  Properties:
    class_path: Path of the Python class to use for this pipeline.
    root_pipeline: The root of the whole workflow; set to itself this pipeline
      is its own root.
    fanned_out: List of child _PipelineRecords that were started when this
      generator pipeline moved from WAITING to RUN.
    start_time: For pipelines with no start _BarrierRecord, when this pipeline
      was enqueued to run immediately.
    finalized_time: When this pipeline moved from WAITING or RUN to DONE.
    params: Serialized parameter dictionary.
    status: The current status of the pipeline.
    current_attempt: The current attempt (starting at 0) to run.
    max_attempts: Maximum number of attempts (starting at 0) to run.
    next_retry_time: ETA of the next retry attempt.
    retry_message: Why the last attempt failed; None or empty if no message.

  Root pipeline properties:
    is_root_pipeline: This is a root pipeline.
    abort_message: Why the whole pipeline was aborted; only saved on
      root pipelines.
    abort_requested: If an abort signal has been requested for this root
      pipeline; only saved on root pipelines
  """

  WAITING = 'waiting'
  RUN = 'run'
  DONE = 'done'
  ABORTED = 'aborted'

  class_path = ndb.StringProperty()
  # The following used: collection_name='child_pipelines_set')
  root_pipeline = ndb.KeyProperty(kind='_PipelineRecord')
  fanned_out = ndb.KeyProperty(repeated=True, indexed=False)
  start_time = ndb.DateTimeProperty(indexed=True)
  finalized_time = ndb.DateTimeProperty(indexed=False)

  # One of these two will be set, depending on the size of the params.
  params_text = ndb.TextProperty(name='params')
  params_blob = ndb.BlobKeyProperty(name='params_blob', indexed=False)

  status = ndb.StringProperty(choices=(WAITING, RUN, DONE, ABORTED),
                             default=WAITING)

  # Retry behavior
  current_attempt = ndb.IntegerProperty(default=0, indexed=False)
  max_attempts = ndb.IntegerProperty(default=1, indexed=False)
  next_retry_time = ndb.DateTimeProperty(indexed=False)
  retry_message = ndb.TextProperty()

  # Root pipeline properties
  is_root_pipeline = ndb.BooleanProperty()
  abort_message = ndb.TextProperty()
  abort_requested = ndb.BooleanProperty(indexed=False)

  @classmethod
  def kind(cls):
    return '_AE_Pipeline_Record'

  @property
  def params(self):
    """Returns the dictionary of parameters for this Pipeline."""
    if hasattr(self, '_params_decoded'):
      return self._params_decoded

    if self.params_blob is not None:
      value_encoded = self.params_blob.open().read()
    else:
      value_encoded = self.params_text

    value = json.loads(value_encoded, cls=util.JsonDecoder)
    if isinstance(value, dict):
      kwargs = value.get('kwargs')
      if kwargs:
        adjusted_kwargs = {}
        for arg_key, arg_value in kwargs.iteritems():
          # Python only allows non-unicode strings as keyword arguments.
          adjusted_kwargs[str(arg_key)] = arg_value
        value['kwargs'] = adjusted_kwargs

    self._params_decoded = value
    return self._params_decoded


class _SlotRecord(ndb.Model):
  """Represents an output slot.

  Properties:
    root_pipeline: The root of the workflow.
    filler: The pipeline that filled this slot.
    value: Serialized value for this slot.
    status: The current status of the slot.
    fill_time: When the slot was filled by the filler.
  """

  FILLED = 'filled'
  WAITING = 'waiting'

  root_pipeline = ndb.KeyProperty(kind=_PipelineRecord)
  # The following used: collection_name='filled_slots_set')
  filler = ndb.KeyProperty(kind=_PipelineRecord)

  # One of these two will be set, depending on the size of the value.
  value_text = ndb.TextProperty(name='value')
  value_blob = ndb.BlobKeyProperty(name='value_blob', indexed=False)

  status = ndb.StringProperty(choices=(FILLED, WAITING), default=WAITING,
                             indexed=False)
  fill_time = ndb.DateTimeProperty(indexed=False)

  @classmethod
  def kind(cls):
    return '_AE_Pipeline_Slot'

  @property
  def value(self):
    """Returns the value of this Slot."""
    if hasattr(self, '_value_decoded'):
      return self._value_decoded

    if self.value_blob is not None:
      encoded_value = self.value_blob.open().read()
    else:
      encoded_value = self.value_text

    self._value_decoded = json.loads(encoded_value, cls=util.JsonDecoder)
    return self._value_decoded


class _BarrierRecord(ndb.Model):
  """Represents a barrier.

  Properties:
    root_pipeline: The root of the workflow.
    target: The pipeline to run when the barrier fires.
    blocking_slots: The slots that must be filled before this barrier fires.
    trigger_time: When this barrier fired.
    status: The current status of the barrier.
  """

  # Barrier statuses
  FIRED = 'fired'
  WAITING = 'waiting'

  # Barrier trigger reasons (used as key names)
  START = 'start'
  FINALIZE = 'finalize'
  ABORT = 'abort'

  root_pipeline = ndb.KeyProperty(kind=_PipelineRecord)
  # The following used: collection_name='called_barrier_set')
  target = ndb.KeyProperty(kind=_PipelineRecord,
  blocking_slots = ndb.KeyProperty(repeated=True)
  trigger_time = ndb.DateTimeProperty(indexed=False)
  status = ndb.StringProperty(choices=(FIRED, WAITING), default=WAITING,
                             indexed=False)

  @classmethod
  def kind(cls):
    return '_AE_Pipeline_Barrier'


class _StatusRecord(ndb.Model):
  """Represents the current status of a pipeline.

  Properties:
    message: The textual message to show.
    console_url: URL to iframe as the primary console for this pipeline.
    link_names: Human display names for status links.
    link_urls: URLs corresponding to human names for status links.
    status_time: When the status was written.
  """

  root_pipeline = ndb.KeyProperty(kind=_PipelineRecord)
  message = ndb.TextProperty()
  console_url = ndb.TextProperty()
  link_names = ndb.TextProperty(repeated=True, indexed=False)
  link_urls = ndb.TextProperty(repeated=True, indexed=False)
  status_time = ndb.DateTimeProperty(indexed=False)

  @classmethod
  def kind(cls):
    return '_AE_Pipeline_Status'
