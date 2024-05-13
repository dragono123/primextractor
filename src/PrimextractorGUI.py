#!/usr/bin/env python3

import subprocess
import time
import struct
import pytesseract
import cv2
import io
import numpy as np
import os
import configparser
import configargparse
import imutils
import pyperclip
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd
from scipy import ndimage
from PIL import Image, ImageTk, ImageFilter, ImageChops
from image_processing import *


class Widget():
    def __init__(self):
        self.valuename = ""
        self.widgetname = ""
        self.associatedValue = None
        self.tkWidget = None

    def add_widget_to_primextractor(self, primextractor):
        primextractor.add_widget(self.widgetname, self)

    def add_value_to_primextractor(self, primextractor):
        primextractor.add_value(self.valuename, self.associatedValue)

    def set_grid(self, column, row, columnspan=1, rowspan=1):
        self.tkWidget.grid(column=column, row=row,
                           columnspan=columnspan, rowspan=rowspan)


class ButtonWidget(Widget):
    def __init__(self, primextractor, widgetname, frame, text, command=None):
        self.widgetname = widgetname
        if command is not None:
            self.tkWidget = ttk.Button(frame, text=text, command=command)
        else:
            self.tkWidget = ttk.Button(frame, text=text)

        self.add_widget_to_primextractor(primextractor)


class CheckButtonWidget(Widget):
    def __init__(self, primextractor, valuename, frame, text):
        self.widgetname = valuename
        self.valuename = valuename
        self.associatedValue = tk.IntVar()
        self.tkWidget = ttk.Checkbutton(frame, text=text,
                                        onvalue=1, offvalue=0,
                                        variable=self.associatedValue)
        self.add_widget_to_primextractor(primextractor)
        self.add_value_to_primextractor(primextractor)


class ScaleWidget(Widget):
    def __init__(self, primextractor, valuename, frame,
                 interval, resolution=1, tickinterval=None):
        self.valuename = valuename
        if resolution % 1 == 0 and interval[0] % 1 == 0 \
                and interval[1] % 1 == 0:
            self.associatedValue = tk.IntVar()
        else:
            self.associatedValue = tk.DoubleVar()

        self.widgetname = valuename
        if tickinterval is None:
            self.tkWidget = tk.Scale(frame, from_=interval[0],
                                     to=interval[1], orient='horizontal',
                                     resolution=resolution,
                                     variable=self.associatedValue)
        else:
            self.tkWidget = tk.Scale(frame, from_=interval[0],
                                     to=interval[1], orient='horizontal',
                                     resolution=resolution,
                                     variable=self.associatedValue,
                                     tickinterval=tickinterval)
        self.add_widget_to_primextractor(primextractor)
        self.add_value_to_primextractor(primextractor)


class CanvasWidget(Widget):
    def __init__(self, primextractor, widgetname, frame, width, height):
        self.widgetname = widgetname
        self.width = width
        self.height = height
        self.image = None
        self.original = False
        self.tkWidget = tk.Canvas(frame, width=width, height=height)
        self.tkWidget.pack(anchor=tk.CENTER, expand=True)
        self.add_widget_to_primextractor(primextractor)

    def is_image_loaded(self):
        return (self.is_viewing_original() and
                os.path.exists("processed/original_image.png")) or \
            (not self.is_viewing_original and
             os.path.exists("processed/current_image.png"))

    def is_viewing_original(self):
        return self.original

    def is_viewing_processed(self):
        return not self.original

    def get_dims(self):
        return (self.width, self.height)

    def update_image(self, clipboard=False):
        if clipboard:
            image = Image.open("processed/original_image.png")
            self.original = True
        else:
            image = Image.open("processed/current_image.png")
            self.original = False
        image.thumbnail((self.width, self.height))
        background = Image.new('RGBA', (self.width, self.height),
                               (255, 255, 255, 255))
        bg_w, bg_h = background.size
        img_w, img_h = image.size
        offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
        background.paste(image, offset)
        image = background
        self.image = ImageTk.PhotoImage(image)
        self.tkWidget.create_image((0, 0), anchor="nw", image=self.image)

    def get_mouse_coords(self, event):
        return self.tkWidget.canvasx(event.x), \
            self.tkWidget.canvasy(event.y)

    def bind_function(self, function):
        self.tkWidget.bind('<Button-1>', function)


class ComboBoxWidget(Widget):
    def __init__(self, primextractor, valuename, frame,
                 combo_choices):
        self.valuename = valuename
        self.associatedValue = tk.StringVar()

        self.widgetname = valuename
        self.tkWidget = ttk.Combobox(frame, textvariable=self.associatedValue)
        self.tkWidget["state"] = "readonly"
        self.update_choices(combo_choices)

        self.add_widget_to_primextractor(primextractor)
        self.add_value_to_primextractor(primextractor)

    def update_choices(self, combo_choices):
        self.tkWidget["values"] = combo_choices

    def bind_function(self, function):
        self.tkWidget.bind('<<ComboboxSelected>>', function)


class DynamicLabelWidget(Widget):
    def __init__(self, primextractor, valuename, frame, text):
        self.widgetname = valuename
        self.valuename = valuename
        self.associatedValue = tk.StringVar()
        self.tkWidget = tk.Label(frame, width=42, height=5,
                                 textvariable=self.associatedValue)
        self.set_text(text)

        self.add_widget_to_primextractor(primextractor)
        self.add_value_to_primextractor(primextractor)

    def set_text(self, new_text):
        self.associatedValue.set(new_text)

    def set_bg_color(self, color):
        self.tkWidget.config(bg=color)


class PrimextractorGUI():
    def __init__(self, default_model=None):
        self.values = {}
        self.window = {}
        self.colors = []
        self.root = tk.Tk()

        self.root.title("Primextractor")
        window_width = 330
        window_height = 750

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        position_x = int(screen_width/4 - window_width/2)
        position_y = int(screen_height/4 - window_height/2)

        self.root.geometry(f'{window_width}x{window_height}+' +
                           f'{position_x}+{position_y}')
        self.generate_main_frame(self.root)
        if default_model is not None:
            self.update_interface_with_model(default_model)

    def get_canvas(self):
        return self.window["canvas"]

    def get_model_selector(self):
        return self.window["model_selection"]

    def add_one(self):
        self.set_value("rotation_factor",
                       self.get_value("rotation_factor") + 1)

    def add_five(self):
        self.set_value("rotation_factor",
                       self.get_value("rotation_factor") + 5)

    def sub_one(self):
        self.set_value("rotation_factor",
                       self.get_value("rotation_factor") - 1)

    def sub_five(self):
        self.set_value("rotation_factor",
                       self.get_value("rotation_factor") - 5)

    def set_zero(self):
        self.set_value("rotation_factor", 0)

    def get_extraction_results(self):
        return self.window["extraction_results"]

    def add_value(self, valuename, associatedValue):
        self.values[valuename] = associatedValue

    def add_widget(self, widgetname, widget):
        self.window[widgetname] = widget

    def loop(self):
        self.root.mainloop()

    def generate_main_frame(self, root):
        image_frame = ttk.Label(root)
        image_frame.grid(column=0, row=0)

        setting_frame = ttk.Frame(root)
        setting_frame.grid(column=0, row=1)

        menu_frame = ttk.Frame(root)
        menu_frame.grid(column=0, row=2)

        self.generate_setting_frame(setting_frame)
        self.generate_menu_frame(menu_frame)
        self.generate_image_frame(image_frame)

    def update_key(self, config, key, win_key):
        if "settings" in config and key in config["settings"]:
            self.set_value(win_key, config["settings"][key])

    def update_bool_key(self, config, key, win_key):
        if "settings" in config:
            if key in config["settings"] and\
                    config["settings"][key] == "True":
                self.set_value(win_key, 1)
            elif key in config["settings"] and\
                    config["settings"][key] == "False":
                self.set_value(win_key, 0)

    def update_interface_with_model(self, model):
        if os.path.exists(model):
            config = configparser.ConfigParser()
            config.read(model)
            self.update_key(config, "lang", "lang")
            self.update_key(config, "treshold", "treshold_factor")
            self.update_key(config, "psm", "psm")
            self.update_key(config, "size", "resizing_factor")
            self.update_key(config, "filter_size", "clean_filter_factor")
            self.update_key(config, "invert_cleaner", "cleaner_inverted_mod")
            self.update_bool_key(config, "inverted", "invert_image")
            self.update_bool_key(config, "clear", "clear_borders")
            self.update_key(config, "erosion", "erosion_factor")
            self.update_key(config, "dilationl", "dilation_factor")
            self.update_key(config, "rotation", "rotation_factor")
            self.update_key(config, "isonoise", "isonoise")
            self.update_key(config, "feathering", "feathering_factor")
            self.update_key(config, "oem", "oem")

    def update_from_selected_model(self, event):
        self.update_interface_with_model(self.get_value("model_selection"))
        self.update_list_models()

    def update_list_models(self):
        list_models = []
        list_models += [each for each in
                        os.listdir('.') if each.endswith('.ini')]
        selected_model = self.get_value("model_selection")
        self.get_model_selector().update_choices(list_models)
        if selected_model in list_models:
            self.set_value("model_selection", selected_model)

    def generate_image_frame(self, image_frame):
        CanvasWidget(self, "canvas", image_frame, 400, 400)
        self.get_canvas().bind_function(self.mouse_pressed_on_canvas)

    def generate_menu_frame(self, menu_frame):
        list_models = []
        list_models += [each for each in os.listdir('.')
                        if each.endswith('.ini')]

        ttk.Label(menu_frame, text='Model selection:').grid(column=0, row=0)
        model_selector = ComboBoxWidget(self, "model_selection",
                                        menu_frame, list_models)
        model_selector.set_grid(column=1, row=0)
        model_selector.bind_function(self.update_from_selected_model)

        ButtonWidget(self, "export_new_model", menu_frame,
                     "Export new model",
                     command=self.export_current_settings_as_model).\
            set_grid(column=2, row=0)

        option_frame = ttk.Frame(menu_frame)
        option_frame.grid(column=0, row=1, columnspan=3, rowspan=2)

        ButtonWidget(self, "image_clipboard",
                     option_frame, "Get Image from Clipboard:",
                     command=self.load_image_clipboard).\
            set_grid(column=0, row=0)
        ButtonWidget(self, "image_processing",
                     option_frame, "Process Image",
                     command=self.process_image).\
            set_grid(column=1, row=0)
        ButtonWidget(self, "extract_text",
                     option_frame, "Extract Text",
                     command=self.apply_tesseract).\
            set_grid(column=2, row=0)
        ButtonWidget(self, "clipboard_processing",
                     option_frame, "Clipboard+Processing",
                     command=self.clipboard_and_processing).\
            set_grid(column=0, row=1)
        ButtonWidget(self, "full_process",
                     option_frame, "Full Process",
                     command=self.full_process).\
            set_grid(column=1, row=1)
        ButtonWidget(self, "copy_processed_image",
                     option_frame, "Copy Processed Image",
                     command=self.copy_processed_image).\
            set_grid(column=2, row=1)

        result_frame = ttk.Frame(menu_frame)
        result_frame.grid(column=0, row=3, columnspan=3)
        DynamicLabelWidget(self, "extraction_results", result_frame, "test").\
            set_grid(column=0, row=0)

        color_frame = ttk.Frame(menu_frame)
        color_frame.grid(column=0, row=4, columnspan=3)
        DynamicLabelWidget(self, "displayed_color", color_frame, "#FFFFFF").\
            set_grid(column=0, row=0)

        ComboBoxWidget(self, "color_selection", color_frame, []).\
            set_grid(1, 0)

    def generate_setting_frame(self, setting_frame):
        ttk.Label(setting_frame, text='Rotation:').grid(column=0, row=0)
        ScaleWidget(self, "rotation_factor", setting_frame, (-90, 90),
                    tickinterval=45, resolution=1).\
            set_grid(column=1, row=0, columnspan=2)

        rotation_set_frame = ttk.Frame(setting_frame)
        rotation_set_frame.grid(column=3, row=0, columnspan=3)

        ButtonWidget(self, "sub_five", rotation_set_frame, "-5",
                     command=self.sub_five).\
            set_grid(column=0, row=0)
        ButtonWidget(self, "sub_one", rotation_set_frame, "-1",
                     command=self.sub_one).\
            set_grid(column=1, row=0)
        ButtonWidget(self, "set_zero", rotation_set_frame, "0",
                     command=self.set_zero).\
            set_grid(column=2, row=0)
        ButtonWidget(self, "add_one", rotation_set_frame, "+1",
                     command=self.add_one).\
            set_grid(column=3, row=0)
        ButtonWidget(self, "add_five", rotation_set_frame, "+5",
                     command=self.add_five).\
            set_grid(column=4, row=0)

        ttk.Label(setting_frame, text='Resize:').grid(column=0, row=1)
        ScaleWidget(self, "resizing_factor", setting_frame, (0.1, 5),
                    resolution=0.1).\
            set_grid(column=1, row=1, columnspan=2)

        ttk.Label(setting_frame, text='Treshold:').grid(column=0, row=2)
        ScaleWidget(self, "treshold_factor", setting_frame, (0, 255),
                    resolution=1).\
            set_grid(column=1, row=2, columnspan=2)

        ttk.Label(setting_frame, text='Image Cleaner Filter::').\
            grid(column=0, row=3)
        ScaleWidget(self, "clean_filter_factor", setting_frame, (0, 50),
                    resolution=0.1).\
            set_grid(column=1, row=3, columnspan=2)

        CheckButtonWidget(self, "invert_image", setting_frame,
                          "Invert Image").set_grid(column=0, row=4)
        CheckButtonWidget(self, "clear_borders", setting_frame,
                          "Clear Borders").set_grid(column=1, row=4)
        CheckButtonWidget(self, "color_diff_enabled", setting_frame,
                          "Enable Color Difference").set_grid(column=2, row=4)

        # Not sure if it is worth keeping
        ttk.Label(setting_frame, text='Text cleaner Inverted Mod Setting:').\
            grid(column=0, row=5)
        ComboBoxWidget(self, "cleaner_inverted_mod",
                       setting_frame, (0, 1, 2)).\
            set_grid(column=1, row=5)

        ttk.Label(setting_frame, text='PSM:').grid(column=0, row=6)
        ComboBoxWidget(self, "psm",
                       setting_frame, tuple(range(14))).\
            set_grid(column=1, row=6)

        ttk.Label(setting_frame, text='OEM:').grid(column=2, row=6)
        ComboBoxWidget(self, "oem",
                       setting_frame, tuple(range(4))).\
            set_grid(column=3, row=6)

        ttk.Label(setting_frame, text='Lang:').grid(column=4, row=6)
        ComboBoxWidget(self, "lang",
                       setting_frame, pytesseract.get_languages(config='')).\
            set_grid(column=5, row=6)

        ttk.Label(setting_frame, text='Feathering:').grid(column=0, row=7)
        ScaleWidget(self, "feathering_factor", setting_frame, (0, 10),
                    resolution=0.1).\
            set_grid(column=1, row=7, columnspan=2)

        ttk.Label(setting_frame, text='Erosion:').grid(column=0, row=8)
        ScaleWidget(self, "erosion_factor", setting_frame, (0, 10),
                    resolution=0.1).\
            set_grid(column=1, row=8, columnspan=2)

        ttk.Label(setting_frame, text='Dilation:').grid(column=0, row=9)
        ScaleWidget(self, "dilation_factor", setting_frame, (0, 10),
                    resolution=0.1).\
            set_grid(column=1, row=9, columnspan=2)

        ttk.Label(setting_frame, text='Isonoise Filtering:').\
            grid(column=0, row=10)
        ScaleWidget(self, "isonoise", setting_frame, (0, 10),
                    resolution=0.1).\
            set_grid(column=1, row=10, columnspan=2)

    def export_current_settings_as_model(self):
        file = fd.asksaveasfile(mode='w', defaultextension=".ini")
        if file is None:
            return
        if os.path.splitext(file.name)[1] == ".ini":
            config = configparser.ConfigParser()
            config["settings"] = {}
            for key in self.values:
                if key not in [""]:
                    config["settings"][key] = str(self.get_value(key))
            config.write(file)
            self.update_list_models()
        file.close()

    def load_image_clipboard(self):
        try:
            stream = subprocess.\
                check_output(["xclip", "-selection", "clipboard",
                              "-t", "image/png", "-o"])
            nparr = np.frombuffer(stream, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if not os.path.exists("processed"):
                os.makedirs("processed")
            cv2.imwrite("processed/original_image.png", img)
        except Exception:
            print("Unable to open clipboard!")
        self.get_canvas().update_image(clipboard=True)

    def get_value(self, valuename):
        return self.values[valuename].get()

    def set_value(self, valuename, new_value):
        self.values[valuename].set(new_value)

    def clipboard_and_processing(self):
        self.load_image_clipboard()
        self.process_image()

    def full_process(self):
        self.load_image_clipboard()
        self.process_image()
        self.apply_tesseract()

    def process_image(self):
        if not self.get_canvas().is_image_loaded():
            print("Load from clipboard image first")
            return

        image = Image.open("processed/original_image.png")

        image = rotate_image(image, self.get_value("rotation_factor"))
        image = resize_image(image, self.get_value("resizing_factor"))

        image = convert_to_gray(image, self.get_value("color_diff_enabled"),
                                self.get_value("color_selection"))
        image = set_inverted(image, self.get_value("invert_image"))
        image = clean_text(image, self.get_value("cleaner_inverted_mod"),
                           self.get_value("clean_filter_factor"))
        image = set_treshold(image, self.get_value("treshold_factor"))

        image = first_filter(image, self.get_value("isonoise"))
        image = clear_image(image, self.get_value("invert_image"),
                            self.get_value("clear_borders"),
                            self.get_value("cleaner_inverted_mod"))
        image = second_filter(image, self.get_value("isonoise"),
                              self.get_value("feathering_factor"),
                              self.get_value("erosion_factor"),
                              self.get_value("dilation_factor"))
        cv2.imwrite("processed/current_image.png", image)

        self.get_canvas().update_image()

    def apply_tesseract(self):
        if not self.get_canvas().is_image_loaded():
            print("Error: No Image found")
            return

        img = Image.open("processed/current_image.png")
        try:
            oem = self.get_value("oem")
            psm = self.get_value("psm")
            lang = self.get_value("lang")
            text = pytesseract.image_to_string(
                    img, lang=lang, config=f"--oem {oem} --psm {psm}")

            text = text.replace(' ', '').replace('、', ',').\
                replace('。', '.').replace('…', '...')
            new_text = ''
            skipNextLine = True

            for line in text.split('\n'):
                if not skipNextLine:
                    new_text += '\n'
                new_text += line
                if len(line) > 0 and line[-1] not in '.?!]』一':
                    skipNextLine = True
                elif len(line) > 0:
                    skipNextLine = False

            if lang[-4:] == "vert":
                lang = lang[:-5]

            print(new_text)
            self.get_extraction_results().set_text(new_text)
            pyperclip.copy(new_text)
        except Exception as e:
            print("Error during tesseract execution:")
            print(str(e))

    def copy_processed_image(self):
        current_image = open("processed/current_image.png")
        subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png"],
                       stdin=current_image)

    def mouse_pressed_on_canvas(self, event):
        x, y = self.get_canvas().get_mouse_coords(event)
        color = self.pick_color(x, y)
        self.update_color_selector(color)

    def pick_color(self, x, y):
        if not self.get_canvas().is_image_loaded():
            return None
        if self.get_canvas().is_viewing_original():
            image = Image.open("processed/original_image.png")
        else:
            image = Image.open("processed/current_imager.png")

        canvas = self.get_canvas()
        canvas_w, canvas_h = canvas.get_dims()
        y = canvas_h - y
        img_w, img_h = image.size
        ratio_w = img_w/canvas_w
        ratio_h = img_h/canvas_h
        if ratio_w > ratio_h:
            if ratio_w >= 1:
                new_x = x*ratio_w
                new_y = img_h - ratio_w*(y - (canvas_h - img_h/ratio_w)/2)
            else:
                new_x = x - (canvas_w - img_w)/2
                new_y = img_h - (y - (canvas_h - img_h)/2)
        else:
            if ratio_h >= 1:
                new_y = img_h - y*ratio_h
                new_x = ratio_h*(x - (canvas_w - img_w/ratio_h)/2)
            else:
                new_y = img_h - (y - (canvas_h - img_h)/2)
                new_x = x - (canvas_w - img_w)/2
        new_x = int(new_x)
        new_y = int(new_y)
        if new_x in range(img_w) and new_y in range(img_h):
            color = image.getpixel((new_x, new_y))
            color = self.rgb2hex(color[0], color[1], color[2])
            return color
        return None

    def update_displayed_color(self, color):
        self.set_value("displayed_color", color)
        self.get_displayed_color().set_bg_color(color)

    def get_color_selector(self):
        return self.window["color_selection"]

    def get_displayed_color(self):
        return self.window["displayed_color"]

    def update_color_selector(self, color):
        if color is None:
            return
        if color in self.colors:
            self.colors.remove(color)
        elif len(self.colors) > 10:
            self.colors.pop()

        self.colors.insert(0, color)
        self.get_color_selector().update_choices(self.colors)
        self.set_value("color_selection", color)
        self.update_displayed_color(color)

    def rgb2hex(self, r, g, b):
        return "#{:02x}{:02x}{:02x}".format(r, g, b)


def main():
    parser = configargparse.\
        ArgParser(description='GUI for processing and extracting text')
    parser.add_argument('-m', '--model-template',
                        type=str, default="default.ini",
                        help='Model templates')
    args = parser.parse_args()
    model = args.model_template

    PrimextractorGUI(default_model=model).loop()


if __name__ == "__main__":
    main()