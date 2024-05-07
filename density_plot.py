#!/usr/bin/env python3

'''
Converts a CSV file exported by WebPlotDigitizer ( https://apps.automeris.io/wpd/ ) to a dcamprof camera SSF JSON
For the time being, the column headers need fixing - Replace the empty entry to the right of Blue in the first row with Blue, etc.
'''
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from functools import partial

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--input', type=argparse.FileType('rb'), required=True,
    help='path to input files')
ap.add_argument('--dmax', type=float, default=1.5,
    help='maximum density for exponent fitting')
ap.add_argument('--dmin', type=float, default=0.5,
    help='minimum density for exponent fitting')

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
    # For now, handle Kodak Gold being nonmonotonic in blue by forcing it to be monotonic, since there's no sane way to invert such a curve
    cdata[color] = np.flip(np.minimum.accumulate(np.flip(cdata[color])))
    datasets[color] = cdata

density_data = pd.concat(datasets.values()).sort_index()

# https://stackoverflow.com/questions/35855772/pandas-merge-duplicate-index-into-single-index
density_data = density_data.groupby(density_data.index).sum(min_count=1)


density_data.rename(columns={'Red' : 'r', 'Green' : 'g', 'Blue' : 'b'}, inplace=True)

density_data.r -= density_data.r.min()
density_data.g -= density_data.g.min()
density_data.b -= density_data.b.min()

# https://stackoverflow.com/questions/43781465/how-to-swap-index-and-values-on-pandas-dataframe
scene_data = density_data.stack().reset_index()
scene_data.columns = ['i', 'c', 'd']

scene_data = scene_data.pivot_table(index='d', columns='c', values='i')

# https://stackoverflow.com/questions/41493282/in-python-pandas-how-can-i-re-sample-and-interpolate-a-dataframe
istep = 0.1
exposure_vals = np.arange(-3.62,1.0 + istep, istep)
density_data = density_data.reindex(density_data.index.union(exposure_vals))

dstep = 0.01
density_vals = np.arange(0, 2.5 + dstep, dstep)
scene_data = scene_data.reindex(scene_data.index.union(density_vals))

#TODO:  Determine if we need to bother with extrapolation and interpolation since we're just curve-fitting.  May cause more problems than it solves in this application.  The dangers of copypasta!
# https://stackoverflow.com/questions/68548971/linearly-extrapolate-pandas-dataframe-using-built-in-interpolate-method
density_data.interpolate(method='slinear', fill_value="extrapolate", limit_direction="both", inplace=True)
density_data = density_data.loc[exposure_vals]

scene_data.interpolate(method='slinear', fill_value="extrapolate", limit_direction="both", inplace=True)
scene_data = scene_data.loc[density_vals]


def tcoeff_to_scenelin(tcoeff, reflevel, exp, linadj, strexp):
    scenelin = np.power(tcoeff, -exp)*reflevel
    return np.power((np.power(scenelin,strexp)-linadj), 1.0/strexp)

'''
curve_fit doesn't support fitting three datasets with one common variable and one independent variable
but it doesn't care about the order of your data

So repeat the X data 3 times, and concatenate the Y data for R, G, and B.

Similarly concatenate our fit function's results the same way
'''

def fitfunc1(tcoeff, reflevel ,rexp, gexp, bexp):
    tcoeff = tcoeff.reshape(-1,3)
    return np.concatenate((np.log10(tcoeff_to_scenelin(tcoeff[:,0], reflevel, rexp, 0, 1)).flatten(),
                        np.log10(tcoeff_to_scenelin(tcoeff[:,1], reflevel, gexp, 0, 1)).flatten(),
                        np.log10(tcoeff_to_scenelin(tcoeff[:,2], reflevel, bexp, 0, 1)).flatten()))


fit_df = scene_data.loc[(args['dmin'] <= scene_data.index) & (scene_data.index <= args['dmax'])]

fit_tcoeff = np.repeat(np.power(10,-fit_df.index),3).to_numpy()
fit_data = np.concatenate((fit_df.r , fit_df.g , fit_df.b))

p0 = [1.0, 1.5, 1.5, 1.5]
(soln, cov) = curve_fit(fitfunc1, fit_tcoeff, fit_data, p0, bounds=((-np.inf,0, 0, 0), (np.inf,5.0,5.0,5.0)))
scenemin = np.mean(scene_data.iloc[0])*np.log2(10)
evdelt = np.log2(soln[0])-scenemin

def fitfunc2(tcoeff, curvr, curvg, curvb, evdelt, reflevel ,rexp, gexp, bexp):
    tcoeff = tcoeff.reshape(-1,3)
    linadjr = np.power(reflevel,curvr) - np.power(reflevel*np.power(2,-evdelt),curvr)
    linadjg = np.power(reflevel,curvg) - np.power(reflevel*np.power(2,-evdelt),curvg)
    linadjb = np.power(reflevel,curvb) - np.power(reflevel*np.power(2,-evdelt),curvb)
    return np.concatenate((np.log10(tcoeff_to_scenelin(tcoeff[:,0], reflevel, rexp, linadjr, curvr)).flatten(),
                        np.log10(tcoeff_to_scenelin(tcoeff[:,1], reflevel, gexp, linadjg, curvg)).flatten(),
                        np.log10(tcoeff_to_scenelin(tcoeff[:,2], reflevel, bexp, linadjb, curvb)).flatten()))

fit_df = scene_data.loc[(0.0 <= scene_data.index) & (scene_data.index <= args['dmax'])]

fit_tcoeff = np.repeat(np.power(10,-fit_df.index),3).to_numpy()
fit_data = np.concatenate((fit_df.r , fit_df.g , fit_df.b))

p0 = [1.0, 1.0, 1.0]
(soln2, cov) = curve_fit(partial(fitfunc2, evdelt = evdelt, reflevel = soln[0], rexp = soln[1], gexp = soln[2], bexp = soln[3]), fit_tcoeff, fit_data, p0, bounds=((0, 0, 0), (5.0,5.0,5.0)))

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

filmdata =  {'Fuji Superia X-Tra 400':   {'inref' : np.power(2.0,-9.3014),
                                        'evdelt' : 2.724,
                                        'exp' : {'r' : 1.6,
                                                'g' : 1.48,
                                                'b' : 1.45},
                                        'cstr': {'r' : 1.5,
                                                'g' : 2.0,
                                                'b' : 2.6}
                                        },
            'Kodak Gold 200':   {'inref' : np.power(2.0,-7.95),
                                        'evdelt' : 4.0,
                                        'exp' : {'r' : 1.83,
                                                'g' : 1.72,
                                                'b' : 1.65},
                                        'cstr': {'r' : 2.0,
                                                'g' : 1.8,
                                                'b' : 3.0}
                                        },
           'Fit To Data':   {'inref' : soln[0],
                                        'evdelt' : evdelt,
                                        'exp' : {'r' : soln[1],
                                                'g' : soln[2],
                                                'b' : soln[3]},
                                        'cstr': {'r' : soln2[0],
                                                'g' : soln2[1],
                                                'b' : soln2[2]}
                                        }
            }

density_vals = np.linspace(0,2.5,2000)
tcoeff_vals = np.power(10,-(density_vals))

film = 'Fit To Data'
inref = filmdata[film]['inref']
evdelt = filmdata[film]['evdelt']
outref = inref*np.power(2.0,-evdelt)
plotnum = 0
pltn = None

print("RawTherapee exponent settings:")
print("Reference power: " + str(filmdata[film]['exp']['g']))
print("Red ratio: " + str(filmdata[film]['exp']['r']/filmdata[film]['exp']['g']))
print("Blue ratio:" + str(filmdata[film]['exp']['b']/filmdata[film]['exp']['g']))
fig, axs = plt.subplots(2,2, sharex=True, sharey=True)
axs[-1,-1].axis('off')
fig.suptitle('Scene Light vs. Film Transmission Coefficient for ' + film)
for color in ['r', 'g', 'b']:
    exp = filmdata[film]['exp'][color]
    cstr = filmdata[film]['cstr'][color]
    linadj = np.power(inref,cstr) - np.power(outref,cstr)
    pltn = axs[plotnum % 2, plotnum // 2]
    plotnum += 1

    pltn.xaxis.set_tick_params(labelbottom=True)
    pltn.yaxis.set_tick_params(labelbottom=True)
    pltn.plot(scene_data.index, np.log2(np.power(10,scene_data[color])), color=color, alpha=0.5, label='Film Response')
    pltn.plot(density_vals, np.log2(tcoeff_to_scenelin(tcoeff_vals, inref, exp, 0.0, 1.0)), color=color, dashes=[1,3], label='Simple Exponent (exp = -{:.2f})'.format(exp))
    pltn.plot(density_vals, np.log2(tcoeff_to_scenelin(tcoeff_vals, inref, exp, linadj, cstr)), color=color, dashes=[2,1], label='Enhanced Model (exp = -{:.2f}, str={:.2f})'.format(exp,cstr))
    pltn.axvline(x=args['dmin'], alpha=0.5)
    pltn.axvline(x=args['dmax'], alpha=0.5)
    pltn.set_xlabel('Density difference from Dmin')
    pltn.set_ylabel('Scene Light (EV)')
    pltn.grid()
    pltn.legend()


plt.show()

