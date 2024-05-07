#!/usr/bin/env python3

'''
Tri-color capture tool inspired by https://discuss.pixls.us/t/digitizing-film-using-dslr-and-rgb-led-lights/18825
'''
import argparse
from time import sleep
import rawpy
import gphoto2 as gp
import numpy as np
from fractions import Fraction
import logging
from neewer_light import NeewerLight
import tifffile as TIFF
import pyexiv2

def empty_event_queue(camera):
    while True:
        type_, data = camera.wait_for_event(10)
        if type_ == gp.GP_EVENT_TIMEOUT:
            return
        if type_ == gp.GP_EVENT_FILE_ADDED:
            # get a second image if camera is set to raw + jpeg
            print('Unexpected new file', data.folder + data.name)

#fugly, find a better solution for generating RATIONAL/SRATIONAL
def cm_to_flatrational(input_array):
    retarray = np.ones(input_array.size*2, dtype=np.int32)
    retarray[0::2] = (input_array.flatten()*10000).astype(np.int32)
    retarray[1::2] = 10000
    return retarray

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
ap.add_argument('-a', '--address', required=False, type=str,
                help='BLE address of Neewer light')

args = vars(ap.parse_args())

with NeewerLight(address=args['address']) as light:
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
    bayer_data = rawfile.raw_image.astype('uint16')

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
    bayer_data = rawfile.raw_image.astype('uint16')

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

    bayer_pattern = rawfile.raw_pattern.astype(np.uint8)
    bayer_data = rawfile.raw_image.astype('uint16')

    #This is the last image, pull all of the other metadata we need for our DNG
    WB_AsShot = rawfile.camera_whitebalance
    WhiteLevel = rawfile.white_level
    WhiteLevel_perChannel = np.array(rawfile.camera_white_level_per_channel, dtype=np.uint16)
    BlackLevel_perChannel = np.array(rawfile.black_level_per_channel, dtype=np.uint16)
    blacklevel_array = np.array(BlackLevel_perChannel)[bayer_pattern].astype(np.uint16)
    CM_XYZ2camRGB = rawfile.rgb_xyz_matrix

    iBrow,  iBclmn  = np.argwhere(bayer_pattern == 2)[0]

    B  = bayer_data[ iBrow::2,  iBclmn::2]

    print("Blue max:" + str(np.amax(B)))
    print("Blue min:" + str(np.amin(B)))

    #Create our merged DNG from our three captures
    bayer_data[ iBrow::2,  iBclmn::2] = B
    bayer_data[iG0row::2, iG0clmn::2] = G
    bayer_data[iG1row::2, iG1clmn::2] = G1
    bayer_data[ iRrow::2,  iRclmn::2] = R

    #Massive amount of copypasta from libraw2dng in my pyimageconvert repo
    #FIXME: Rework it all to reuse this boilerplate properly
    preserved_keys = ['Exif.Photo.LensModel',
                'Exif.Photo.LensModel',
                'Exif.Photo.FocalLengthIn35mmFilm',
                'Exif.Photo.FocalLength',
                'Exif.Photo.FNumber',
                'Exif.Photo.ExposureTime',
                'Exif.Image.Make',
                'Exif.Image.Model',
                'Exif.Image.Orientation',
                'Exif.Image.DateTime',
                'Exif.Sony2.SonyModelID', #not sure if we want to keep this?
                'Exif.Sony2.LensID', #needed for RT to get lens data
                'Exif.Photo.ISOSpeedRatings']
    
    with pyexiv2.Image('blue.ARW') as exiv_file:
        exif_data = exiv_file.read_exif()
        preserved_data = {k: exif_data[k] for k in set(preserved_keys).intersection(exif_data.keys())}

    """     
        for i in range(blacklevel_array.shape[0]):
            for j in range(blacklevel_array.shape[1]):
                bayer_data[i::blacklevel_array.shape[0], j::blacklevel_array.shape[1]] -= blacklevel_array[i][j]

        avg_blacklevel = np.mean(BlackLevel_perChannel)
        wpoint = 65504 #Largest value representable in a float16
        bayer_data *= wpoint/(WhiteLevel - avg_blacklevel)

        if(np.amax(bayer_data) > 65504):
            scalefac = 65504/np.amax(bayer_data)
            bayer_data *= scalefac
            wpoint *= scalefac
    """
    #RT crashes badly if we preserve G1 as 3 instead of mapping it to 1.  TODO:  Check what DNG spec says about this.
    bayer_pattern[bayer_pattern == 3] = 1

    #FIXME:  Handle this better/more flexibly/more cleanly
    #FIXME:  The camera color metadata is meaningless for an RGB capture like this, figure out an appropriate cmatrix.  Fixing that likely fixes the prior FIXME
    cmatrix = CM_XYZ2camRGB[:-1,:]

    unique_cam_model = preserved_data['Exif.Image.Make'] + " " + preserved_data['Exif.Image.Model']

    dng_extratags = []
    dng_extratags.append(('CFARepeatPatternDim', 'H', len(bayer_pattern.shape), bayer_pattern.shape, 0))
    dng_extratags.append(('CFAPattern', 'B', bayer_pattern.size, bayer_pattern.flatten()))
    dng_extratags.append(('ColorMatrix1', '2i', cmatrix.size, cm_to_flatrational(cmatrix)))
    dng_extratags.append(('CalibrationIlluminant1', 'H', 1, 21)) #is there an enum for this in tifffile???
    dng_extratags.append(('BlackLevelRepeatDim', 'H', 2, blacklevel_array.shape)) #BlackLevelRepeatDim
    dng_extratags.append(('BlackLevel', 'H', blacklevel_array.size, blacklevel_array.flatten().astype(np.uint16))) #We subtracted the black level already
    dng_extratags.append(('WhiteLevel', 'H', 1, WhiteLevel)) #WhiteLevel, scaled by us to the max for a float64
    dng_extratags.append(('DNGVersion', 'B', 4, [1,4,0,0])) #DNGVersion
    dng_extratags.append(('DNGBackwardVersion', 'B', 4, [1,4,0,0])) #DNGBackwardVersion
    #Since we normalized our channels, our AsShotNeutral is close to 1
    #FIXME: Derive AsShotNeutral from the maximum of each channel
    dng_extratags.append(('AsShotNeutral', '2I', 3, np.array([1,1,1,1,1,1], dtype=np.uint32)))
    dng_extratags.append(('UniqueCameraModel', 's', len(unique_cam_model), unique_cam_model))

    with TIFF.TiffWriter(args['output']) as dng:
        dng.write(bayer_data.astype(np.uint16),
                photometric='CFA',
                compression=None,
                extratags=dng_extratags,
                subfiletype=0)

    with pyexiv2.Image(args['output']) as dng:
        dng.modify_exif(preserved_data)