#!/usr/bin/env python3

import argparse
from time import sleep
import rawpy
import gphoto2 as gp
import numpy as np
from fractions import Fraction
import logging
from neewer_light import NeewerLight

def empty_event_queue(camera):
    while True:
        type_, data = camera.wait_for_event(10)
        if type_ == gp.GP_EVENT_TIMEOUT:
            return
        if type_ == gp.GP_EVENT_FILE_ADDED:
            # get a second image if camera is set to raw + jpeg
            print('Unexpected new file', data.folder + data.name)



logging.basicConfig(
    format='%(levelname)s: %(name)s: %(message)s', level=logging.ERROR)
callback_obj = gp.check_result(gp.use_python_logging())

ap = argparse.ArgumentParser()
ap.add_argument('-o', '--output', required=True,
    help='path to output DNG')
ap.add_argument('-s', '--shutter_speed', required=True,
                help='Shutter Speed')
ap.add_argument('-r', '--rgb', required=True, nargs=3, type=int,
                help='RGB intensities for Neewer light, 0-100')

args = vars(ap.parse_args())

with NeewerLight() as light:
    print("Initializing camera")
    camera = gp.Camera()
    camera.init()
    print("Discovering Neewer light")
    light.find_device()
    if(light.neewer_device is None):
        print("No device found")
        exit(0)

    print("Neewer light found")


    print ("Configuring camera")
    # get configuration tree
    cfg = camera.get_config()
    capturetarget_cfg = cfg.get_child_by_name('capturetarget')
    capturetarget_cfg.set_value('sdram')
    camera.set_config(cfg)
    shutterspeed_cfg = cfg.get_child_by_name('shutterspeed')
    speeds_byname = []
    speeds = []
    for j in range(shutterspeed_cfg.count_choices()):
        choice = shutterspeed_cfg.get_choice(j)
        if choice != 'Bulb':
            speeds_byname.append(choice)
            speeds.append(Fraction(choice))
    idx = speeds.index(Fraction(args['shutter_speed']))
    shutterspeed_cfg.set_value(speeds_byname[idx])
    print("Setting shutter speed")
    camera.set_config(cfg)

    print()
    light.set_HSI(0, 100, args['rgb'][0])
    sleep(0.1)

    path = camera.capture(gp.GP_CAPTURE_IMAGE)
    camera_file = camera.file_get(path.folder, path.name, gp.GP_FILE_TYPE_NORMAL)
    camera_file.save('red.ARW')
    sleep(0.1)
    camera.file_delete(path.folder, path.name)
    empty_event_queue(camera)

    rawfile = rawpy.imread('red.ARW')

    bayer_pattern = rawfile.raw_pattern
    bayer_data = rawfile.raw_image.astype('float64')

    iRrow,  iRclmn  = np.argwhere(bayer_pattern == 0)[0]

    R  = bayer_data[ iRrow::2,  iRclmn::2]

    print("Red max:" + str(np.amax(R)))
    print("Red min:" + str(np.amin(R)))

    print()
    light.set_HSI(120, 100, args['rgb'][1])
    sleep(0.1)

    empty_event_queue(camera)
    print("\nCapturing green")
    path = camera.capture(gp.GP_CAPTURE_IMAGE)
    print("Captured")
    camera_file = camera.file_get(path.folder, path.name, gp.GP_FILE_TYPE_NORMAL)
    camera_file.save('green.ARW')
    sleep(0.2)
    camera.file_delete(path.folder, path.name)



    rawfile = rawpy.imread('green.ARW')

    bayer_pattern = rawfile.raw_pattern
    bayer_data = rawfile.raw_image.astype('float64')

    iG0row, iG0clmn = np.argwhere(bayer_pattern == 1)[0]
    iG1row, iG1clmn = np.argwhere(bayer_pattern == 3)[0]

    G = bayer_data[iG0row::2, iG0clmn::2]
    G1 = bayer_data[iG1row::2, iG1clmn::2]

    print("Green max:" + str(np.amax(G)))
    print("Green2 max:" + str(np.amax(G1)))
    print("Green min:" + str(np.amin(G)))
    print("Green2 min:" + str(np.amin(G1)))

    print()
    light.set_HSI(240, 100, args['rgb'][2])
    sleep(0.1)

    empty_event_queue(camera)
    print("Capturing blue")
    path = camera.capture(gp.GP_CAPTURE_IMAGE)
    print("Captured")
    camera_file = camera.file_get(path.folder, path.name, gp.GP_FILE_TYPE_NORMAL)
    camera_file.save('blue.ARW')
    sleep(0.2)
    camera.file_delete(path.folder, path.name)



    rawfile = rawpy.imread('blue.ARW')

    bayer_pattern = rawfile.raw_pattern
    bayer_data = rawfile.raw_image.astype('float64')

    iBrow,  iBclmn  = np.argwhere(bayer_pattern == 2)[0]

    B  = bayer_data[ iBrow::2,  iBclmn::2]

    print("Blue max:" + str(np.amax(B)))
    print("Blue min:" + str(np.amin(B)))