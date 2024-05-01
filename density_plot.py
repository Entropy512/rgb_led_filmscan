#!/usr/bin/env python3

'''
Converts a CSV file exported by WebPlotDigitizer ( https://apps.automeris.io/wpd/ ) to a dcamprof camera SSF JSON
For the time being, the column headers need fixing - Replace the empty entry to the right of Blue in the first row with Blue, etc.
'''
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
#from scipy.optimize import root, minimize_scalar

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--input', type=argparse.FileType('rb'), required=True,
    help='path to input files')

args = vars(ap.parse_args())

pd.options.mode.copy_on_write = True

density_data = pd.read_csv(args['input'], header=[0,1])

'''
WebPlotDigitizer exports in the order you added points, and has individual X values for each dataset instead of a single X column that is suitable for indexing,
so let's do some re-sorting.
'''
datasets = {}
for color in ['Red', 'Green', 'Blue']:
    cdata = density_data[color]
    cdata.rename(columns={'Y' : color}, inplace=True)
    cdata.set_index('X', inplace=True, drop=True)
    cdata = cdata[cdata.index.notnull()]
    datasets[color] = cdata

density_data = pd.concat(datasets.values()).sort_index()

# https://stackoverflow.com/questions/35855772/pandas-merge-duplicate-index-into-single-index
density_data = density_data.groupby(density_data.index).sum(min_count=1)

# https://stackoverflow.com/questions/41493282/in-python-pandas-how-can-i-re-sample-and-interpolate-a-dataframe
dstep = 0.1
exposure_vals = np.arange(-3.62,1.0 + dstep, dstep)
density_data = density_data.reindex(density_data.index.union(exposure_vals))

#TODO:  Determine if we need to bother with extrapolation and interpolation since we're just curve-fitting.  May cause more problems than it solves in this application.  The dangers of copypasta!
# https://stackoverflow.com/questions/68548971/linearly-extrapolate-pandas-dataframe-using-built-in-interpolate-method
density_data.interpolate(method='slinear', fill_value="extrapolate", limit_direction="both", inplace=True)

density_data = density_data.loc[exposure_vals]

density_data['Red'] -= density_data['Red'].min()
density_data['Green'] -= density_data['Green'].min()
density_data['Blue'] -= density_data['Blue'].min()


plt.figure()
plt.semilogx(np.power(10.0,-density_data['Red']), np.log2(np.power(10,density_data.index)), color='r', alpha=0.5, label='Film Red')
plt.semilogx(np.power(10.0,-density_data['Green']), np.log2(np.power(10,density_data.index)), color='g', alpha=0.5, label='Film Green')
plt.semilogx(np.power(10.0,-density_data['Blue']), np.log2(np.power(10,density_data.index)), color='b', alpha=0.5, label='Film Blue')

def tcoeff_to_scenelin(tcoeff, exp, linadj, strexp):
    scenelin = np.power(tcoeff, -exp)/np.power(10.0,2.8)
    return np.power((np.power(scenelin,strexp)-linadj)/(1-linadj), 1.0/strexp)

""" 
def equations(evadj, outref, strexp):
    print()
    print(evadj)
    linadj = np.power(2.0,-evadj)
    print(np.log2(outref))
    #Exp doesn't matter below since we're passing a tcoeff of 1, so just hardcode to -1.5, better than rewriting the function a second time
    res = np.abs(np.log2(tcoeff_to_scenelin(1.0, 1.5, linadj, strexp)) - np.log2(outref))
    print(res)
    return res

min_evadj = -np.log2(np.power(1.0/np.power(10,2.8),strexp))
bounds = [min_evadj,40]
soln = minimize_scalar(equations, bounds=bounds, args=(np.power(10,-3.62), strexp))
print(soln)
"""

filmdata = {'Fuji Superia X-Tra 400':   {'inref' : np.power(10.0,-2.8),
                                        'evdelt' : 2.724,
                                        'exp' : {'r' : 1.6,
                                                'g' : 1.48,
                                                'b' : 1.45},
                                        'cstr': {'r' : 1.2,
                                                'g' : 2.0,
                                                'b' : 2.6}
                                        }}

density_vals = np.linspace(0,2.5,2000)
tcoeff_vals = np.power(10,-(density_vals))

film = 'Fuji Superia X-Tra 400'
inref = filmdata[film]['inref']
evdelt = filmdata[film]['evdelt']
outref = inref*np.power(2.0,-evdelt)

for color in ['r', 'g', 'b']:
    exp = filmdata[film]['exp'][color]
    cstr = filmdata[film]['cstr'][color]
    linadj = (np.power(outref,cstr)-np.power(inref,cstr))/(np.power(outref,cstr)-1)
    plt.semilogx(np.power(10,-density_vals), np.log2(tcoeff_to_scenelin(tcoeff_vals, exp, 0.0, 1.0)), color=color, dashes=[1,3], label='Simple Exponent (exp = -{})'.format(exp))
    plt.semilogx(np.power(10,-density_vals), np.log2(tcoeff_to_scenelin(tcoeff_vals, exp, linadj, cstr)), color=color, dashes=[2,1], label='Enhanced Model (exp = -{}, str={})'.format(exp,cstr))

exp = 1.6
strexp = 1.2



plt.xlabel('Normalized Transmission Coefficient (Orange Mask = 1.0)')
plt.ylabel('Scene Light (EV)')
plt.title('Scene Light vs. Film Transmission Coefficient for' + film)
plt.legend()
plt.show()

