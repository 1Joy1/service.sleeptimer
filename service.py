# -*- coding: utf-8 -*-

""" Service Sleep Timer  (c)  2015 enen92, Solo0815

# This program is free software; you can redistribute it and/or modify it under the terms
# of the GNU General Public License as published by the Free Software Foundation;
# either version 2 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program;
# if not, see <http://www.gnu.org/licenses/>.


"""

import time
import datetime
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import os


__addonid__ = 'service.sleeptimer'
__addon__ = xbmcaddon.Addon( __addonid__ )
__version__ = __addon__.getAddonInfo( 'version' )




# Functions:

def _log( message ):
    xbmc.log( "[" + __addonid__ + "] : " + message, level=xbmc.LOGNOTICE )

def translate(text):
    return __addon__.getLocalizedString(text).encode('utf-8')

def str_to_bool( string ):
    if string.lower() == "true" or string == "1":
        return True
    elif string.lower() == "false" or string == "0":
        return False
    else:
        raise ValueError("The argument must be a string, value must be one of: «true», «false», «1», «0»")




class ServiceMonitor(xbmc.Monitor):
    def __init__( self, *args, **kwargs ):
        xbmc.Monitor.__init__(self)
        self.action = kwargs['action']

    def onSettingsChanged( self ):
        self.action()





class Service:
    def __init__( self ):
        _log( "Service initialized ... (" + str(__version__) + ")" )
        # addon settings change
        self.monitor = ServiceMonitor(action = self.initSettings)
        self.initSettings()
        self.startService()


    def startService( self ):
        _log ( " ... started ... " )
        canceled_by_user = False
        check_time = 0.25

        while not self.monitor.abortRequested():

            self.debugging( "Do next check after " + ((str(int(check_time*60)) + " sec") if check_time < 1 else (str(check_time) + " min")) )

            self.monitor.waitForAbort(int(check_time * 60))
            check_time = self.check_time

            if not xbmc.Player().isPlaying() or not self.superviseTime():
                self.debugging( "Player not playing or not supervise time." )
                canceled_by_user = False
                continue

            max_time_in_minutes = self.getMaxTimeInMinutes( canceled_by_user )

            if max_time_in_minutes is None:
                self.debugging( "Value max_time_in_minutes is " + str(max_time_in_minutes) )
                canceled_by_user = False
                continue

            idle_time = xbmc.getGlobalIdleTime()
            idle_time_in_minutes = int(idle_time) / 60
            self.debugging( "Value max_time_in_minutes = " + str(max_time_in_minutes) )
            self.debugging( "idle_time: '" + str(idle_time) + " sec'; idle_time_in_minutes: '" + str(idle_time_in_minutes) + " min'" )

            if idle_time_in_minutes < max_time_in_minutes:
                self.debugging( "Time does not exceed max limit.")
                continue

            if not self.tryStopPlaying():
                self.debugging( "The user canceled the sleep process, next sleep process after " + str(self.max_min_after_canceled) + " min" )
                canceled_by_user = True

        self.stopService()



    def stopService( self ):
        _log( "Service terminated" )



    def getMaxTimeInMinutes( self, canceled_by_user ):
        max_time_in_minutes = None

        if xbmc.Player().isPlayingAudio() and self.enable_audio:
            if self.debug_mode:
                self.debugging( "Detect playing audio and monitoring audio enabled" )
                self.debugging( "File: " + str(xbmc.Player().getPlayingFile()) )
                self.debugging( "Max audio time = " + str(self.maxaudio_time_in_minutes) + "min" )
            max_time_in_minutes = self.maxaudio_time_in_minutes if not canceled_by_user else self.max_min_after_canceled
        elif xbmc.Player().isPlayingVideo() and self.enable_video:
            if self.debug_mode:
                self.debugging( "Detect playing video and monitoring video enabled" )
                self.debugging( "File: " + str(xbmc.Player().getPlayingFile()) )
                self.debugging( "Max video time = " + str(self.maxvideo_time_in_minutes) + "min" )
            max_time_in_minutes = self.maxvideo_time_in_minutes if not canceled_by_user else self.max_min_after_canceled
        else:
            if self.debug_mode:
                self.debugging( "Playing is not Audio or Video, or not monitoring enabled" )

        return max_time_in_minutes



    def tryStopPlaying( self ):
        if self.msgDialogIsCanceled():
            return False

        if self.audio_change:
            current_volume = self.getCurrentVolume()
            if not self.softVolumeDown(current_volume):
                return False

        self.playerStop()

        if self.audio_change:
            self.restoreVolume(current_volume)

        if self.enable_screensaver:
            self.activateScreensaver()

        if self.custom_cmd:
            self.runCustomCMD()

        return True



    def initSettings( self ):
        _log ( "Load Settings ..." )

        self.debug_mode = str_to_bool( __addon__.getSetting('debug_mode') )
        self.enable_audio = str_to_bool( __addon__.getSetting('audio_enable') )
        self.enable_video = str_to_bool( __addon__.getSetting('video_enable') )
        self.enable_screensaver = str_to_bool( __addon__.getSetting('enable_screensaver') )
        self.custom_cmd = str_to_bool( __addon__.getSetting('custom_cmd') )
        self.audio_change = str_to_bool( __addon__.getSetting('audio_change') )
        self.supervision_mode = str_to_bool( __addon__.getSetting('supervision_mode') )
        self.maxaudio_time_in_minutes = int( __addon__.getSetting('max_time_audio') )
        self.maxvideo_time_in_minutes = int( __addon__.getSetting('max_time_video') )
        self.check_time = int( __addon__.getSetting('check_time') )
        self.max_min_after_canceled = int( __addon__.getSetting('check_time_next') )
        self.waiting_time_dialog = int( __addon__.getSetting('waiting_time_dialog') )
        self.audio_change_rate = int( __addon__.getSetting('audio_change_rate') )
        self.supervise_start_time = int( __addon__.getSetting('hour_start_sup').replace(":", "") )
        self.supervise_end_time = int( __addon__.getSetting('hour_end_sup').replace(":", "") )
        self.cmd = __addon__.getSetting('cmd')

        # If debugging mode, set low values for easier!
        if self.debug_mode:
            self.debugging( "#######################Settings in Kodi##########################" )
            self.debugging( "debug_mode: " + str(self.debug_mode) )
            self.debugging( "enable_audio: " + str(self.enable_audio) )
            self.debugging( "enable_video: " + str(self.enable_video) )
            self.debugging( "enable_screensaver: " + str(self.enable_screensaver) )
            self.debugging( "custom_cmd: " + str(self.custom_cmd) )
            self.debugging( "audio_change: " + str(self.audio_change) )
            self.debugging( "maxaudio_time_in_minutes: " + str(self.maxaudio_time_in_minutes) )
            self.debugging( "maxvideo_time_in_minutes: " + str(self.maxvideo_time_in_minutes) )
            self.debugging( "max_min_after_canceled: " + str(self.max_min_after_canceled) )
            self.debugging( "check_time: " + str(self.check_time) )
            self.debugging( "waiting_time_dialog: " + str(self.waiting_time_dialog) )
            self.debugging( "audio_change_rate: " + str(self.audio_change_rate) )
            self.debugging( "Supervision mode: " + str(self.supervision_mode) )
            self.debugging( "supervise_start_time: " + str(self.supervise_start_time) )
            self.debugging( "supervise_end_time: " + str(self.supervise_end_time) )
            self.debugging( "################################################################" )

            self.enable_audio = True
            self.enable_video = True
            self.maxaudio_time_in_minutes = 3
            self.maxvideo_time_in_minutes = 3
            self.check_time = 1
            self.max_min_after_canceled = 5
            self.waiting_time_dialog = 30
            self.supervision_mode = False

            self.debugging( "--------------Debug is enabled! Override Settings:--------------" )
            self.debugging( "-> enable_audio: " + str(self.enable_audio) )
            self.debugging( "-> maxaudio_time_in_minutes: " + str(self.maxaudio_time_in_minutes) )
            self.debugging( "-> enable_video: " + str(self.enable_audio) )
            self.debugging( "-> maxvideo_time_in_minutes: " + str(self.maxvideo_time_in_minutes) )
            self.debugging( "-> check_time: " + str(self.check_time) )
            self.debugging( "-> max_min_after_canceled: " + str(self.max_min_after_canceled) )
            self.debugging( "-> waiting_time_dialog: " + str(self.waiting_time_dialog) )
            self.debugging( "Supervision mode: " + str(self.supervision_mode) )
            self.debugging( "----------------------------------------------------------------" )


    def superviseTime( self ):
        if self.supervision_mode:

            kodi_time = int(time.strftime("%H%M"))

            if self.supervise_start_time > self.supervise_end_time:
                if kodi_time < self.supervise_start_time and kodi_time > self.supervise_end_time:
                    return False

            if self.supervise_start_time < self.supervise_end_time:
                if kodi_time < self.supervise_start_time or kodi_time > self.supervise_end_time:
                    return False

        return True


    def msgDialogIsCanceled( self ):
        self.debugging( "Display Progress dialog" )

        dialog_progress = xbmcgui.DialogProgress()
        dialog_progress.create(translate(30000), translate(30001))
        secs=0

        # use the multiplier 100 to get better %/calculation
        increment = 100*100 / self.waiting_time_dialog

        while secs < self.waiting_time_dialog:
            secs = secs + 1
            # divide with 100, to get the right value
            percent = increment * secs / 100
            secs_left = str((self.waiting_time_dialog - secs))
            dialog_progress.update(percent, translate(30001), secs_left + " seconds left.")
            xbmc.sleep(1000)

            if (dialog_progress.iscanceled()):
                self.debugging( "Progress dialog is cancelled. Not stopping Player" )
                dialog_progress.close()
                return True

        self.debugging( "Progressdialog not cancelled. Stopping Player" )
        dialog_progress.close()
        return False



    def getCurrentVolume( self ):
        resp = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": { "properties": [ "volume"] }, "id": 1}')
        dct = json.loads(resp)
        if (dct.has_key("result")) and (dct["result"].has_key("volume")):
            return dct["result"]["volume"]
        else:
            return 50



    def softVolumeDown( self, current_volume ):
        self.debugging( "Wait 2s before changing volume down" )
        xbmc.sleep(2000) # wait 2s before changing the volume back
        mute_volume = 10
        for i in range(current_volume - 1, mute_volume - 1, -1):
            xbmc.executebuiltin('SetVolume(%d,showVolumeBar)' % (i))
            # move down slowly
            xbmc.sleep(self.audio_change_rate)
            # Canceled if any key down
            if self.checkPressAnyKey():
                return False
        return True



    def playerStop( self ):
        self.debugging( "Wait 5s before stopping" )
        xbmc.sleep(5000) # wait 5s before stopping
        self.debugging( "Stop player" )
        xbmc.executebuiltin('PlayerControl(Stop)')



    def activateScreensaver( self ):
        self.debugging( "Activating screensaver" )
        xbmc.executebuiltin('ActivateScreensaver')



    def runCustomCMD( self ):
        self.debugging( "Running custom script" )
        os.system(self.cmd)



    def restoreVolume( self, volume ):
        xbmc.sleep(2000) # wait 2s before changing the volume back
        # we can move upwards fast, because there is nothing playing
        xbmc.executebuiltin('SetVolume(%d,showVolumeBar)' % (volume))



    def checkPressAnyKey( self ):
        if xbmc.getGlobalIdleTime() < 1:
            return True
        return False



    def debugging( self, message ):
        if self.debug_mode:
            _log ( "DEBUG: " + message )


Service()
