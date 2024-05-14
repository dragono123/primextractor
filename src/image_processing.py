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
        img = cv2.resize(img, None, fx=size, fy=size,
                         interpolation=cv2.INTER_AREA)
    return img


def set_treshold(img, treshold, filter_size):
    if filter_size > 1:
        img = cv2.adaptiveThreshold(img, 255,
                                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY,
                                    int(filter_size), 2)
    else:
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
    subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png"],
                   stdin=current_image)


def set_inverted(img, inverted):
    if inverted:
        img = cv2.bitwise_not(img)
    return img


def apply_filter(img, feathering, erosion, dilation):
    if int(feathering) > 0:
        cv2.imwrite("processed/text_to_clean2.png", img)
        qrange = subprocess.check_output(
                "convert xc: -format \"%[fx:quantumrange]\" info:".split())
        qrange = qrange.decode("utf-8")[1:-1]

        subprocess.run(["convert", "processed/text_to_clean2.png", "-blur",
                        f"{feathering}x{qrange}", "-level", "50%,100%",
                        "-define", "png:color-type=6",
                        "processed/text_cleaned2.png"])

        img = cv2.imread("processed/text_cleaned2.png")
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


def clear_image(img, inverted, clear):
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if clear:
        im_floodfill = img.copy()
        h, w = im_floodfill.shape[:2]

        for x in range(w):
            end_h = h - 1
            points = [(x, 0), (x, end_h)]
            for point in points:
                if any(value != 255 for value in
                       im_floodfill[point[1], point[0]]):
                    cv2.floodFill(im_floodfill, None, point, (255, 255, 255))
        for y in range(h):
            end_w = w - 1
            points = [(0, y), (end_w, y)]
            for point in points:
                if any(value != 255 for value
                       in im_floodfill[point[1], point[0]]):
                    cv2.floodFill(im_floodfill, None, point, (255, 255, 255))
        img = im_floodfill
    return img
