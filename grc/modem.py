#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: QO100Modem-NOTXSync
# Author: Vatan Zengin TA7WRS
# Copyright: Copyright (c) 2026 Vatan Zengin. Licensed under GPL v3. Read LISANCE.
# Description: https://github.com/vatanzngn/QO100DataModem
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt
from gnuradio import qtgui
import os
import sys
import logging as log

def get_state_directory() -> str:
    oldpath = os.path.expanduser("~/.grc_gnuradio")
    try:
        from gnuradio.gr import paths
        newpath = paths.persistent()
        if os.path.exists(newpath):
            return newpath
        if os.path.exists(oldpath):
            log.warning(f"Found persistent state path '{newpath}', but file does not exist. " +
                     f"Old default persistent state path '{oldpath}' exists; using that. " +
                     "Please consider moving state to new location.")
            return oldpath
        # Default to the correct path if both are configured.
        # neither old, nor new path exist: create new path, return that
        os.makedirs(newpath, exist_ok=True)
        return newpath
    except (ImportError, NameError):
        log.warning("Could not retrieve GNU Radio persistent state directory from GNU Radio. " +
                 "Trying defaults.")
        xdgstate = os.getenv("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
        xdgcand = os.path.join(xdgstate, "gnuradio")
        if os.path.exists(xdgcand):
            return xdgcand
        if os.path.exists(oldpath):
            log.warning(f"Using legacy state path '{oldpath}'. Please consider moving state " +
                     f"files to '{xdgcand}'.")
            return oldpath
        # neither old, nor new path exist: create new path, return that
        os.makedirs(xdgcand, exist_ok=True)
        return xdgcand

sys.path.append(os.environ.get('GRC_HIER_PATH', get_state_directory()))

from PyQt5 import QtCore
from QO100_QPSKDataModem_RX_nofec import QO100_QPSKDataModem_RX_nofec  # grc-generated hier_block
from QO100_QPSKDataModem_TX_nofec import QO100_QPSKDataModem_TX_nofec  # grc-generated hier_block
from QO100_SSBModem_RX import QO100_SSBModem_RX  # grc-generated hier_block
from QO100_SSBModem_TX import QO100_SSBModem_TX  # grc-generated hier_block
from QO100_TXSyncCal_RX import QO100_TXSyncCal_RX  # grc-generated hier_block
from QO100_TXSyncCal_TX import QO100_TXSyncCal_TX  # grc-generated hier_block
from RXSync import RXSync  # grc-generated hier_block
from gnuradio import analog
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import iio
import sip
import threading
import time



class modem(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "QO100Modem-NOTXSync", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("QO100Modem-NOTXSync")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "modem")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.upper_int = upper_int = -70
        self.txsync_txlo_drift = txsync_txlo_drift = 0
        self.txsync_enable = txsync_enable = 0
        self.txsync_debtone_freq = txsync_debtone_freq = 0
        self.txsync_caltone_freq = txsync_caltone_freq = 35000
        self.tx_lo = tx_lo = 2400250000
        self.tx_att = tx_att = 16
        self.ssb_tx_gain = ssb_tx_gain = 0.8
        self.ssb_tx_enable = ssb_tx_enable = 0
        self.ssb_enable = ssb_enable = 0
        self.sql_thresh = sql_thresh = -49
        self.sql_ramp = sql_ramp = 4800
        self.sql_alpha = sql_alpha = 0.001
        self.sdr_ip = sdr_ip = "ip:192.168.1.84"
        self.samp_rate = samp_rate = 960000
        self.rxsync_enable = rxsync_enable = 0
        self.rx_lo = rx_lo = 739750000
        self.rx_gain = rx_gain = 8
        self.qpskrx_costas_bw = qpskrx_costas_bw = 0.02
        self.qpsk_tx_gain = qpsk_tx_gain = 0.5
        self.qpsk_ted_gain = qpsk_ted_gain = 0.5
        self.qpsk_symsync_dev = qpsk_symsync_dev = 0.01
        self.qpsk_symsync_bw = qpsk_symsync_bw = 0.008
        self.qpsk_rrc_alpha = qpsk_rrc_alpha = 0.35
        self.qpsk_chan_bw = qpsk_chan_bw = 2800
        self.lower_int = lower_int = -112
        self.foff_ssb_ch1 = foff_ssb_ch1 = 50000
        self.foff_data_ch1 = foff_data_ch1 = (-124800)
        self.fine_tune = fine_tune = 0
        self.bt_loop_bw = bt_loop_bw = 0.005
        self.bt_filter_bw = bt_filter_bw = 1500
        self.bt_expected_beacon_freq = bt_expected_beacon_freq = 0
        self.audio_dev_name = audio_dev_name = "default"
        self.agc_ref = agc_ref = 0.5
        self.agc_max_gain = agc_max_gain = 3
        self.agc_gain = agc_gain = 1.0
        self.agc_decay = agc_decay = 0.00006
        self.agc_attack = agc_attack = 0.0008
        self.af_gain = af_gain = 0.5

        ##################################################
        # Blocks
        ##################################################

        self.tabs = Qt.QTabWidget()
        self.tabs_widget_0 = Qt.QWidget()
        self.tabs_layout_0 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_0)
        self.tabs_grid_layout_0 = Qt.QGridLayout()
        self.tabs_layout_0.addLayout(self.tabs_grid_layout_0)
        self.tabs.addTab(self.tabs_widget_0, 'RX Sync')
        self.tabs_widget_1 = Qt.QWidget()
        self.tabs_layout_1 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_1)
        self.tabs_grid_layout_1 = Qt.QGridLayout()
        self.tabs_layout_1.addLayout(self.tabs_grid_layout_1)
        self.tabs.addTab(self.tabs_widget_1, 'TX Sync')
        self.tabs_widget_2 = Qt.QWidget()
        self.tabs_layout_2 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_2)
        self.tabs_grid_layout_2 = Qt.QGridLayout()
        self.tabs_layout_2.addLayout(self.tabs_grid_layout_2)
        self.tabs.addTab(self.tabs_widget_2, 'SSB Control')
        self.tabs_widget_3 = Qt.QWidget()
        self.tabs_layout_3 = Qt.QBoxLayout(Qt.QBoxLayout.TopToBottom, self.tabs_widget_3)
        self.tabs_grid_layout_3 = Qt.QGridLayout()
        self.tabs_layout_3.addLayout(self.tabs_grid_layout_3)
        self.tabs.addTab(self.tabs_widget_3, 'QPSK Flow')
        self.top_layout.addWidget(self.tabs)
        self._upper_int_range = qtgui.Range(-80, 40, 1, -70, 200)
        self._upper_int_win = qtgui.RangeWidget(self._upper_int_range, self.set_upper_int, "Waterfall Upper Color Intensity", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_0.addWidget(self._upper_int_win)
        self._txsync_txlo_drift_range = qtgui.Range(-1500, 1500, 1, 0, 200)
        self._txsync_txlo_drift_win = qtgui.RangeWidget(self._txsync_txlo_drift_range, self.set_txsync_txlo_drift, "Clock Drift Amount", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._txsync_txlo_drift_win)
        _txsync_enable_check_box = Qt.QCheckBox("TX Sync Tone Enable")
        self._txsync_enable_choices = {True: 1, False: 0}
        self._txsync_enable_choices_inv = dict((v,k) for k,v in self._txsync_enable_choices.items())
        self._txsync_enable_callback = lambda i: Qt.QMetaObject.invokeMethod(_txsync_enable_check_box, "setChecked", Qt.Q_ARG("bool", self._txsync_enable_choices_inv[i]))
        self._txsync_enable_callback(self.txsync_enable)
        _txsync_enable_check_box.stateChanged.connect(lambda i: self.set_txsync_enable(self._txsync_enable_choices[bool(i)]))
        self.tabs_layout_1.addWidget(_txsync_enable_check_box)
        self._txsync_debtone_freq_range = qtgui.Range(-4000, 4000, 1, 0, 200)
        self._txsync_debtone_freq_win = qtgui.RangeWidget(self._txsync_debtone_freq_range, self.set_txsync_debtone_freq, "TX Sync Debug Tone Offset", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_1.addWidget(self._txsync_debtone_freq_win)
        self._txsync_caltone_freq_range = qtgui.Range(-400000, 400000, 1, 35000, 200)
        self._txsync_caltone_freq_win = qtgui.RangeWidget(self._txsync_caltone_freq_range, self.set_txsync_caltone_freq, "Caltone Freq", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_1.addWidget(self._txsync_caltone_freq_win)
        self._tx_att_range = qtgui.Range(0, 80, 1, 16, 200)
        self._tx_att_win = qtgui.RangeWidget(self._tx_att_range, self.set_tx_att, "TX Attenuation !", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._tx_att_win)
        self._ssb_tx_gain_range = qtgui.Range(0, 1, 0.01, 0.8, 200)
        self._ssb_tx_gain_win = qtgui.RangeWidget(self._ssb_tx_gain_range, self.set_ssb_tx_gain, "TX gain", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._ssb_tx_gain_win)
        _ssb_tx_enable_check_box = Qt.QCheckBox("SSB PTT")
        self._ssb_tx_enable_choices = {True: 1, False: 0}
        self._ssb_tx_enable_choices_inv = dict((v,k) for k,v in self._ssb_tx_enable_choices.items())
        self._ssb_tx_enable_callback = lambda i: Qt.QMetaObject.invokeMethod(_ssb_tx_enable_check_box, "setChecked", Qt.Q_ARG("bool", self._ssb_tx_enable_choices_inv[i]))
        self._ssb_tx_enable_callback(self.ssb_tx_enable)
        _ssb_tx_enable_check_box.stateChanged.connect(lambda i: self.set_ssb_tx_enable(self._ssb_tx_enable_choices[bool(i)]))
        self.tabs_layout_2.addWidget(_ssb_tx_enable_check_box)
        _ssb_enable_check_box = Qt.QCheckBox("SSB Enable")
        self._ssb_enable_choices = {True: 1, False: 0}
        self._ssb_enable_choices_inv = dict((v,k) for k,v in self._ssb_enable_choices.items())
        self._ssb_enable_callback = lambda i: Qt.QMetaObject.invokeMethod(_ssb_enable_check_box, "setChecked", Qt.Q_ARG("bool", self._ssb_enable_choices_inv[i]))
        self._ssb_enable_callback(self.ssb_enable)
        _ssb_enable_check_box.stateChanged.connect(lambda i: self.set_ssb_enable(self._ssb_enable_choices[bool(i)]))
        self.tabs_layout_2.addWidget(_ssb_enable_check_box)
        self._sql_thresh_range = qtgui.Range(-100, 0, 1, -49, 200)
        self._sql_thresh_win = qtgui.RangeWidget(self._sql_thresh_range, self.set_sql_thresh, "Squelch (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._sql_thresh_win)
        self._sql_ramp_range = qtgui.Range(0, 12000, 100, 4800, 200)
        self._sql_ramp_win = qtgui.RangeWidget(self._sql_ramp_range, self.set_sql_ramp, "Squelch ramp", "counter_slider", int, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._sql_ramp_win)
        self._sql_alpha_range = qtgui.Range(0.0001, 0.1, 0.0001, 0.001, 200)
        self._sql_alpha_win = qtgui.RangeWidget(self._sql_alpha_range, self.set_sql_alpha, "Squelch alpha", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._sql_alpha_win)
        _rxsync_enable_check_box = Qt.QCheckBox("RXSync Enable")
        self._rxsync_enable_choices = {True: 1, False: 0}
        self._rxsync_enable_choices_inv = dict((v,k) for k,v in self._rxsync_enable_choices.items())
        self._rxsync_enable_callback = lambda i: Qt.QMetaObject.invokeMethod(_rxsync_enable_check_box, "setChecked", Qt.Q_ARG("bool", self._rxsync_enable_choices_inv[i]))
        self._rxsync_enable_callback(self.rxsync_enable)
        _rxsync_enable_check_box.stateChanged.connect(lambda i: self.set_rxsync_enable(self._rxsync_enable_choices[bool(i)]))
        self.tabs_layout_0.addWidget(_rxsync_enable_check_box)
        self._rx_gain_range = qtgui.Range(0, 65, 1, 8, 200)
        self._rx_gain_win = qtgui.RangeWidget(self._rx_gain_range, self.set_rx_gain, "RX Gain", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_layout.addWidget(self._rx_gain_win)
        self._qpskrx_costas_bw_range = qtgui.Range(0.002, 0.15, 0.002, 0.02, 200)
        self._qpskrx_costas_bw_win = qtgui.RangeWidget(self._qpskrx_costas_bw_range, self.set_qpskrx_costas_bw, "QPSK Costas Loop BW", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_grid_layout_3.addWidget(self._qpskrx_costas_bw_win, 0, 0, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._qpsk_tx_gain_range = qtgui.Range(0, 1, 0.01, 0.5, 200)
        self._qpsk_tx_gain_win = qtgui.RangeWidget(self._qpsk_tx_gain_range, self.set_qpsk_tx_gain, "TX Gain", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_grid_layout_3.addWidget(self._qpsk_tx_gain_win, 2, 0, 1, 2)
        for r in range(2, 3):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 2):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._lower_int_range = qtgui.Range(-150, -80, 1, -112, 200)
        self._lower_int_win = qtgui.RangeWidget(self._lower_int_range, self.set_lower_int, "Waterfall Lower Color Intensity", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_0.addWidget(self._lower_int_win)
        self._foff_ssb_ch1_tool_bar = Qt.QToolBar(self)
        self._foff_ssb_ch1_tool_bar.addWidget(Qt.QLabel("T-SSB Freq Offs" + ": "))
        self._foff_ssb_ch1_line_edit = Qt.QLineEdit(str(self.foff_ssb_ch1))
        self._foff_ssb_ch1_tool_bar.addWidget(self._foff_ssb_ch1_line_edit)
        self._foff_ssb_ch1_line_edit.editingFinished.connect(
            lambda: self.set_foff_ssb_ch1(int(str(self._foff_ssb_ch1_line_edit.text()))))
        self.tabs_layout_2.addWidget(self._foff_ssb_ch1_tool_bar)
        self._foff_data_ch1_tool_bar = Qt.QToolBar(self)
        self._foff_data_ch1_tool_bar.addWidget(Qt.QLabel("T-Data Freq Offs" + ": "))
        self._foff_data_ch1_line_edit = Qt.QLineEdit(str(self.foff_data_ch1))
        self._foff_data_ch1_tool_bar.addWidget(self._foff_data_ch1_line_edit)
        self._foff_data_ch1_line_edit.editingFinished.connect(
            lambda: self.set_foff_data_ch1(int(str(self._foff_data_ch1_line_edit.text()))))
        self.tabs_grid_layout_3.addWidget(self._foff_data_ch1_tool_bar, 0, 1, 1, 1)
        for r in range(0, 1):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._fine_tune_range = qtgui.Range(-200, 200, 1, 0, 300)
        self._fine_tune_win = qtgui.RangeWidget(self._fine_tune_range, self.set_fine_tune, "Fine tune (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._fine_tune_win)
        self._bt_loop_bw_range = qtgui.Range(0.0001, 0.02, 0.0001, 0.005, 200)
        self._bt_loop_bw_win = qtgui.RangeWidget(self._bt_loop_bw_range, self.set_bt_loop_bw, "Costas Loop BW", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_0.addWidget(self._bt_loop_bw_win)
        self._bt_filter_bw_range = qtgui.Range(1000, 10000, 100, 1500, 200)
        self._bt_filter_bw_win = qtgui.RangeWidget(self._bt_filter_bw_range, self.set_bt_filter_bw, "Filter Bandwith", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_0.addWidget(self._bt_filter_bw_win)
        self._bt_expected_beacon_freq_range = qtgui.Range(-samp_rate/2, samp_rate/2, 1, 0, 200)
        self._bt_expected_beacon_freq_win = qtgui.RangeWidget(self._bt_expected_beacon_freq_range, self.set_bt_expected_beacon_freq, "Expected Freq", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_0.addWidget(self._bt_expected_beacon_freq_win)
        self._agc_ref_range = qtgui.Range(0.1, 1.0, 0.05, 0.5, 200)
        self._agc_ref_win = qtgui.RangeWidget(self._agc_ref_range, self.set_agc_ref, "AGC ref", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._agc_ref_win)
        self._agc_max_gain_range = qtgui.Range(1, 100, 0.5, 3, 200)
        self._agc_max_gain_win = qtgui.RangeWidget(self._agc_max_gain_range, self.set_agc_max_gain, "AGC max gain", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._agc_max_gain_win)
        self._agc_gain_range = qtgui.Range(0.01, 5.0, 0.01, 1.0, 200)
        self._agc_gain_win = qtgui.RangeWidget(self._agc_gain_range, self.set_agc_gain, "AGC init gain", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._agc_gain_win)
        self._agc_decay_range = qtgui.Range(0.00001, 0.01, 0.00001, 0.00006, 200)
        self._agc_decay_win = qtgui.RangeWidget(self._agc_decay_range, self.set_agc_decay, "AGC decay", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._agc_decay_win)
        self._agc_attack_range = qtgui.Range(0.0001, 0.05, 0.0001, 0.0008, 200)
        self._agc_attack_win = qtgui.RangeWidget(self._agc_attack_range, self.set_agc_attack, "AGC attack", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._agc_attack_win)
        self._af_gain_range = qtgui.Range(0, 2, 0.01, 0.5, 200)
        self._af_gain_win = qtgui.RangeWidget(self._af_gain_range, self.set_af_gain, "AF gain", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_layout_2.addWidget(self._af_gain_win)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_1 = qtgui.waterfall_sink_c(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            8000, #bw
            '', #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_update_time(0.2)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_1.enable_grid(True)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_1.enable_axis_labels(True)

        self.qtgui_waterfall_sink_x_1_0_0_1_0_1.disable_legend()


        labels = ['costas', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_intensity_range(lower_int, upper_int)

        self._qtgui_waterfall_sink_x_1_0_0_1_0_1_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_1_0_0_1_0_1.qwidget(), Qt.QWidget)

        self.tabs_grid_layout_3.addWidget(self._qtgui_waterfall_sink_x_1_0_0_1_0_1_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_0 = qtgui.waterfall_sink_c(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            (samp_rate/10), #bw
            "Costas Output", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_update_time(0.2)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_0.enable_grid(True)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_0.enable_axis_labels(True)



        labels = ['costas', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_intensity_range(lower_int, upper_int)

        self._qtgui_waterfall_sink_x_1_0_0_1_0_0_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_1_0_0_1_0_0.qwidget(), Qt.QWidget)

        self.tabs_grid_layout_0.addWidget(self._qtgui_waterfall_sink_x_1_0_0_1_0_0_win, 3, 1, 1, 1)
        for r in range(3, 4):
            self.tabs_grid_layout_0.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_0.setColumnStretch(c, 1)
        self.qtgui_waterfall_sink_x_1_0_0_1_0 = qtgui.waterfall_sink_c(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            (int(samp_rate/10)), #bw
            "Filtered Signal", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_waterfall_sink_x_1_0_0_1_0.set_update_time(0.2)
        self.qtgui_waterfall_sink_x_1_0_0_1_0.enable_grid(True)
        self.qtgui_waterfall_sink_x_1_0_0_1_0.enable_axis_labels(True)

        self.qtgui_waterfall_sink_x_1_0_0_1_0.disable_legend()


        labels = ['costas', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_1_0_0_1_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_1_0_0_1_0.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_1_0_0_1_0.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_1_0_0_1_0.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_1_0_0_1_0.set_intensity_range(lower_int, upper_int)

        self._qtgui_waterfall_sink_x_1_0_0_1_0_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_1_0_0_1_0.qwidget(), Qt.QWidget)

        self.tabs_grid_layout_0.addWidget(self._qtgui_waterfall_sink_x_1_0_0_1_0_win, 3, 0, 1, 1)
        for r in range(3, 4):
            self.tabs_grid_layout_0.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_0.setColumnStretch(c, 1)
        self.qtgui_waterfall_sink_x_0_1 = qtgui.waterfall_sink_c(
            16384, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate, #bw
            '', #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_waterfall_sink_x_0_1.set_update_time(0.1)
        self.qtgui_waterfall_sink_x_0_1.enable_grid(False)
        self.qtgui_waterfall_sink_x_0_1.enable_axis_labels(False)

        self.qtgui_waterfall_sink_x_0_1.disable_legend()


        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_0_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_0_1.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_0_1.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_0_1.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_0_1.set_intensity_range(lower_int, upper_int)

        self._qtgui_waterfall_sink_x_0_1_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_0_1.qwidget(), Qt.QWidget)

        self.top_grid_layout.addWidget(self._qtgui_waterfall_sink_x_0_1_win, 2, 0, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_waterfall_sink_x_0_0_0 = qtgui.waterfall_sink_f(
            512, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            24000, #bw
            'SSB Audio TX', #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_waterfall_sink_x_0_0_0.set_update_time(0.05)
        self.qtgui_waterfall_sink_x_0_0_0.enable_grid(False)
        self.qtgui_waterfall_sink_x_0_0_0.enable_axis_labels(True)


        self.qtgui_waterfall_sink_x_0_0_0.set_plot_pos_half(not True)

        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_0_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_0_0_0.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_0_0_0.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_0_0_0.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_0_0_0.set_intensity_range(-140, 10)

        self._qtgui_waterfall_sink_x_0_0_0_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_0_0_0.qwidget(), Qt.QWidget)

        self.tabs_grid_layout_2.addWidget(self._qtgui_waterfall_sink_x_0_0_0_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
        self.qtgui_waterfall_sink_x_0_0 = qtgui.waterfall_sink_c(
            512, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            24000, #bw
            'SSB Audio RX', #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_waterfall_sink_x_0_0.set_update_time(0.05)
        self.qtgui_waterfall_sink_x_0_0.enable_grid(False)
        self.qtgui_waterfall_sink_x_0_0.enable_axis_labels(True)



        labels = ['', '', '', '', '',
                  '', '', '', '', '']
        colors = [0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
                  1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_waterfall_sink_x_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_waterfall_sink_x_0_0.set_line_label(i, labels[i])
            self.qtgui_waterfall_sink_x_0_0.set_color_map(i, colors[i])
            self.qtgui_waterfall_sink_x_0_0.set_line_alpha(i, alphas[i])

        self.qtgui_waterfall_sink_x_0_0.set_intensity_range(-140, 10)

        self._qtgui_waterfall_sink_x_0_0_win = sip.wrapinstance(self.qtgui_waterfall_sink_x_0_0.qwidget(), Qt.QWidget)

        self.tabs_grid_layout_2.addWidget(self._qtgui_waterfall_sink_x_0_0_win, 1, 1, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_2.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_2.setColumnStretch(c, 1)
        self.qtgui_number_sink_0 = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            1,
            None # parent
        )
        self.qtgui_number_sink_0.set_update_time(0.10)
        self.qtgui_number_sink_0.set_title("TX Freq Error")

        labels = ['TX Freq Error', '', '', '', '',
            '', '', '', '', '']
        units = ['Hz', '', '', '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(1):
            self.qtgui_number_sink_0.set_min(i, -4000)
            self.qtgui_number_sink_0.set_max(i, +4000)
            self.qtgui_number_sink_0.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.qtgui_number_sink_0.set_label(i, "Data {0}".format(i))
            else:
                self.qtgui_number_sink_0.set_label(i, labels[i])
            self.qtgui_number_sink_0.set_unit(i, units[i])
            self.qtgui_number_sink_0.set_factor(i, factor[i])

        self.qtgui_number_sink_0.enable_autoscale(False)
        self._qtgui_number_sink_0_win = sip.wrapinstance(self.qtgui_number_sink_0.qwidget(), Qt.QWidget)
        self.tabs_layout_1.addWidget(self._qtgui_number_sink_0_win)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            4096, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            8000, #bw
            "Measurement Window", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0.set_y_axis((-140), 10)
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(True)
        self.qtgui_freq_sink_x_0.set_fft_average(0.2)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)
        self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)

        self.qtgui_freq_sink_x_0.disable_legend()


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
        self.tabs_layout_1.addWidget(self._qtgui_freq_sink_x_0_win)
        self.qtgui_const_sink_x_1 = qtgui.const_sink_c(
            512, #size
            "Modem 1", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_1.set_update_time(0.5)
        self.qtgui_const_sink_x_1.set_y_axis((-1), 1)
        self.qtgui_const_sink_x_1.set_x_axis((-1), 1)
        self.qtgui_const_sink_x_1.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_1.enable_autoscale(False)
        self.qtgui_const_sink_x_1.enable_grid(False)
        self.qtgui_const_sink_x_1.enable_axis_labels(True)

        self.qtgui_const_sink_x_1.disable_legend()

        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_const_sink_x_1.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_1.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_1.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_1.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_1.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_1.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_1.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_1_win = sip.wrapinstance(self.qtgui_const_sink_x_1.qwidget(), Qt.QWidget)
        self.tabs_grid_layout_3.addWidget(self._qtgui_const_sink_x_1_win, 1, 0, 1, 1)
        for r in range(1, 2):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._qpsk_ted_gain_range = qtgui.Range(0.1, 2.0, 0.05, 0.5, 250)
        self._qpsk_ted_gain_win = qtgui.RangeWidget(self._qpsk_ted_gain_range, self.set_qpsk_ted_gain, "QPSK TED Gain", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_grid_layout_3.addWidget(self._qpsk_ted_gain_win, 4, 0, 1, 1)
        for r in range(4, 5):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._qpsk_symsync_dev_range = qtgui.Range(0.001, 0.2, 0.001, 0.01, 250)
        self._qpsk_symsync_dev_win = qtgui.RangeWidget(self._qpsk_symsync_dev_range, self.set_qpsk_symsync_dev, "QPSK Symbol Sync MaxDev", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_grid_layout_3.addWidget(self._qpsk_symsync_dev_win, 3, 1, 1, 1)
        for r in range(3, 4):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._qpsk_symsync_bw_range = qtgui.Range(0.001, 0.05, 0.001, 0.008, 250)
        self._qpsk_symsync_bw_win = qtgui.RangeWidget(self._qpsk_symsync_bw_range, self.set_qpsk_symsync_bw, "QPSK Symbol Sync BW", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_grid_layout_3.addWidget(self._qpsk_symsync_bw_win, 3, 0, 1, 1)
        for r in range(3, 4):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 1):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._qpsk_rrc_alpha_range = qtgui.Range(0.1, 0.9, 0.05, 0.35, 250)
        self._qpsk_rrc_alpha_win = qtgui.RangeWidget(self._qpsk_rrc_alpha_range, self.set_qpsk_rrc_alpha, "QPSK RRC Alpha", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_grid_layout_3.addWidget(self._qpsk_rrc_alpha_win, 5, 0, 1, 2)
        for r in range(5, 6):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(0, 2):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self._qpsk_chan_bw_range = qtgui.Range(500, 5000, 100, 2800, 250)
        self._qpsk_chan_bw_win = qtgui.RangeWidget(self._qpsk_chan_bw_range, self.set_qpsk_chan_bw, "QPSK Channel BW (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.tabs_grid_layout_3.addWidget(self._qpsk_chan_bw_win, 4, 1, 1, 1)
        for r in range(4, 5):
            self.tabs_grid_layout_3.setRowStretch(r, 1)
        for c in range(1, 2):
            self.tabs_grid_layout_3.setColumnStretch(c, 1)
        self.iio_pluto_source_0 = iio.fmcomms2_source_fc32(sdr_ip if sdr_ip else iio.get_pluto_uri(), [True, True], 32768)
        self.iio_pluto_source_0.set_len_tag_key('packet_len')
        self.iio_pluto_source_0.set_frequency(rx_lo)
        self.iio_pluto_source_0.set_samplerate(samp_rate)
        self.iio_pluto_source_0.set_gain_mode(0, 'manual')
        self.iio_pluto_source_0.set_gain(0, rx_gain)
        self.iio_pluto_source_0.set_quadrature(True)
        self.iio_pluto_source_0.set_rfdc(True)
        self.iio_pluto_source_0.set_bbdc(True)
        self.iio_pluto_source_0.set_filter_params('Auto', '', 0, 0)
        self.iio_pluto_sink_0 = iio.fmcomms2_sink_fc32(sdr_ip if sdr_ip else iio.get_pluto_uri(), [True, True], 32768, False)
        self.iio_pluto_sink_0.set_len_tag_key('')
        self.iio_pluto_sink_0.set_bandwidth(1500000)
        self.iio_pluto_sink_0.set_frequency(tx_lo)
        self.iio_pluto_sink_0.set_samplerate(samp_rate)
        self.iio_pluto_sink_0.set_attenuation(0, tx_att)
        self.iio_pluto_sink_0.set_filter_params('Auto', '', 0, 0)
        self.blocks_multiply_xx_0_0 = blocks.multiply_vcc(1)
        self.blocks_file_sink_0 = blocks.file_sink(gr.sizeof_gr_complex*1, '/home/vatanz/Desktop/grcrec_sep18_13.04', False)
        self.blocks_file_sink_0.set_unbuffered(False)
        self.blocks_add_xx_0 = blocks.add_vcc(1)
        self.analog_sig_source_x_0 = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, (txsync_txlo_drift*(-1)), 1, 0, 0)
        self.RXSync_0 = RXSync(
            beacontrack_bw=bt_filter_bw,
            enable=rxsync_enable,
            expected_beacon_freq=bt_expected_beacon_freq,
            loop_bw=bt_loop_bw,
            samp_rate=samp_rate,
        )
        self.QO100_TXSyncCal_TX_0 = QO100_TXSyncCal_TX(
            cal_tone=txsync_caltone_freq,
            debug_tone_offset=txsync_debtone_freq,
            enable=txsync_enable,
        )
        self.QO100_TXSyncCal_RX_0 = QO100_TXSyncCal_RX(
            cal_tone=txsync_caltone_freq,
        )
        self.QO100_SSBModem_TX_0 = QO100_SSBModem_TX(
            agc_attack=agc_attack,
            agc_decay=agc_decay,
            agc_gain=agc_gain,
            agc_max_gain=agc_max_gain,
            agc_ref=agc_ref,
            dev_name=audio_dev_name,
            freq_offset=foff_ssb_ch1,
            samp_rate=samp_rate,
            tx_gain=ssb_tx_gain,
            txenable=ssb_tx_enable,
        )
        self.QO100_SSBModem_RX_0 = QO100_SSBModem_RX(
            af_gain=af_gain,
            agc_attack=agc_attack,
            agc_decay=agc_decay,
            agc_gain=agc_gain,
            agc_max_gain=agc_max_gain,
            agc_ref=agc_ref,
            dev_name=audio_dev_name,
            enable=ssb_enable,
            fine_tune=fine_tune,
            freq_offset=foff_ssb_ch1,
            samp_rate=samp_rate,
            sql_alpha=sql_alpha,
            sql_ramp=sql_ramp,
            sql_thresh=sql_thresh,
        )
        self.QO100_QPSKDataModem_TX_nofec_0 = QO100_QPSKDataModem_TX_nofec(
            freq_offs=foff_data_ch1,
            gain=qpsk_tx_gain,
            port=5001,
            samp_rate=960000,
        )
        self.QO100_QPSKDataModem_RX_nofec_0 = QO100_QPSKDataModem_RX_nofec(
            costas_bw=qpskrx_costas_bw,
            freq_offset=foff_data_ch1,
            logport=5002,
            port1=5003,
            port2=5004,
            port3=5005,
            port4=5006,
            samp_rate=960000,
            symsync_bw=0.008,
            symsync_dev=0.01,
            ted_gain=0.5,
            chan_bw=1500,
            rrc_alpha=0.35,
        )


        ##################################################
        # Connections
        ##################################################
        self.connect((self.QO100_QPSKDataModem_RX_nofec_0, 0), (self.qtgui_const_sink_x_1, 0))
        self.connect((self.QO100_QPSKDataModem_RX_nofec_0, 1), (self.qtgui_waterfall_sink_x_1_0_0_1_0_1, 0))
        self.connect((self.QO100_QPSKDataModem_TX_nofec_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.QO100_SSBModem_RX_0, 0), (self.qtgui_waterfall_sink_x_0_0, 0))
        self.connect((self.QO100_SSBModem_TX_0, 0), (self.blocks_add_xx_0, 2))
        self.connect((self.QO100_SSBModem_TX_0, 1), (self.qtgui_waterfall_sink_x_0_0_0, 0))
        self.connect((self.QO100_TXSyncCal_RX_0, 1), (self.qtgui_freq_sink_x_0, 0))
        self.connect((self.QO100_TXSyncCal_RX_0, 0), (self.qtgui_number_sink_0, 0))
        self.connect((self.QO100_TXSyncCal_TX_0, 0), (self.blocks_add_xx_0, 0))
        self.connect((self.RXSync_0, 0), (self.QO100_QPSKDataModem_RX_nofec_0, 0))
        self.connect((self.RXSync_0, 0), (self.QO100_SSBModem_RX_0, 0))
        self.connect((self.RXSync_0, 0), (self.QO100_TXSyncCal_RX_0, 0))
        self.connect((self.RXSync_0, 0), (self.qtgui_waterfall_sink_x_0_1, 0))
        self.connect((self.RXSync_0, 2), (self.qtgui_waterfall_sink_x_1_0_0_1_0, 0))
        self.connect((self.RXSync_0, 1), (self.qtgui_waterfall_sink_x_1_0_0_1_0_0, 0))
        self.connect((self.analog_sig_source_x_0, 0), (self.blocks_multiply_xx_0_0, 0))
        self.connect((self.blocks_add_xx_0, 0), (self.blocks_multiply_xx_0_0, 1))
        self.connect((self.blocks_multiply_xx_0_0, 0), (self.iio_pluto_sink_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.RXSync_0, 0))
        self.connect((self.iio_pluto_source_0, 0), (self.blocks_file_sink_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "modem")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_upper_int(self):
        return self.upper_int

    def set_upper_int(self, upper_int):
        self.upper_int = upper_int
        self.qtgui_waterfall_sink_x_0_1.set_intensity_range(self.lower_int, self.upper_int)
        self.qtgui_waterfall_sink_x_1_0_0_1_0.set_intensity_range(self.lower_int, self.upper_int)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_intensity_range(self.lower_int, self.upper_int)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_intensity_range(self.lower_int, self.upper_int)

    def get_txsync_txlo_drift(self):
        return self.txsync_txlo_drift

    def set_txsync_txlo_drift(self, txsync_txlo_drift):
        self.txsync_txlo_drift = txsync_txlo_drift
        self.analog_sig_source_x_0.set_frequency((self.txsync_txlo_drift*(-1)))

    def get_txsync_enable(self):
        return self.txsync_enable

    def set_txsync_enable(self, txsync_enable):
        self.txsync_enable = txsync_enable
        self._txsync_enable_callback(self.txsync_enable)
        self.QO100_TXSyncCal_TX_0.set_enable(self.txsync_enable)

    def get_txsync_debtone_freq(self):
        return self.txsync_debtone_freq

    def set_txsync_debtone_freq(self, txsync_debtone_freq):
        self.txsync_debtone_freq = txsync_debtone_freq
        self.QO100_TXSyncCal_TX_0.set_debug_tone_offset(self.txsync_debtone_freq)

    def get_txsync_caltone_freq(self):
        return self.txsync_caltone_freq

    def set_txsync_caltone_freq(self, txsync_caltone_freq):
        self.txsync_caltone_freq = txsync_caltone_freq
        self.QO100_TXSyncCal_RX_0.set_cal_tone(self.txsync_caltone_freq)
        self.QO100_TXSyncCal_TX_0.set_cal_tone(self.txsync_caltone_freq)

    def get_tx_lo(self):
        return self.tx_lo

    def set_tx_lo(self, tx_lo):
        self.tx_lo = tx_lo
        self.iio_pluto_sink_0.set_frequency(self.tx_lo)

    def get_tx_att(self):
        return self.tx_att

    def set_tx_att(self, tx_att):
        self.tx_att = tx_att
        self.iio_pluto_sink_0.set_attenuation(0,self.tx_att)

    def get_ssb_tx_gain(self):
        return self.ssb_tx_gain

    def set_ssb_tx_gain(self, ssb_tx_gain):
        self.ssb_tx_gain = ssb_tx_gain
        self.QO100_SSBModem_TX_0.set_tx_gain(self.ssb_tx_gain)

    def get_ssb_tx_enable(self):
        return self.ssb_tx_enable

    def set_ssb_tx_enable(self, ssb_tx_enable):
        self.ssb_tx_enable = ssb_tx_enable
        self._ssb_tx_enable_callback(self.ssb_tx_enable)
        self.QO100_SSBModem_TX_0.set_txenable(self.ssb_tx_enable)

    def get_ssb_enable(self):
        return self.ssb_enable

    def set_ssb_enable(self, ssb_enable):
        self.ssb_enable = ssb_enable
        self._ssb_enable_callback(self.ssb_enable)
        self.QO100_SSBModem_RX_0.set_enable(self.ssb_enable)

    def get_sql_thresh(self):
        return self.sql_thresh

    def set_sql_thresh(self, sql_thresh):
        self.sql_thresh = sql_thresh
        self.QO100_SSBModem_RX_0.set_sql_thresh(self.sql_thresh)

    def get_sql_ramp(self):
        return self.sql_ramp

    def set_sql_ramp(self, sql_ramp):
        self.sql_ramp = sql_ramp
        self.QO100_SSBModem_RX_0.set_sql_ramp(self.sql_ramp)

    def get_sql_alpha(self):
        return self.sql_alpha

    def set_sql_alpha(self, sql_alpha):
        self.sql_alpha = sql_alpha
        self.QO100_SSBModem_RX_0.set_sql_alpha(self.sql_alpha)

    def get_sdr_ip(self):
        return self.sdr_ip

    def set_sdr_ip(self, sdr_ip):
        self.sdr_ip = sdr_ip

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.QO100_SSBModem_RX_0.set_samp_rate(self.samp_rate)
        self.QO100_SSBModem_TX_0.set_samp_rate(self.samp_rate)
        self.RXSync_0.set_samp_rate(self.samp_rate)
        self.analog_sig_source_x_0.set_sampling_freq(self.samp_rate)
        self.iio_pluto_sink_0.set_samplerate(self.samp_rate)
        self.iio_pluto_source_0.set_samplerate(self.samp_rate)
        self.qtgui_waterfall_sink_x_0_1.set_frequency_range(0, self.samp_rate)
        self.qtgui_waterfall_sink_x_1_0_0_1_0.set_frequency_range(0, (int(self.samp_rate/10)))
        self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_frequency_range(0, (self.samp_rate/10))

    def get_rxsync_enable(self):
        return self.rxsync_enable

    def set_rxsync_enable(self, rxsync_enable):
        self.rxsync_enable = rxsync_enable
        self._rxsync_enable_callback(self.rxsync_enable)
        self.RXSync_0.set_enable(self.rxsync_enable)

    def get_rx_lo(self):
        return self.rx_lo

    def set_rx_lo(self, rx_lo):
        self.rx_lo = rx_lo
        self.iio_pluto_source_0.set_frequency(self.rx_lo)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.iio_pluto_source_0.set_gain(0, self.rx_gain)

    def get_qpskrx_costas_bw(self):
        return self.qpskrx_costas_bw

    def set_qpskrx_costas_bw(self, qpskrx_costas_bw):
        self.qpskrx_costas_bw = qpskrx_costas_bw
        self.QO100_QPSKDataModem_RX_nofec_0.set_costas_bw(self.qpskrx_costas_bw)

    def get_qpsk_tx_gain(self):
        return self.qpsk_tx_gain

    def set_qpsk_tx_gain(self, qpsk_tx_gain):
        self.qpsk_tx_gain = qpsk_tx_gain
        self.QO100_QPSKDataModem_TX_nofec_0.set_gain(self.qpsk_tx_gain)

    def get_qpsk_ted_gain(self):
        return self.qpsk_ted_gain

    def set_qpsk_ted_gain(self, qpsk_ted_gain):
        self.qpsk_ted_gain = qpsk_ted_gain

    def get_qpsk_symsync_dev(self):
        return self.qpsk_symsync_dev

    def set_qpsk_symsync_dev(self, qpsk_symsync_dev):
        self.qpsk_symsync_dev = qpsk_symsync_dev

    def get_qpsk_symsync_bw(self):
        return self.qpsk_symsync_bw

    def set_qpsk_symsync_bw(self, qpsk_symsync_bw):
        self.qpsk_symsync_bw = qpsk_symsync_bw

    def get_qpsk_rrc_alpha(self):
        return self.qpsk_rrc_alpha

    def set_qpsk_rrc_alpha(self, qpsk_rrc_alpha):
        self.qpsk_rrc_alpha = qpsk_rrc_alpha

    def get_qpsk_chan_bw(self):
        return self.qpsk_chan_bw

    def set_qpsk_chan_bw(self, qpsk_chan_bw):
        self.qpsk_chan_bw = qpsk_chan_bw

    def get_lower_int(self):
        return self.lower_int

    def set_lower_int(self, lower_int):
        self.lower_int = lower_int
        self.qtgui_waterfall_sink_x_0_1.set_intensity_range(self.lower_int, self.upper_int)
        self.qtgui_waterfall_sink_x_1_0_0_1_0.set_intensity_range(self.lower_int, self.upper_int)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_0.set_intensity_range(self.lower_int, self.upper_int)
        self.qtgui_waterfall_sink_x_1_0_0_1_0_1.set_intensity_range(self.lower_int, self.upper_int)

    def get_foff_ssb_ch1(self):
        return self.foff_ssb_ch1

    def set_foff_ssb_ch1(self, foff_ssb_ch1):
        self.foff_ssb_ch1 = foff_ssb_ch1
        Qt.QMetaObject.invokeMethod(self._foff_ssb_ch1_line_edit, "setText", Qt.Q_ARG("QString", str(self.foff_ssb_ch1)))
        self.QO100_SSBModem_RX_0.set_freq_offset(self.foff_ssb_ch1)
        self.QO100_SSBModem_TX_0.set_freq_offset(self.foff_ssb_ch1)

    def get_foff_data_ch1(self):
        return self.foff_data_ch1

    def set_foff_data_ch1(self, foff_data_ch1):
        self.foff_data_ch1 = foff_data_ch1
        Qt.QMetaObject.invokeMethod(self._foff_data_ch1_line_edit, "setText", Qt.Q_ARG("QString", str(self.foff_data_ch1)))
        self.QO100_QPSKDataModem_RX_nofec_0.set_freq_offset(self.foff_data_ch1)
        self.QO100_QPSKDataModem_TX_nofec_0.set_freq_offs(self.foff_data_ch1)

    def get_fine_tune(self):
        return self.fine_tune

    def set_fine_tune(self, fine_tune):
        self.fine_tune = fine_tune
        self.QO100_SSBModem_RX_0.set_fine_tune(self.fine_tune)

    def get_bt_loop_bw(self):
        return self.bt_loop_bw

    def set_bt_loop_bw(self, bt_loop_bw):
        self.bt_loop_bw = bt_loop_bw
        self.RXSync_0.set_loop_bw(self.bt_loop_bw)

    def get_bt_filter_bw(self):
        return self.bt_filter_bw

    def set_bt_filter_bw(self, bt_filter_bw):
        self.bt_filter_bw = bt_filter_bw
        self.RXSync_0.set_beacontrack_bw(self.bt_filter_bw)

    def get_bt_expected_beacon_freq(self):
        return self.bt_expected_beacon_freq

    def set_bt_expected_beacon_freq(self, bt_expected_beacon_freq):
        self.bt_expected_beacon_freq = bt_expected_beacon_freq
        self.RXSync_0.set_expected_beacon_freq(self.bt_expected_beacon_freq)

    def get_audio_dev_name(self):
        return self.audio_dev_name

    def set_audio_dev_name(self, audio_dev_name):
        self.audio_dev_name = audio_dev_name
        self.QO100_SSBModem_RX_0.set_dev_name(self.audio_dev_name)
        self.QO100_SSBModem_TX_0.set_dev_name(self.audio_dev_name)

    def get_agc_ref(self):
        return self.agc_ref

    def set_agc_ref(self, agc_ref):
        self.agc_ref = agc_ref
        self.QO100_SSBModem_RX_0.set_agc_ref(self.agc_ref)
        self.QO100_SSBModem_TX_0.set_agc_ref(self.agc_ref)

    def get_agc_max_gain(self):
        return self.agc_max_gain

    def set_agc_max_gain(self, agc_max_gain):
        self.agc_max_gain = agc_max_gain
        self.QO100_SSBModem_RX_0.set_agc_max_gain(self.agc_max_gain)
        self.QO100_SSBModem_TX_0.set_agc_max_gain(self.agc_max_gain)

    def get_agc_gain(self):
        return self.agc_gain

    def set_agc_gain(self, agc_gain):
        self.agc_gain = agc_gain
        self.QO100_SSBModem_RX_0.set_agc_gain(self.agc_gain)
        self.QO100_SSBModem_TX_0.set_agc_gain(self.agc_gain)

    def get_agc_decay(self):
        return self.agc_decay

    def set_agc_decay(self, agc_decay):
        self.agc_decay = agc_decay
        self.QO100_SSBModem_RX_0.set_agc_decay(self.agc_decay)
        self.QO100_SSBModem_TX_0.set_agc_decay(self.agc_decay)

    def get_agc_attack(self):
        return self.agc_attack

    def set_agc_attack(self, agc_attack):
        self.agc_attack = agc_attack
        self.QO100_SSBModem_RX_0.set_agc_attack(self.agc_attack)
        self.QO100_SSBModem_TX_0.set_agc_attack(self.agc_attack)

    def get_af_gain(self):
        return self.af_gain

    def set_af_gain(self, af_gain):
        self.af_gain = af_gain
        self.QO100_SSBModem_RX_0.set_af_gain(self.af_gain)




def main(top_block_cls=modem, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
