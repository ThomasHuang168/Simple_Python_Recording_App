#!/usr/bin/python

'''
Author: TAO Dehua, Feng Huang, Huang Hing Pang
Last edited:
 2021/06/24, Huang Hing Pang
 2019/06/21, TAO Dehua
'''
# import platform
# os_sys = platform.system()
# if 'Windows' == os_sys:
#     from PyQt5 import sip
# else:
#     import sip
# # solve 'QString' object has no attribute 'write'
# # import sip
# sip.setapi('QString', 2)
# # or unicode(string)
from yaml import load, dump, loader
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import pyaudio
import wave
import time
import sys
import os
# import Queue
import threading

import numpy as np

# from PyQt4 import QtGui, QtCore
from PyQt5 import QtWidgets, QtGui, QtCore
import threading
import queue as Queue
import pyqtgraph
from pyqtgraph import PlotWidget

import codecs
try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

import os

# Recoder GUI interface based on pyqt (qt4)
class Recoder(QtWidgets.QWidget):
    def __init__(self):
        super(Recoder, self).__init__()
        self.isPlaying = False

        self.config = dict()
        with open("demo_setting.yaml", 'r', encoding='utf-8') as fr:
            self.config = load("".join(fr.readlines()), Loader=Loader)
        with open("current_setting.yaml", 'r', encoding='utf-8') as fr:
            self.config.update(load("".join(fr.readlines()), Loader=Loader))
    
        self.checkDevices()


        self.initGUI()

        self.data_db = None
        self.data_db_x = None
        self.rootPath = ""

        self.p = pyaudio.PyAudio()
        self.rec_samples = []
        self.rec_stream = None
        self.recIndex = 0

        self.player = pyaudio.PyAudio()
        self.player_wf = None
        self.player_stream = None


        REC_DISPLAY_BUFFER = self.config["REC_DISPLAY_BUFFER"]
        REC_DISPLAY_INIT_VAL = self.config["REC_DISPLAY_INIT_VAL"]
        REC_RATE = self.config["REC_RATE"]
        REC_CHUNK = self.config["REC_CHUNK"]
        self.data_db_x = np.arange(REC_DISPLAY_BUFFER)*REC_CHUNK/float(REC_RATE)
        self.data_db = float(REC_DISPLAY_INIT_VAL)*np.ones(REC_DISPLAY_BUFFER)

    # initialize the in/out devices
    def initDevice(self):
        REC_IN_CARD = self.config["REC_IN_CARD"]
        REC_OUT_CARD = self.config["REC_OUT_CARD"]

        count = self.p.get_device_count()
        self.inCardIndex = -1
        self.outCardIndex = -1
        for i in range(count):
            dev = self.p.get_device_info_by_index(i)
            if REC_IN_CARD in dev['name']:
                # dev['name']="Scarlett 2i2 USB: Audio (hw:2,0)"
                self.inCardIndex = i
                print( "inCardIndex: " + str(i) + ' ' + dev['name'])
            if dev['name'] == REC_OUT_CARD:
                self.outCardIndex = i
                print( "outCardIndex: " + str(i) + ' ' + dev['name'])

    def updateGUI(self, in_data):
        data = np.frombuffer(in_data, dtype=np.int16)
        if not data.shape[0] == 0:
            data_ = np.max(np.abs(data))
            self.data_db = np.roll(self.data_db, -1)
            self.data_db[-1] = 20*np.log10(data_/2**15)

    def rec_callback(self, in_data, frame_count, time_info, status):
        self.rec_samples.append(in_data)
        self.updateGUI(in_data)
        return (in_data, pyaudio.paContinue)

    def startRecording(self):
        self.saveScript()
        REC_CHANNELS = self.config["REC_CHANNELS"]
        REC_RATE = self.config["REC_RATE"]
        REC_CHUNK = self.config["REC_CHUNK"]
        REC_FORMAT = eval(self.config["REC_FORMAT"])

        # it can be put in __init__, but more safe to put here
        # in case that usb soundcard gets re-plugged during the recording
        self.initDevice()
        self.rec_samples = []
        self.rec_stream = self.p.open(format = REC_FORMAT,
                                 channels = REC_CHANNELS,
                                 rate = REC_RATE,
                                 input = True,
                                 input_device_index = self.inCardIndex,
                                 frames_per_buffer = REC_CHUNK,
                                 stream_callback = self.rec_callback)
        print( "Start recording")
        self.rec_stream.start_stream()

        self.btnRecord.setEnabled(False)
        self.btnStopRecord.setEnabled(True)
        self.textRootPath.setEnabled(False)
        self.comboRecScript.setEnabled(False)
        self.comboRecWave.setEnabled(False)


    def stopRecording(self):
        self.rec_stream.stop_stream()
        while self.rec_stream.is_active():
            time.sleep(0.1)
        self.rec_stream.close()
        print( "Pause recording")

        self.recIndex += 1
        self.saveWave()
        print( "Recording saved")

        self.comboRecWave.addItem(self.newWavName)

        ScriptName = self.comboRecScript.currentText()
        scriptPath = os.path.join(self.textRootPath.text(), ScriptName)
        newWavName = "{}_{}.wav".format(ScriptName, self.recIndex)
        while os.path.exists(os.path.join(scriptPath, newWavName)):
            self.recIndex += 1
            newWavName = "{}_{}.wav".format(ScriptName, self.recIndex)
        self.newWavName = newWavName
        print("New Record File will be \"{}\".".format(newWavName))

        self.btnRecord.setEnabled(True)
        self.btnStopRecord.setEnabled(False)
        self.textRootPath.setEnabled(True)
        self.comboRecScript.setEnabled(True)
        self.comboRecWave.setEnabled(True)


    def player_callback(self, in_data, frame_count, time_info, status):
        data = self.player_wf.readframes(frame_count)
        self.updateGUI(data)
        if self.isPlaying:
            return (data, pyaudio.paContinue)
        else:
            return (data, pyaudio.paComplete)

    def playRecording(self):
        wavePath = os.path.join(self.textRootPath.text(), self.comboRecScript.currentText(), self.comboRecWave.currentText())
        self.isPlaying = True

        self.initDevice()
        self.player_wf = wave.open(wavePath, 'rb')
        # numFrames = self.player_wf.getnframes()
        # data_wf = self.player_wf.readframes(numFrames)
        self.player_stream = self.player.open(format=self.player.get_format_from_width(self.player_wf.getsampwidth()),
                                    channels=self.player_wf.getnchannels(),
                                    rate=self.player_wf.getframerate(),
                                    output=True,
                                    output_device_index=self.outCardIndex,
                                    stream_callback=self.player_callback)
        self.player_stream.start_stream()

        endPlayThread = threading.Thread(target=EndPlayRecThread, args=(self,))
        endPlayThread.start()

        self.btnPlay.setEnabled(False)
        self.btnStopPlay.setEnabled(True)
        self.textRootPath.setEnabled(False)
        self.comboRecScript.setEnabled(False)
        self.comboRecWave.setEnabled(False)

    def endPlayingRecording(self):
        while self.player_stream.is_active():
            time.sleep(0.1)
        self.player_stream.close()
        self.player_wf.close()

        self.isPlaying = False
        self.btnPlay.setEnabled(True)
        self.btnStopPlay.setEnabled(False)
        self.textRootPath.setEnabled(True)
        self.comboRecScript.setEnabled(True)
        self.comboRecWave.setEnabled(True)

    def stopPlayingRecording(self):
        self.isPlaying = False

    def saveWave(self):
        REC_CHANNELS = self.config["REC_CHANNELS"]
        REC_RATE = self.config["REC_RATE"]
        REC_FORMAT = eval(self.config["REC_FORMAT"])

        waveFilePath = os.path.join(self.textRootPath.text(), self.comboRecScript.currentText(), self.newWavName)
        waveFile = wave.open(waveFilePath, 'wb')
        waveFile.setnchannels(REC_CHANNELS)
        waveFile.setsampwidth(self.p.get_sample_size(REC_FORMAT))
        waveFile.setframerate(REC_RATE)
        waveFile.writeframes(b''.join(self.rec_samples))
        waveFile.close()

    def close(self):
        self.p.terminate()
        self.player.terminate()

    ##GUI##
    def initGUI(self):
        BTN_FONT_STYLE = self.config["BTN_FONT_STYLE"]
        BTN_FONT_SIZE = self.config["BTN_FONT_SIZE"]
        BTN_W = self.config["BTN_W"]
        BTN_H = self.config["BTN_H"]
        X_BTN = self.config["X_BTN"]
        Y_BTN = self.config["Y_BTN"]

        screenNo = QtWidgets.QApplication.desktop().screenNumber(QtWidgets.QApplication.desktop().cursor().pos())
        screen = QtWidgets.QApplication.desktop().screenGeometry(screenNo)

        GUI_scale = screen.width() / 1920

        BTN_FONT_SIZE = int(BTN_FONT_SIZE * GUI_scale)
        BTN_W = int(BTN_W * GUI_scale)
        BTN_H = int(BTN_H * GUI_scale)
        X_BTN = int(X_BTN * GUI_scale)
        Y_BTN = int(Y_BTN * GUI_scale)

        # first LineEdit widget is used to define the path to store the recording files
        # second when path is not empty, the programme will scan txt files in the directory
        # and list them (only the name before ".txt") out in the second combo box
        # when a name of script is selected, the program look the directory with the same name first to display existing project. If that directory is not found, the program create the directory with the name of file, copy the script file into that path and display the copied file
        # wave file combo box is empty at the begining. If any wavefile exists in the directory, the combo should list them out
        # if the empty combo box is selected, the program is in record mode. The new file name will be in format of "{script}-{#index}.wav". Once any file is selected in the combo box, the program is in play mode. 
        # The function of fifth button is activated after script name is selected. The default function is recording. 

        h0box = QtWidgets.QHBoxLayout()

        # self.textRead = QtWidgets.QPlainTextEdit()
        self.textRead = QtWidgets.QTextEdit()
        h0box.addWidget(self.textRead)

        self.grDB = PlotWidget()
        self.grDB.setObjectName(_fromUtf8("grDB"))
        h0box.addWidget(self.grDB)


        grid0 = QtWidgets.QGridLayout()

        flo0 = QtWidgets.QFormLayout()

        self.textRootPath = QtWidgets.QLineEdit()
        self.textRootPath.setAlignment(QtCore.Qt.AlignCenter)
        self.textRootPath.setFont(QtGui.QFont(BTN_FONT_STYLE, BTN_FONT_SIZE))
        self.textRootPath.setText(self.config['PATH'])
        self.textRootPath.setMinimumWidth(3*BTN_W)
        self.textRootPath.setFixedHeight(BTN_H)
        self.textRootPath.textEdited.connect(self.pathEdited)
        self.textRootPath.editingFinished.connect(self.pathEditFinished)
        flo0.addRow("Path: ",self.textRootPath)

        self.comboRecScript = QtWidgets.QComboBox(self)
        self.comboRecScript.setFont(QtGui.QFont(BTN_FONT_STYLE, BTN_FONT_SIZE))
        # self.comboRecScript.addItem("Select script")
        self.comboRecScript.setMinimumWidth(3*BTN_W)
        self.comboRecScript.setFixedHeight(BTN_H)
        self.comboRecScript.activated.connect(self.scriptSelected)
        flo0.addRow("Script: ", self.comboRecScript)

        self.comboRecWave = QtWidgets.QComboBox(self)
        self.comboRecWave.setFont(QtGui.QFont(BTN_FONT_STYLE, BTN_FONT_SIZE))
        # self.comboRecWave.addItem("Select Record")
        self.comboRecWave.setMinimumWidth(3*BTN_W)
        self.comboRecWave.setFixedHeight(BTN_H)
        self.comboRecWave.activated.connect(self.waveChanged)
        flo0.addRow("Record: ", self.comboRecWave)
        grid0.addLayout(flo0, 0, 0, 3, 1)
        grid0.setColumnStretch(0, 1)
        grid0.setColumnMinimumWidth(0, 2*BTN_W)

        self.btnRecord = QtWidgets.QPushButton("Record")
        self.btnRecord.setEnabled(False)
        self.btnRecord.setFixedSize(BTN_W, BTN_H)
        self.btnRecord.clicked.connect(self.startRecording)
        grid0.addWidget(self.btnRecord, 0, 1)

        self.btnStopRecord = QtWidgets.QPushButton("Stop Recording")
        self.btnStopRecord.setEnabled(False)
        self.btnStopRecord.setFixedSize(BTN_W, BTN_H)
        self.btnStopRecord.clicked.connect(self.stopRecording)
        grid0.addWidget(self.btnStopRecord, 0, 2)

        self.btnPlay = QtWidgets.QPushButton("Play")
        self.btnPlay.setEnabled(False)
        self.btnPlay.setFixedSize(BTN_W, BTN_H)
        self.btnPlay.clicked.connect(self.playRecording)
        grid0.addWidget(self.btnPlay, 1, 1)

        self.btnStopPlay = QtWidgets.QPushButton("Stop Playing")
        self.btnStopPlay.setEnabled(False)
        self.btnStopPlay.setFixedSize(BTN_W, BTN_H)
        self.btnStopPlay.clicked.connect(self.stopPlayingRecording)
        grid0.addWidget(self.btnStopPlay, 1, 2)

        self.btnSaveText = QtWidgets.QPushButton("Save Script")
        self.btnSaveText.setEnabled(True)
        self.btnSaveText.setFixedSize(BTN_W, BTN_H)
        self.btnSaveText.clicked.connect(self.saveScript)
        grid0.addWidget(self.btnSaveText, 2, 1)

        flo1 = QtWidgets.QFormLayout()
        self.textFontSize = QtWidgets.QLineEdit("10")
        self.textFontSize.setEnabled(True)
        self.textFontSize.editingFinished.connect(self.setFontSize)
        flo1.addRow("Font Size: ", self.textFontSize)
        # flo1.setFixedSize(BTN_W, BTN_H)
        grid0.addLayout(flo1, 2, 2)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(h0box)
        vbox.addLayout(grid0)

        self.setLayout(vbox)
        self.setGeometry(300, 300, 300, 150)
        self.setWindowTitle('Simple Python Recorder GUI')

        self.show()

    def update(self):
        if not self.data_db is None and not self.data_db_x is None:
            pen = pyqtgraph.mkPen(color='r')
            self.grDB.plot(self.data_db_x, self.data_db, pen=pen, clear=True)
        QtCore.QTimer.singleShot(500, self.update)

    def pathEdited(self, text):
        self.textRootPath.setText(text)

    def pathEditFinished(self):
        if not self.rootPath == self.textRootPath.text():
            self.rootPath = self.textRootPath.text()
            if os.path.exists(self.textRootPath.text()):
                self.comboRecScript.clear()
                listTXT = os.listdir(self.textRootPath.text())
                listRecScript = []
                for txtFilename in listTXT:
                    if txtFilename[-4:] == ".txt":
                        listRecScript.append(txtFilename[0:-4])
                self.comboRecScript.addItems(listRecScript)

    def scriptSelected(self, index):
        if not index == -1:
            ScriptName = self.comboRecScript.currentText()
            scriptPath = os.path.join(self.textRootPath.text(), ScriptName)
            if not os.path.exists(scriptPath):
                os.mkdir(scriptPath)

            scriptFile = os.path.join(scriptPath, ScriptName + ".txt")
            if not os.path.exists(scriptFile):
                from shutil import copyfile
                src_file = os.path.join(self.textRootPath.text(), ScriptName + ".txt")
                copyfile(src_file, scriptFile)

            # with codecs.open(scriptFile, 'r', encoding='big5hkscs') as f:

            with codecs.open(scriptFile, 'r', encoding='utf8') as f:
                text_2_read = f.read()
            self.textRead.setPlainText(text_2_read)

            self.comboRecWave.clear()
            self.recIndex = 0
            listRecWave = [""]
            for wavFile in os.listdir(scriptPath):
                if ".wav" == wavFile[-4:]:
                    listRecWave.append(wavFile)
            self.comboRecWave.addItems(listRecWave)

            newWavName = "{}_{}.wav".format(ScriptName, self.recIndex)
            while os.path.exists(os.path.join(scriptPath, newWavName)):
                self.recIndex = self.recIndex + 1
                newWavName = "{}_{}.wav".format(ScriptName, self.recIndex)
            self.newWavName = newWavName
            print("New Record File will be \"{}\".".format(newWavName))

            self.btnRecord.setEnabled(True)

    def waveChanged(self, index):
        if not index == -1:
            if self.comboRecWave.currentText() == "":
                # recording mode
                self.btnPlay.setEnabled(False)
                self.btnStopPlay.setEnabled(False)
                self.btnRecord.setEnabled(True)
                self.btnStopRecord.setEnabled(False)
            else:
                # playback mode
                self.btnPlay.setEnabled(True)
                self.btnStopPlay.setEnabled(False)
                self.btnRecord.setEnabled(False)
                self.btnStopRecord.setEnabled(False)

    def saveScript(self):
        scriptFile = os.path.join(self.textRootPath.text(), self.comboRecScript.currentText(), self.comboRecScript.currentText()+".txt")
        # with codecs.open(scriptFile, "w", encoding='big5hkscs') as f:
        with codecs.open(scriptFile, "w", encoding='utf8') as f:
            f.write(self.textRead.toPlainText())
        print("{}.txt updated".format(self.comboRecScript.currentText()))

    def setFontSize(self):
        sizeFont = int(self.textFontSize.text())
        self.textRead.selectAll()
        self.textRead.setFontPointSize(sizeFont)


    # check if the specified in/output devices exist, otherwise quit the program
    def checkDevices(self):
        REC_IN_CARD = self.config["REC_IN_CARD"]
        REC_OUT_CARD = self.config["REC_OUT_CARD"]
        hasInputDev = False
        hasOutputDev = False

        p = pyaudio.PyAudio()
        count = p.get_device_count()
        for i in range(count):
            dev = p.get_device_info_by_index(i)
            print( dev['name'])
            if REC_IN_CARD in dev['name']:
                hasInputDev = True
            if dev['name'] == REC_OUT_CARD:
                hasOutputDev = True
        p.terminate()

        if hasInputDev == False:
            print( "Can't find input device: " + REC_IN_CARD)
            quit()
        if hasOutputDev == False:
            print( "Can't find output device: " + REC_OUT_CARD)
            quit()

def EndPlayRecThread(recorder):
    recorder.endPlayingRecording()

def main():

    app = QtWidgets.QApplication(sys.argv)
    recGUI = Recoder()
    recGUI.update()
    # run the GUI
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

