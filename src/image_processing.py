#!/usr/bin/env python3

import subprocess
import time
import struct
import cv2
import io
import numpy as np
import os
import configparser
import configargparse
import imutils
import pyperclip
from scipy import ndimage
from PIL import Image, ImageFilter, ImageChops


def rotate_image(img, rotation):
    rotation *= -1
    img = np.array(img)
    img = ndimage.rotate(img, angle=rotation)
    return img


def resize_image(img, size):
    if size > 1:
        image = Image.fromarray(img)
        width, height = image.size
        new_size = (int(width * size), int(height*size))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        img = np.array(image)
    elif size < 1 and size > 0:
        img = cv2.resize(img, None, fx=size, fy=size, interpolation=cv2.INTER_AREA)
    return img


def set_treshold(img, treshold):
    img = cv2.threshold(img, treshold, 255, cv2.THRESH_BINARY)[1]
    return img


def convert_to_gray(img, enable_colordiff, color):
    if enable_colordiff and color != "":
        color = color[1:]
        img = Image.fromarray(img)
        color = struct.unpack('BBB', bytes.fromhex(color))
        background_color = Image.new('RGB', img.size, color)
        img = ImageChops.difference(img, background_color)
        img = np.asarray(img)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def copy_final_result():
    current_image = open("processed/current_image.png")
    subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png"], stdin=current_image)


def set_inverted(img, inverted):
    if inverted:
        img = cv2.bitwise_not(img)
    return img


def clean_text(img, invert_cleaner, filter_size):
    if int(filter_size) > 0:
        cv2.imwrite("processed/text_to_clean.png", img)
        if int(invert_cleaner) > 0:
            subprocess.run(["scripts/textcleaner", "-i", str(invert_cleaner), "-f", str(filter_size), "processed/text_to_clean.png", "processed/text_cleaned.png"])
        else:
            subprocess.run(["scripts/textcleaner", "-f", str(filter_size), "processed/text_to_clean.png", "processed/text_cleaned.png"])
        img = cv2.imread("processed/text_cleaned.png")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def first_filter(img, isonoise):
    if int(isonoise) > 0:
        cv2.imwrite("processed/text_to_clean2.png", img)
        subprocess.run(["scripts/noisecleaner", "processed/text_to_clean2.png", "processed/text_to_clean3.png"])
        subprocess.run(["scripts/isonoise", "processed/text_to_clean3.png", "processed/text_cleaned2.png"])
        img = cv2.imread("processed/text_cleaned2.png")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def second_filter(img, isonoise, feathering, erosion, dilation):
    if int(isonoise) > 0:
        cv2.imwrite("processed/text_to_clean2.png", img)
        subprocess.run(["scripts/isonoise", "-r", str(isonoise), "processed/text_to_clean2.png", "processed/text_cleaned2.png"])
        img = cv2.imread("processed/text_cleaned2.png")
    
        cv2.imwrite("processed/text_to_clean2.png", img)
        subprocess.run(["scripts/noisecleaner", "processed/text_to_clean2.png", "processed/text_cleaned2t.png"])
        img = cv2.imread("processed/text_cleaned2.png")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if int(feathering) > 0:
        # img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_AREA)
        cv2.imwrite("processed/text_to_clean2.png", img)
        subprocess.run(["scripts/feather", "-d", str(feathering), "processed/text_to_clean2.png", "processed/text_cleaned2.png"])
        img = cv2.imread("processed/text_cleaned2.png")
        # img = cv2.resize(img, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
    erosion = int(erosion)
    dilation = int(dilation)
    if erosion > 0:
        kernel = np.ones((erosion, erosion), np.uint8)
        img = cv2.erode(img, kernel)
    
    if dilation > 0:
        kernel = np.ones((dilation, dilation), np.uint8)
        img = cv2.dilate(img, kernel)
    return img


def clear_image(img, inverted, clear, invert_cleaner):
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if clear:
        if invert_cleaner > 0:

            im_floodfill = img.copy()
            h, w = im_floodfill.shape[:2]

            white_lo = np.array((254, 254, 254))
            white_hi = np.array((255, 255, 255))
            black_lo = np.array((0, 0, 0))
            black_hi = np.array((1, 1, 1))
            blue_lo = np.array((254, 0, 0))
            blue_hi = np.array((255, 0, 0))

            if inverted != invert_cleaner:
                mask = cv2.inRange(im_floodfill, white_lo, white_hi)
            else:
                mask = cv2.inRange(im_floodfill, black_lo, black_hi)
            im_floodfill[mask > 0] = (255, 0, 0)

            for x in range(w):
                end_h = h - 1
                points = [(x, 0), (x, end_h)]
                for point in points:
                    if inverted != invert_cleaner:
                        if any(value != 255 for value in im_floodfill[point[1], point[0]]):
                            cv2.floodFill(im_floodfill, None, point, (255, 255, 255))
                    else:
                        if any(value != 0 for value in im_floodfill[point[1], point[0]]):
                            cv2.floodFill(im_floodfill, None, point, (0, 0, 0))
            for y in range(h):
                end_w = w - 1
                points = [(0, y), (end_w, y)]
                for point in points:
                    if inverted != invert_cleaner:
                        if any(value != 255 for value in im_floodfill[point[1], point[0]]):
                            cv2.floodFill(im_floodfill, None, point, (255, 255, 255))
                    else:
                        if any(value != 0 for value in im_floodfill[point[1], point[0]]):
                            cv2.floodFill(im_floodfill, None, point, (0, 0, 0))

            if inverted != invert_cleaner:
                mask=cv2.inRange(im_floodfill,black_lo,black_hi)
                im_floodfill[mask>0]=(255,255,255)
            else:
                mask=cv2.inRange(im_floodfill,white_lo,white_hi)
                im_floodfill[mask>0]=(0,0,0)

            mask=cv2.inRange(im_floodfill,blue_lo,blue_hi)
            if inverted != invert_cleaner:
                im_floodfill[mask>0]=(0, 0, 0)
            else:
                im_floodfill[mask>0]=(255, 255, 255)

            img = im_floodfill
        else:

            im_floodfill = img.copy()
            h, w = im_floodfill.shape[:2]

            for x in range(w):
                end_h = h - 1
                points = [(x, 0), (x, end_h)]
                for point in points:
                    if any(value != 255 for value in im_floodfill[point[1], point[0]]):
                        cv2.floodFill(im_floodfill, None, point, (255, 255, 255))
            for y in range(h):
                end_w = w - 1
                points = [(0, y), (end_w, y)]
                for point in points:
                    if any(value != 255 for value in im_floodfill[point[1], point[0]]):
                        cv2.floodFill(im_floodfill, None, point, (255, 255, 255))
            img = im_floodfill
    return img

