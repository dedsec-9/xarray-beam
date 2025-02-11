# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Rechunk the WeatherBench ERA5 dataset from images to time-series."""
from absl import app
from absl import flags
import apache_beam as beam
import xarray
import xarray_beam


INPUT_PATH = flags.DEFINE_string('input_path', None, help='Input Zarr path')
OUTPUT_PATH = flags.DEFINE_string('output_path', None, help='Output Zarr path')
RUNNER = flags.DEFINE_string('runner', None, 'beam.runners.Runner')

FLAGS = flags.FLAGS

# pylint: disable=expression-not-assigned


def main(argv):
  source_dataset = xarray.open_zarr(
      INPUT_PATH.value, chunks=None, consolidated=True
  )
  template = xarray.zeros_like(source_dataset.chunk())
  source_chunks = {'latitude': -1, 'longitude': -1, 'time': 31}
  split_chunks = {'latitude': 1440//8, 'longitude': -1, 'time': 31}
  target_chunks = {'latitude': 5, 'longitude': 5, 'time': -1}

  with beam.Pipeline(runner=RUNNER.value, argv=argv) as root:
    (
        root
        | xarray_beam.DatasetToChunks(source_dataset, source_chunks)
        # add an intermediate splitting, because rechunker complains about
        # source chunks too big to fit into memory.
        | xarray_beam.SplitChunks(split_chunks)
        # TODO(shoyer): split this rechunk per data variable; it currently ends
        # up producing tiny intermediate chunks (50 KB), which adds significant
        # overhead.
        | xarray_beam.Rechunk(
            source_dataset.sizes,
            split_chunks,
            target_chunks,
            itemsize=len(source_dataset.data_vars) * 4,
        )
        | xarray_beam.ChunksToZarr(
            OUTPUT_PATH.value, template, target_chunks,
        )
    )


if __name__ == '__main__':
  app.run(main)
