# See readme at @'https://github.com/rai68/gpsd-easy'
# for installation

#* How to install gpsd with PPS time syncing (requires a non USB GPS that has a PPS pin, but will give you sub microsecond time accuracy (1.000_0##_###s))
#
# to be written
#
#
#
#

#* example config
# | 
# | main.plugins.gpsdeasy.enabled = true
# | main.plugins.gpsdeasy.host = '127.0.0.1'
# | main.plugins.gpsdeasy.port = 2947
# | main.plugins.gpsdeasy.fields = ['fix','lat','lon','alt','speed'] #<-- Any order or amount, you can also use custom values from POLL.TPV; on gpsd documents (https://gpsd.gitlab.io/gpsd/gpsd_json.html#_tpv)
# | main.plugins.gpsdeasy.speedUnit = 'kph' or 'mph'
# | main.plugins.gpsdeasy.distanceUnit = 'm' or 'ft'
# | main.plugins.gpsdeasy.bettercap = true #<--- report to bettercap

import time
import json
import logging

import socket

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue

import pwnagotchi

class GPSD:
    def __init__(self, gpsdhost, gpsdport):
        self.socket = None
        self.stream = None
        self.connect(host=gpsdhost, port=gpsdport)
        self.running = True
        self.spacing = 0


    def connect(self, host="127.0.0.1", port=2947):
        """ Connect to a GPSD instance
        :param host: hostname for the GPSD server
        :param port: port for the GPSD server
        """
        
        logging.info("[gpsdeasy] Connecting to gpsd socket at {}:{}".format(host, port))
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.stream = self.socket.makefile(mode="rw")
        except:
            logging.warning("[gpseasy] error occured during socket setup, try power cycle the device")

        self.stream.write('?WATCH={"enable":true}\n')
        self.stream.flush()


        welcome_raw = self.stream.readline()
        welcome = json.loads(welcome_raw)
        if welcome['class'] != "VERSION":
            raise Exception(
                "Unexpected data received as welcome. Is the server a gpsd 3 server?")
        logging.info("[gpsdeasy] connected")


    def get_current(self):
        """ Poll gpsd for a new position
        :return: GpsResponse
        """
        if self.running != True:
            return
        
        self.stream.write("?POLL;\n")
        self.stream.flush()
        raw = self.stream.readline()
        response = json.loads(raw)
        if response['class'] != 'POLL':
            if response['class'] == "DEVICES":
                logging.info("Got DEVICES: %s" % repr(response))
            else:
                raise Exception(
                    "Unexpected message received from gps: {} : If = DEVICES, you can safely ignore and continue".format(response['class']))
            return {}
        else:
            return response['tpv'][0]


class gpsdeasy(plugins.Plugin):
    __author__ = "discord@rai68"
    __version__ = "1.1.2"
    __license__ = "LGPL"
    __description__ = "uses gpsd to report lat/long on the screen and setup bettercap pcap gps logging"

    def __init__(self):
        self.gpsd = None
        self.fields = ['fix','lat','lon','alt','spd']
        self.speedUnit = 'ms'
        self.distanceUnit = 'm'
        self.element_pos_x = 130
        self.element_pos_y = 47
        self.host = '127.0.0.1'
        self.port = 2947
        self.spacing = 12
        self.agent = None
        self.bettercap = True
        self.loaded = False

    def on_loaded(self):
        
        if 'host' in self.options:
            self.host = self.options['host']
            
        if 'port' in self.options:
            self.port = self.options['port']
        
        self.gpsd = GPSD(self.host, self.port)
        
        if 'bettercap' in self.options:
            self.bettercap = self.options['bettercap']
        
        if 'fields' in self.options:
            self.fields = self.options['fields']
            
        if 'speedUnit' in self.options:
            self.speedUnit = self.options['speedUnit']
        
        if 'distanceUnit' in self.options:
            self.distanceUnit = self.options['distanceUnit']

        if 'topleft_x' in self.options:
            self.distanceUnit = self.options['topleft_x']
            
        if 'topleft_y' in self.options:
            self.distanceUnit = self.options['topleft_y']
        
        global BLACK
        if 'invert' in pwnagotchi.config['ui'] and pwnagotchi.config['ui']['invert'] == 1:
            BLACK = 0xFF
        else: 
            BLACK = 0x00
        self.loaded = True
        logging.info("[gpsdeasy] plugin loaded")

    def on_ready(self, agent):
        self.agent = agent
        if self.bettercap:
            logging.info(f"[gpsdeasy] enabling bettercap's gps module for {self.options['host']}:{self.options['port']}")
            try:
                agent.run("gps off")
            except Exception:
                logging.info(f"[gpsdeasy] bettercap gps was already off")
                pass

            agent.run(f"set gps.device {self.options['host']}:{self.options['port']}; set gps.baudrate 9600; gps on")
            logging.info("[gpsdeasy] bettercap set and on")
            self.running = True
        else:
            logging.warning("[gpsdeasy] bettercap gps reporting disabled")

    def on_handshake(self, agent, filename, access_point, client_station):
        coords = self.gpsd.get_current()
        if coords and all([
            # avoid 0.000... measurements
            coords["lat"], coords["lon"]
        ]):
            gps_filename = filename.replace(".pcap", ".gps.json")
            logging.info(f"[gpsdeasy] saving GPS to {gps_filename} ({coords})")
            with open(gps_filename, "w+t") as fp:
                json.dump(coords, fp)
        else:
            logging.info("[gpsdeasy] not saving GPS: no fix")

    def on_ui_setup(self, ui):
        # add coordinates for other displays
        while self.loaded == False:
            logging.info(self.loaded)
            time.sleep(0.1)
        label_spacing = 0

        for i,item in enumerate(self.fields):
            element_pos_x = self.element_pos_x
            element_pos_y = self.element_pos_y + (self.spacing * i)
            if len(item) == 4:
                element_pos_x = element_pos_x - 5
                
            
            pos = (element_pos_x,element_pos_y)
            ui.add_element(
                item,
                LabeledValue(
                    color=BLACK,
                    label=f"{item}:",
                    value="-",
                    position=pos,
                    label_font=fonts.Small,
                    text_font=fonts.Small,
                    label_spacing=label_spacing,
                ),
            )


    def on_unload(self, ui):
        logging.info("[gpsdeasy] bettercap gps reporting disabled")
        try:
            agent.run("gps off")
        except Exception:
            logging.info(f"[gpsdeasy] bettercap gps was already off")

        
        
        with ui._lock:
            for element in self.fields:
                ui.remove_element(element)
                
        logging.info("[gpsdeasy] plugin disabled")


    def on_ui_update(self, ui):
        coords = self.gpsd.get_current()
        
        for item in self.fields:
            #create depending on fields option
            
            if item == 'fix':
                try:
                    if coords['mode'] == 0:
                        ui.set("fix", f"-")
                    elif coords['mode'] == 1:
                        ui.set("fix", f"0D")
                    elif coords['mode'] == 2:
                        ui.set("fix", f"2D")
                    elif coords['mode'] == 3:
                        ui.set("fix", f"3D")
                    else:
                        ui.set("fix", f"err")
                except: ui.set("fix", f"err")
            
            
            elif item == 'lat':
                try:
                    if coords['mode'] == 0:
                        ui.set("lat", f"{0:.4f} ")
                    elif coords['mode'] == 1:
                        ui.set("lat", f"{0:.4f} ")
                    elif coords['mode'] == 2:
                        ui.set("lat", f"{coords['lat']:.4f} ")
                    elif coords['mode'] == 3:
                        ui.set("lat", f"{coords['lat']:.4f} ")
                    else:
                        ui.set("lat", f"err")
                except: ui.set("lat", f"err")

            elif item == 'lon':
                try:
                    if coords['mode'] == 0:
                        ui.set("lon", f"{0:.4f} ")
                    elif coords['mode'] == 1:
                        ui.set("lon", f"{0:.4f} ")
                    elif coords['mode'] == 2:
                        ui.set("lon", f"{coords['lon']:.4f} ")
                    elif coords['mode'] == 3:
                        ui.set("lon", f"{coords['lon']:.4f} ")
                    else:
                        ui.set("lon", f"err")
                except: ui.set("lon", f"err")

            elif item == 'alt':
                try: 
                    if 'speed' in coords:
                        if self.distanceUnit == 'ft':
                            coords['altMSL'] == coords['altMSL'] * 3.281

                        
                        if coords['mode'] == 0:
                            ui.set("alt", f"{0:.1f}{self.distanceUnit}")
                        elif coords['mode'] == 1:
                            ui.set("alt", f"{0:.1f}{self.distanceUnit}")
                        elif coords['mode'] == 2:
                            ui.set("alt", f"{0:.2f}{self.distanceUnit}")
                        elif coords['mode'] == 3:
                            ui.set("alt", f"{coords['altMSL']:.1f}{self.distanceUnit}")
                        else:
                            ui.set("alt", f"err")
                    else:
                        ui.set("alt", f"{0:.1f}{self.distanceUnit}")
                except: ui.set("alt", f"err")
        
            elif item == 'spd':
                
                try:
                    if 'speed' in coords:
                        if self.speedUnit == 'kph':
                            coords['speed'] == coords['speed'] * 3.6
                        elif self.speedUnit == 'mph':
                            coords['speed'] == coords['speed'] * 2.237
                        else: coords['speed']
                        
                    else:
                        coords['speed'] = 0
                    
                    if self.speedUnit == 'kph':
                        displayUnit = 'km/h'
                    elif self.speedUnit == 'mph':
                        displayUnit = 'mi/h'
                    elif self.speedUnit == 'ms':
                        displayUnit = 'm/s'
                    else: coords['mode'] = -1 #err mode
                    
                    
                    if coords['mode'] == 0:
                        ui.set("spd", f"{0:.2f}{displayUnit}")
                    elif coords['mode'] == 1:
                        ui.set("spd", f"{0:.2f}{displayUnit}")
                    elif coords['mode'] == 2:
                        ui.set("spd", f"{coords['speed']:.2f}{displayUnit}")
                    elif coords['mode'] == 3:
                        ui.set("spd", f"{coords['speed']:.2f}{displayUnit}")
                    else:
                        ui.set("spd", f"err")

                except:
                    ui.set("spd", f"err")
                    
            else:
                if item:
                #custom item add unit after f}
                    try:
                        if coords[item] == 0:
                            ui.set(item, f"{0:.1f}")
                        elif coords[item] == 1:
                            ui.set(item, f"{coords[item]:.2f}")
                        elif coords[item] == 2:
                            ui.set(item, f"{coords[item]:.2f}")
                        elif coords[item] == 3:
                            ui.set(item, f"{coords[item]:.2f}")
                        else:
                            ui.set(item, f"err")
                    except: ui.set(item, f"err")
                        
                        
#version 1.1.2
