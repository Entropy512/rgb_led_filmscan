#!/usr/bin/env python3

'''
Converts a CSV file exported by WebPlotDigitizer ( https://apps.automeris.io/wpd/ ) to a dcamprof camera SSF JSON
For the time being, the column headers need fixing - Replace the empty entry to the right of Blue in the first row with Blue, etc.
'''
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--input', type=argparse.FileType('rb'), required=True,
    help='path to input files')

args = vars(ap.parse_args())

pd.options.mode.copy_on_write = True

spectral_data = pd.read_csv(args['input'], header=[0,1])

'''
WebPlotDigitizer exports in the order you added points, and has individual X values for each dataset instead of a single X column that is suitable for indexing,
so let's do some re-sorting.
'''
datasets = {}
for color in ['Red', 'Green', 'Blue']:
    cdata = spectral_data[color]
    cdata.rename(columns={'Y' : color}, inplace=True)
    cdata.set_index('X', inplace=True, drop=True)
    cdata = cdata[cdata.index.notnull()]
    datasets[color] = cdata

spectral_data = pd.concat(datasets.values()).sort_index()

# https://stackoverflow.com/questions/35855772/pandas-merge-duplicate-index-into-single-index
spectral_data = spectral_data.groupby(spectral_data.index).sum(min_count=1)

# https://stackoverflow.com/questions/41493282/in-python-pandas-how-can-i-re-sample-and-interpolate-a-dataframe
ssfstep = 5
ssf_bands = np.arange(400,720 + ssfstep,ssfstep)
spectral_data = spectral_data.reindex(spectral_data.index.union(ssf_bands))

# https://stackoverflow.com/questions/68548971/linearly-extrapolate-pandas-dataframe-using-built-in-interpolate-method
spectral_data.interpolate(method='slinear', fill_value="extrapolate", limit_direction="both", inplace=True)

spectral_data = spectral_data.loc[ssf_bands]

plt.plot(spectral_data['Red'], color='r')
plt.plot(spectral_data['Green'], color='g')
plt.plot(spectral_data['Blue'], color='b')

plt.show()

#Convert to linear values
spectral_data = spectral_data.apply(lambda x: np.power(10,x))

# Generate dcamprof spectral JSON
filebase = os.path.splitext(args['input'].name)[0]
jsonname = filebase + ".json"

ssfdata = {'camera_name': filebase,
           'ssf_bands': [int(ssf_bands[0]), int(ssf_bands[-1]), 5],
           'red_ssf': spectral_data['Red'].tolist(),
           'green_ssf': spectral_data['Green'].tolist(),
           'blue_ssf': spectral_data['Blue'].tolist()}

with open(jsonname, 'w') as jsonfile:
    jsonfile.write(json.dumps(ssfdata, indent=4))