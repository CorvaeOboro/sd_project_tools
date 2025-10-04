"""
VIDEO Music Sync - Align audio to video timing via waveform analysis

Given a music video and target audio track, synchronize the audio to the video's timing
by using multiple techniques including chromagram analysis , spectral correlation , beat alignment, 
and similarity scoring.

Features:
- GUI with drag & drop for video/audio inputs
- Accepts audio files (.wav, .mp3, .flac, etc.) or video files (extracts audio)
- Trying varied techniques : spectral correlation, beat matching, chromagram analysis
- randomized-sampling offset search with scoring
- Exports metrics report JSON  
- CLI mode for batch processing

Usage:
    GUI (default):  python VIDEO_music_sync.py , or launch from launch tools 
    CLI:            python VIDEO_music_sync.py --video input.mp4 --audio target.wav --out synced.mp4

STATUS:: working  
VERSION::20251004
"""

import os
import sys
import json
import argparse
from dataclasses import dataclass, asdict
from typing import Optional, Tuple

import numpy as np
import librosa
import soundfile as sf
import scipy.signal as _spsig
import pygame
import threading
import time

# ======================== Compatibility Shims ========================

# MoviePy import fallback for different versions
try:
    import moviepy.editor as mpe
except Exception:
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        from moviepy.audio.io.AudioFileClip import AudioFileClip

        class _MPE:
            VideoFileClip = VideoFileClip
            AudioFileClip = AudioFileClip

        mpe = _MPE()
    except Exception as _err:
        raise ImportError(
            "MoviePy is installed but 'moviepy.editor' is unavailable. "
            "Try: pip install 'moviepy<2'"
        ) from _err

# SciPy window function compatibility (hann moved to scipy.signal.windows in newer versions)
try:
    _ = _spsig.hann
except AttributeError:
    try:
        from scipy.signal.windows import hann as _hann
        setattr(_spsig, 'hann', lambda M, sym=True: _hann(M, sym=sym))
    except Exception:
        pass

# PyQt5 import 
from PyQt5 import QtCore, QtGui, QtWidgets

class WaveformWidget(QtWidgets.QWidget):
    """Custom widget for rendering waveforms with color-coded similarity."""
    
    clicked_time = QtCore.pyqtSignal(float)  # Signal emitted when user clicks on waveform
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(400)
        self.video_waveform = None
        self.target_waveform = None
        self.similarity = None
        self.time_axis = None
        self.offset = 0.0
        self.video_beats = None
        self.target_beats = None
        
    def set_waveforms(self, video_data, target_data, similarity_data, time_data, offset, video_beats=None, target_beats=None):
        """Update waveform data and trigger repaint."""
        self.video_waveform = video_data
        self.target_waveform = target_data
        self.similarity = similarity_data
        self.time_axis = time_data
        self.offset = offset
        self.video_beats = video_beats
        self.target_beats = target_beats
        self.update()  # Trigger paintEvent
    
    def paintEvent(self, event):
        """Paint the waveforms."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QtGui.QColor(30, 30, 30))
        
        if self.video_waveform is None or self.target_waveform is None:
            # Draw placeholder text
            painter.setPen(QtGui.QColor(100, 100, 100))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, 
                           "Load waveforms to see visualization")
            return
        
        width = self.width()
        height = self.height()
        
        # Split into two sections (top = video, bottom = target) with NO gap
        video_height = height // 2
        target_height = height // 2
        video_y_offset = 0
        target_y_offset = height // 2
        
        # Draw labels
        painter.setPen(QtGui.QColor(200, 200, 200))
        painter.drawText(10, video_y_offset + 15, f"VIDEO AUDIO (offset={self.offset:+.3f}s)")
        painter.drawText(10, target_y_offset + 15, "TARGET AUDIO")
        
        # Draw waveforms
        num_samples = len(self.video_waveform)
        
        for i in range(num_samples - 1):
            x1 = int((i / num_samples) * width)
            x2 = int(((i + 1) / num_samples) * width)
            
            # Get similarity color
            sim = self.similarity[i] if i < len(self.similarity) else 0.0
            if sim > 0.7:
                color = QtGui.QColor(0, 255, 0, 200)  # Green - strong match
            elif sim > 0.4:
                color = QtGui.QColor(60, 80, 140, 200)  # Dark blue - medium match
            elif sim > 0.0:
                color = QtGui.QColor(80, 60, 120, 180)  # Dark purple - weak match
            else:
                color = QtGui.QColor(20, 20, 20, 200)  # Black - poor match
            
            painter.setPen(QtGui.QPen(color, 1))
            
            # Video waveform
            v1 = self.video_waveform[i]
            v2 = self.video_waveform[i + 1]
            y1_video = int(video_y_offset + video_height // 2 - v1 * video_height // 2)
            y2_video = int(video_y_offset + video_height // 2 - v2 * video_height // 2)
            painter.drawLine(x1, y1_video, x2, y2_video)
            
            # Target waveform
            t1 = self.target_waveform[i]
            t2 = self.target_waveform[i + 1]
            y1_target = int(target_y_offset + target_height // 2 - t1 * target_height // 2)
            y2_target = int(target_y_offset + target_height // 2 - t2 * target_height // 2)
            painter.drawLine(x1, y1_target, x2, y2_target)
        
        # Draw center lines
        painter.setPen(QtGui.QColor(80, 80, 80))
        painter.drawLine(0, video_y_offset + video_height // 2, width, video_y_offset + video_height // 2)
        painter.drawLine(0, target_y_offset + target_height // 2, width, target_y_offset + target_height // 2)
        
        # Draw beat markers as single-pixel lines at edges for alignment checking
        # Video beats at BOTTOM of video waveform section
        if self.video_beats is not None and self.time_axis is not None and len(self.time_axis) > 0:
            max_time = self.time_axis[-1]
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 200, 255), 1))  # Cyan, 1px wide
            video_beat_y = video_y_offset + video_height  # Bottom edge of video waveform
            for beat_time in self.video_beats:
                if 0 <= beat_time <= max_time:
                    x = int((beat_time / max_time) * width)
                    # Draw single pixel line at bottom of video waveform
                    painter.drawLine(x, video_beat_y - 5, x, video_beat_y)
        
        # Target beats at TOP of target waveform section
        if self.target_beats is not None and self.time_axis is not None and len(self.time_axis) > 0:
            max_time = self.time_axis[-1]
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 0, 255), 1))  # Magenta, 1px wide
            target_beat_y = target_y_offset  # Top edge of target waveform
            for beat_time in self.target_beats:
                adjusted_beat = beat_time + self.offset
                if 0 <= adjusted_beat <= max_time:
                    x = int((adjusted_beat / max_time) * width)
                    # Draw single pixel line at top of target waveform
                    painter.drawLine(x, target_beat_y, x, target_beat_y + 5)
        
        # Draw time markers
        painter.setPen(QtGui.QColor(150, 150, 150))
        if self.time_axis is not None and len(self.time_axis) > 0:
            max_time = self.time_axis[-1]
            for t in range(0, int(max_time) + 1, 10):  # Every 10 seconds
                x = int((t / max_time) * width)
                painter.drawLine(x, 0, x, height)
                painter.drawText(x + 2, height - 5, f"{t}s")
        
    
    def mousePressEvent(self, event):
        """Handle mouse clicks to set playhead position."""
        if self.time_axis is not None and len(self.time_axis) > 0:
            # Calculate time from click position
            x = event.x()
            width = self.width()
            max_time = self.time_axis[-1]
            clicked_time = (x / width) * max_time
            
            # Emit signal with the clicked time
            self.clicked_time.emit(clicked_time)

class DropLineEdit(QtWidgets.QLineEdit):
    """QLineEdit that accepts file drag-and-drop with optional extension filtering."""
    def __init__(self, parent=None, *, name: str = '', exts: Optional[Tuple[str, ...]] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._exts = tuple(e.lower() for e in (exts or ()))
        self._name = name
        self.setPlaceholderText(f'Drop {name} here or click Browse…')

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = [u.toLocalFile() for u in event.mimeData().urls()]
            if urls:
                p = urls[0]
                if os.path.isfile(p):
                    if not self._exts or os.path.splitext(p)[1].lower() in self._exts:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        urls = [u.toLocalFile() for u in event.mimeData().urls()]
        if urls:
            p = urls[0]
            if os.path.isfile(p):
                if not self._exts or os.path.splitext(p)[1].lower() in self._exts:
                    self.setText(p)
        event.acceptProposedAction()

class EmittingStream(QtCore.QObject):
    text_written = QtCore.pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass

class SyncWorker(QtCore.QThread):
    finished_ok = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)
    log_text = QtCore.pyqtSignal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self.params = params

    def run(self):
        # Redirect stdout to GUI
        old_stdout = sys.stdout
        emitter = EmittingStream()
        emitter.text_written.connect(self.log_text.emit)
        sys.stdout = emitter
        try:
            # Only do search, no export
            result = search_sync_offset(
                video_path=self.params['video'],
                target_audio_path=self.params['audio'],
                sr=int(self.params.get('sr', 22050)),
                hop_length=int(self.params.get('hop', 512)),
                max_seek_s=float(self.params.get('max_seek', 10.0)),
            )
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            sys.stdout = old_stdout

class VideoMusicSyncGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Video Music Sync - GUI with Waveform Viewer')
        self.setMinimumSize(1400, 900)
        self._build_ui()
        self.worker: Optional[SyncWorker] = None
        
        # Store loaded audio for visualization
        self.video_audio = None
        self.target_audio = None
        self.video_beats = None
        self.target_beats = None
        self.sr = 22050
        self.current_offset = 0.0
        
        # Audio playback
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        self.is_playing = False
        self.video_muted = False
        self.target_muted = False
        self.playback_thread = None
        self.playhead_position = 0.0  # seconds
        
        # Auto-sync results
        self.sync_results = []  # Store all randomized sampling results
        self.candidate_buttons = []  # Store candidate offset buttons

    def _build_ui(self):

        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-size: 11px;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
                color: #e0e0e0;
            }
            QLineEdit:focus {
                border: 1px solid #6a9fb5;
            }
            QPushButton {
                background-color: #4a5a6a;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6a7a;
            }
            QPushButton:pressed {
                background-color: #3a4a5a;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                color: #e0e0e0;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 3px;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)

        # Inputs group
        grp_inputs = QtWidgets.QGroupBox('Inputs')
        inputs_layout = QtWidgets.QGridLayout(grp_inputs)

        self.ed_video = DropLineEdit(name='video (.mp4/.mov/.mkv)', exts=('.mp4', '.mov', '.mkv', '.avi'))
        self.btn_video = QtWidgets.QPushButton('Browse…')
        self.btn_video.clicked.connect(self.browse_video)

        self.ed_audio = DropLineEdit(
            name='audio or video (.wav/.mp3/.flac/.m4a/.aac or .mp4/.mov/.mkv/.avi/.webm)',
            exts=('.wav', '.mp3', '.flac', '.m4a', '.aac', '.mp4', '.mov', '.mkv', '.avi', '.webm')
        )
        self.btn_audio = QtWidgets.QPushButton('Browse…')
        self.btn_audio.clicked.connect(self.browse_audio)

        inputs_layout.addWidget(QtWidgets.QLabel('Video'), 0, 0)
        inputs_layout.addWidget(self.ed_video, 0, 1)
        inputs_layout.addWidget(self.btn_video, 0, 2)

        inputs_layout.addWidget(QtWidgets.QLabel('Target Audio/Video'), 1, 0)
        inputs_layout.addWidget(self.ed_audio, 1, 1)
        inputs_layout.addWidget(self.btn_audio, 1, 2)

        layout.addWidget(grp_inputs)

        # Output group
        grp_output = QtWidgets.QGroupBox('Output')
        out_layout = QtWidgets.QGridLayout(grp_output)

        self.ed_out = DropLineEdit(name='output video (.mp4)', exts=('.mp4',))
        self.btn_out = QtWidgets.QPushButton('Browse…')
        self.btn_out.clicked.connect(self.browse_out)

        self.ed_report = DropLineEdit(name='optional report (.json)', exts=('.json',))
        self.btn_report = QtWidgets.QPushButton('Browse…')
        self.btn_report.clicked.connect(self.browse_report)

        out_layout.addWidget(QtWidgets.QLabel('Output Video'), 0, 0)
        out_layout.addWidget(self.ed_out, 0, 1)
        out_layout.addWidget(self.btn_out, 0, 2)

        out_layout.addWidget(QtWidgets.QLabel('Report (optional)'), 1, 0)
        out_layout.addWidget(self.ed_report, 1, 1)
        out_layout.addWidget(self.btn_report, 1, 2)

        layout.addWidget(grp_output)

        # Waveform visualization and manual offset controls
        grp_waveform = QtWidgets.QGroupBox('Waveform Comparison & Manual Offset')
        waveform_layout = QtWidgets.QVBoxLayout(grp_waveform)
        
        # Load waveforms button and legend on same row
        load_layout = QtWidgets.QHBoxLayout()
        self.btn_load_waveforms = QtWidgets.QPushButton('Load Waveforms for Comparison')
        self.btn_load_waveforms.clicked.connect(self.load_waveforms)
        self.btn_load_waveforms.setStyleSheet("""
            QPushButton {
                background-color: #5a6a8a;
                color: #ffffff;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6a7a9a; }
            QPushButton:pressed { background-color: #4a5a7a; }
        """)
        load_layout.addWidget(self.btn_load_waveforms)
        
        load_layout.addSpacing(20)
        
        # Legend for waveform colors (inline with button)
        load_layout.addWidget(QtWidgets.QLabel('Similarity:'))
        
        lbl_strong = QtWidgets.QLabel('█ Strong (>0.7)')
        lbl_strong.setStyleSheet('color: #00ff00; font-weight: bold;')
        load_layout.addWidget(lbl_strong)
        
        lbl_medium = QtWidgets.QLabel('█ Medium (>0.4)')
        lbl_medium.setStyleSheet('color: #5080c0; font-weight: bold;')
        load_layout.addWidget(lbl_medium)
        
        lbl_weak = QtWidgets.QLabel('█ Weak (>0.0)')
        lbl_weak.setStyleSheet('color: #7060a0; font-weight: bold;')
        load_layout.addWidget(lbl_weak)
        
        lbl_poor = QtWidgets.QLabel('█ Poor (<0.0)')
        lbl_poor.setStyleSheet('color: #404040; font-weight: bold;')
        load_layout.addWidget(lbl_poor)
        
        load_layout.addWidget(QtWidgets.QLabel('  |  Beats:'))
        
        lbl_video_beats = QtWidgets.QLabel('█ Video')
        lbl_video_beats.setStyleSheet('color: #00c8ff; font-weight: bold;')
        load_layout.addWidget(lbl_video_beats)
        
        lbl_target_beats = QtWidgets.QLabel('█ Target (offset adjusted)')
        lbl_target_beats.setStyleSheet('color: #ff00ff; font-weight: bold;')
        load_layout.addWidget(lbl_target_beats)
        
        load_layout.addStretch(1)
        waveform_layout.addLayout(load_layout)
        
        # Custom waveform widget (reduced height to 90%)
        self.waveform_widget = WaveformWidget()
        self.waveform_widget.setMinimumHeight(360)  # 90% of 400
        self.waveform_widget.clicked_time.connect(self.on_waveform_clicked)
        waveform_layout.addWidget(self.waveform_widget)
        
        # Manual offset controls
        manual_layout = QtWidgets.QHBoxLayout()
        manual_layout.addWidget(QtWidgets.QLabel('Manual Offset (seconds):'))
        
        # Beat snap buttons
        self.btn_prev_beat = QtWidgets.QPushButton('◄ Prev Beat')
        self.btn_prev_beat.clicked.connect(self.snap_to_prev_beat)
        self.btn_prev_beat.setStyleSheet("""
            QPushButton {
                background-color: #5a6a8a;
                color: #ffffff;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #6a7a9a; }
        """)
        manual_layout.addWidget(self.btn_prev_beat)
        
        self.spin_manual_offset = QtWidgets.QDoubleSpinBox()
        self.spin_manual_offset.setRange(-60.0, 60.0)
        self.spin_manual_offset.setSingleStep(0.1)
        self.spin_manual_offset.setDecimals(3)
        self.spin_manual_offset.setValue(0.0)
        self.spin_manual_offset.valueChanged.connect(self.on_manual_offset_changed)
        manual_layout.addWidget(self.spin_manual_offset)
        
        self.btn_next_beat = QtWidgets.QPushButton('Next Beat ►')
        self.btn_next_beat.clicked.connect(self.snap_to_next_beat)
        self.btn_next_beat.setStyleSheet("""
            QPushButton {
                background-color: #5a6a8a;
                color: #ffffff;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #6a7a9a; }
        """)
        manual_layout.addWidget(self.btn_next_beat)
        
        self.lbl_similarity = QtWidgets.QLabel('Similarity: N/A')
        manual_layout.addWidget(self.lbl_similarity)
        manual_layout.addStretch(1)
        waveform_layout.addLayout(manual_layout)
        
        # Playback controls
        playback_layout = QtWidgets.QHBoxLayout()
        
        # Playhead position control
        playback_layout.addWidget(QtWidgets.QLabel('Start at:'))
        self.spin_playhead = QtWidgets.QDoubleSpinBox()
        self.spin_playhead.setRange(0.0, 120.0)
        self.spin_playhead.setSingleStep(1.0)
        self.spin_playhead.setDecimals(2)
        self.spin_playhead.setValue(0.0)
        self.spin_playhead.setSuffix(' s')
        self.spin_playhead.setMinimumWidth(80)
        playback_layout.addWidget(self.spin_playhead)
        
        # Play button
        self.btn_play = QtWidgets.QPushButton('▶ Play')
        self.btn_play.clicked.connect(self.start_playback)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background-color: #5a7a5a;
                color: #ffffff;
                font-size: 14px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6a8a6a; }
            QPushButton:pressed { background-color: #4a6a4a; }
        """)
        playback_layout.addWidget(self.btn_play)
        
        # Pause button
        self.btn_pause = QtWidgets.QPushButton('⏸ Pause')
        self.btn_pause.clicked.connect(self.stop_playback)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #7a6a5a;
                color: #ffffff;
                font-size: 14px;
                padding: 10px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #8a7a6a; }
            QPushButton:pressed { background-color: #6a5a4a; }
            QPushButton:disabled {
                background-color: #4a4a4a;
                color: #888;
            }
        """)
        playback_layout.addWidget(self.btn_pause)
        
        self.btn_mute_video = QtWidgets.QPushButton('🔊 Video Audio')
        self.btn_mute_video.setCheckable(True)
        self.btn_mute_video.clicked.connect(self.toggle_video_mute)
        self.btn_mute_video.setStyleSheet("""
            QPushButton {
                background-color: #5a6a8a;
                color: #ffffff;
                font-size: 12px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6a7a9a; }
            QPushButton:checked {
                background-color: #8a4a4a;
            }
        """)
        playback_layout.addWidget(self.btn_mute_video)
        
        self.btn_mute_target = QtWidgets.QPushButton('🔊 Target Audio')
        self.btn_mute_target.setCheckable(True)
        self.btn_mute_target.clicked.connect(self.toggle_target_mute)
        self.btn_mute_target.setStyleSheet("""
            QPushButton {
                background-color: #7a5a8a;
                color: #ffffff;
                font-size: 12px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #8a6a9a; }
            QPushButton:checked {
                background-color: #8a4a4a;
            }
        """)
        playback_layout.addWidget(self.btn_mute_target)
        
        playback_layout.addStretch(1)
        waveform_layout.addLayout(playback_layout)
        
        layout.addWidget(grp_waveform)

        # Auto-sync section - Settings on left, Results on right
        autosync_row = QtWidgets.QHBoxLayout()
        
        # Left side: Auto-sync settings and controls
        grp_autosync = QtWidgets.QGroupBox('Auto Sync Settings')
        autosync_layout = QtWidgets.QVBoxLayout(grp_autosync)
        
        # Settings row
        settings_layout = QtWidgets.QHBoxLayout()
        
        settings_layout.addWidget(QtWidgets.QLabel('Sample rate (Hz):'))
        self.spin_sr = QtWidgets.QSpinBox()
        self.spin_sr.setRange(8000, 96000)
        self.spin_sr.setSingleStep(1000)
        self.spin_sr.setValue(22050)
        self.spin_sr.setMinimumWidth(80)
        settings_layout.addWidget(self.spin_sr)
        
        settings_layout.addWidget(QtWidgets.QLabel('  Hop:'))
        self.spin_hop = QtWidgets.QSpinBox()
        self.spin_hop.setRange(64, 8192)
        self.spin_hop.setSingleStep(64)
        self.spin_hop.setValue(512)
        self.spin_hop.setMinimumWidth(70)
        settings_layout.addWidget(self.spin_hop)
        
        settings_layout.addWidget(QtWidgets.QLabel('  Max Search Offset (s):'))
        self.dsp_maxseek = QtWidgets.QDoubleSpinBox()
        self.dsp_maxseek.setRange(0.0, 120.0)
        self.dsp_maxseek.setSingleStep(0.5)
        self.dsp_maxseek.setDecimals(2)
        self.dsp_maxseek.setValue(30.0)
        self.dsp_maxseek.setMinimumWidth(70)
        settings_layout.addWidget(self.dsp_maxseek)
        
        settings_layout.addStretch(1)
        autosync_layout.addLayout(settings_layout)
        
        # Run button row
        run_layout = QtWidgets.QHBoxLayout()
        self.btn_start = QtWidgets.QPushButton('▶ Run Sync Search')
        self.btn_start.clicked.connect(self.on_start)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #5a7a5a;
                color: #ffffff;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6a8a6a; }
            QPushButton:pressed { background-color: #4a6a4a; }
        """)
        run_layout.addWidget(self.btn_start)
        
        self.lbl_status = QtWidgets.QLabel('Idle')
        self.lbl_status.setStyleSheet('color: #888; font-size: 12px;')
        run_layout.addWidget(self.lbl_status)
        
        run_layout.addSpacing(20)
        
        # Export button (moved here from playback section)
        self.btn_export = QtWidgets.QPushButton('📁 Export Video with Current Offset')
        self.btn_export.clicked.connect(self.export_video)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #5a7a5a;
                color: #ffffff;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6a8a6a; }
            QPushButton:pressed { background-color: #4a6a4a; }
        """)
        run_layout.addWidget(self.btn_export)
        
        run_layout.addStretch(1)
        autosync_layout.addLayout(run_layout)
        
        autosync_row.addWidget(grp_autosync)
        
        # Right side: Sync results panel
        grp_results = QtWidgets.QGroupBox('Results - Click to Test')
        results_layout = QtWidgets.QVBoxLayout(grp_results)
        
        # Scroll area for candidate buttons
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(120)
        scroll_content = QtWidgets.QWidget()
        self.results_button_layout = QtWidgets.QVBoxLayout(scroll_content)
        self.results_button_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        results_layout.addWidget(scroll)
        
        # Feedback buttons
        feedback_layout = QtWidgets.QHBoxLayout()
        feedback_layout.addWidget(QtWidgets.QLabel('Rate:'))
        
        self.btn_feedback_good = QtWidgets.QPushButton('good')
        self.btn_feedback_good.clicked.connect(lambda: self.submit_feedback('good'))
        self.btn_feedback_good.setStyleSheet("""
            QPushButton {
                background-color: #4a7a4a;
                color: #ffffff;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #5a8a5a; }
        """)
        feedback_layout.addWidget(self.btn_feedback_good)
        
        self.btn_feedback_ok = QtWidgets.QPushButton('ok')
        self.btn_feedback_ok.clicked.connect(lambda: self.submit_feedback('ok'))
        self.btn_feedback_ok.setStyleSheet("""
            QPushButton {
                background-color: #6a7a5a;
                color: #ffffff;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #7a8a6a; }
        """)
        feedback_layout.addWidget(self.btn_feedback_ok)
        
        self.btn_feedback_bad = QtWidgets.QPushButton('bad')
        self.btn_feedback_bad.clicked.connect(lambda: self.submit_feedback('bad'))
        self.btn_feedback_bad.setStyleSheet("""
            QPushButton {
                background-color: #7a4a4a;
                color: #ffffff;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #8a5a5a; }
        """)
        feedback_layout.addWidget(self.btn_feedback_bad)
        
        feedback_layout.addStretch(1)
        results_layout.addLayout(feedback_layout)
        
        autosync_row.addWidget(grp_results)
        
        layout.addLayout(autosync_row)

        # Log
        self.txt_log = QtWidgets.QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText('Logs will appear here…')
        layout.addWidget(self.txt_log, 1)

    def browse_video(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Video', '',
                                                        'Video Files (*.mp4 *.mov *.mkv *.avi);;All Files (*)')
        if path:
            self.ed_video.setText(path)
            self._maybe_autofill_output()

    def browse_audio(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Select Audio or Video (audio will be extracted from video)',
            '',
            'Audio/Video (*.wav *.mp3 *.flac *.m4a *.aac *.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)'
        )
        if path:
            self.ed_audio.setText(path)

    def browse_out(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Output Video', '', 'MP4 Video (*.mp4)')
        if path:
            if os.path.splitext(path)[1].lower() != '.mp4':
                path = os.path.splitext(path)[0] + '.mp4'
            self.ed_out.setText(path)

    def browse_report(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Report', '', 'JSON (*.json)')
        if path:
            if os.path.splitext(path)[1].lower() != '.json':
                path = os.path.splitext(path)[0] + '.json'
            self.ed_report.setText(path)

    def _maybe_autofill_output(self):
        vid = self.ed_video.text().strip()
        if vid and not self.ed_out.text().strip():
            base, _ = os.path.splitext(vid)
            self.ed_out.setText(base + '_synced.mp4')

    def _append_log(self, text: str):
        self.txt_log.moveCursor(QtGui.QTextCursor.End)
        self.txt_log.insertPlainText(text)
        self.txt_log.moveCursor(QtGui.QTextCursor.End)

    def on_start(self):
        video = self.ed_video.text().strip()
        audio = self.ed_audio.text().strip()

        # Validation - only need video and audio for search
        errors = []
        if not video or not os.path.isfile(video):
            errors.append(f'[ERROR] Invalid video: {video}')
        if not audio or not os.path.isfile(audio):
            errors.append(f'[ERROR] Invalid audio: {audio}')
        if errors:
            for e in errors:
                self._append_log(e + '\n')
            self.lbl_status.setText('Errors in inputs')
            self.lbl_status.setStyleSheet('color: #c00;')
            return

        params = {
            'video': video,
            'audio': audio,
            'sr': int(self.spin_sr.value()),
            'hop': int(self.spin_hop.value()),
            'max_seek': float(self.dsp_maxseek.value()),
        }

        self.txt_log.clear()
        self.lbl_status.setText('Running…')
        self.lbl_status.setStyleSheet('color: #0a0;')
        self.btn_start.setEnabled(False)

        self.worker = SyncWorker(params)
        self.worker.log_text.connect(self._append_log)
        self.worker.finished_ok.connect(self.on_finished_ok)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_any_finished)
        self.worker.start()

    def on_finished_ok(self, result: object):
        self._append_log('\n[GUI] Search complete.\n')
        self.lbl_status.setText('Done - Review results')
        self.lbl_status.setStyleSheet('color: #08c;')
        
        # Populate results if available
        if hasattr(result, 'sync_points') and result.sync_points:
            self.populate_sync_results(result.sync_points, result.final_offset_s)
            # Set the recommended offset in the manual offset field
            self.spin_manual_offset.setValue(result.final_offset_s)
            self._append_log(f'[RECOMMENDED] Set manual offset to: {result.final_offset_s:+.3f}s\n')
            self._append_log('[INFO] Click candidate buttons to test other offsets, then Export when ready.\n')

    def on_failed(self, msg: str):
        self._append_log(f"\n[GUI] Failed: {msg}\n")
        self.lbl_status.setText('Failed')
        self.lbl_status.setStyleSheet('color: #c00;')

    def on_any_finished(self):
        self.btn_start.setEnabled(True)
    
    def populate_sync_results(self, sync_points, selected_offset):
        """Populate the results panel with clickable offset candidates."""
        # Clear existing buttons
        for btn in self.candidate_buttons:
            btn.deleteLater()
        self.candidate_buttons.clear()
        
        # Store results
        self.sync_results = sync_points
        
        # Create button for each candidate
        for i, result in enumerate(sync_points[:10], 1):  # Top 10
            offset = result['offset_s']
            chroma = result['chroma_correlation']
            combined = result['combined_score']
            onset = result['onset_correlation']
            
            # Determine if this is the selected offset
            is_selected = abs(offset - selected_offset) < 0.01
            
            # Create button text with all scores
            btn_text = f"#{i}: {offset:+.2f}s | Chroma:{chroma:.3f} Combined:{combined:.3f} Onset:{onset:.3f}"
            if is_selected:
                btn_text = f"★ {btn_text} (SELECTED)"
            
            btn = QtWidgets.QPushButton(btn_text)
            btn.clicked.connect(lambda checked, o=offset: self.apply_candidate_offset(o))
            
            # Style based on selection and scores
            if is_selected:
                bg_color = '#5a7a8a'  # Blue for selected
            elif chroma > 0.5:
                bg_color = '#5a7a5a'  # Green for high chroma
            elif combined > 0.3:
                bg_color = '#6a6a5a'  # Yellow-ish for decent combined
            else:
                bg_color = '#5a5a5a'  # Gray for low scores
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: #ffffff;
                    padding: 8px;
                    text-align: left;
                    font-family: monospace;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #7a7a8a;
                }}
            """)
            
            self.results_button_layout.insertWidget(self.results_button_layout.count() - 1, btn)
            self.candidate_buttons.append(btn)
        
        self._append_log(f'[RESULTS] Loaded {len(sync_points)} candidate offsets. Click to test each one.\n')
    
    def apply_candidate_offset(self, offset):
        """Apply a candidate offset from the results."""
        self.spin_manual_offset.setValue(offset)
        self._append_log(f'[CANDIDATE] Applied offset: {offset:+.3f}s. Play to test sync quality.\n')
    
    def submit_feedback(self, rating):
        """Submit feedback about current offset quality."""
        current_offset = self.current_offset
        
        # Find which candidate this is
        candidate_info = None
        for i, result in enumerate(self.sync_results, 1):
            if abs(result['offset_s'] - current_offset) < 0.01:
                candidate_info = f"#{i} (chroma={result['chroma_correlation']:.3f}, combined={result['combined_score']:.3f})"
                break
        
        if candidate_info:
            self._append_log(f'[FEEDBACK] Offset {current_offset:+.3f}s rated as "{rating}" - Candidate {candidate_info}\n')
        else:
            self._append_log(f'[FEEDBACK] Offset {current_offset:+.3f}s rated as "{rating}" - Manual offset\n')
        
        # Log to file for analysis
        feedback_file = 'video_music_sync_feedback.log'
        try:
            with open(feedback_file, 'a', encoding='utf-8') as f:
                import datetime
                timestamp = datetime.datetime.now().isoformat()
                video = self.ed_video.text().strip()
                audio = self.ed_audio.text().strip()
                
                f.write(f"{timestamp}|{rating}|{current_offset:.3f}|{video}|{audio}")
                if candidate_info:
                    f.write(f"|{candidate_info}")
                f.write("\n")
            
            self._append_log(f'[FEEDBACK] Logged to {feedback_file}\n')
        except Exception as e:
            self._append_log(f'[FEEDBACK] Failed to log: {e}\n')
    
    def load_waveforms(self):
        """Load audio from video and target for waveform visualization."""
        video = self.ed_video.text().strip()
        audio = self.ed_audio.text().strip()
        
        if not video or not os.path.isfile(video):
            self._append_log('[ERROR] Please select a valid video file first\n')
            return
        if not audio or not os.path.isfile(audio):
            self._append_log('[ERROR] Please select a valid audio/video file first\n')
            return
        
        try:
            self._append_log('[LOAD] Loading video audio...\n')
            self.video_audio, _, _ = load_audio_from_video(video, self.sr)
            
            self._append_log('[LOAD] Loading target audio...\n')
            self.target_audio, _, _ = load_audio_from_any(audio, self.sr)
            
            # Detect beats
            self._append_log('[ANALYZE] Detecting beats in video audio...\n')
            onset_env = librosa.onset.onset_strength(y=self.video_audio, sr=self.sr, hop_length=512, aggregate=np.median)
            _, video_beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=self.sr, hop_length=512)
            self.video_beats = librosa.frames_to_time(video_beat_frames, sr=self.sr, hop_length=512)
            
            self._append_log('[ANALYZE] Detecting beats in target audio...\n')
            onset_env = librosa.onset.onset_strength(y=self.target_audio, sr=self.sr, hop_length=512, aggregate=np.median)
            _, target_beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=self.sr, hop_length=512)
            self.target_beats = librosa.frames_to_time(target_beat_frames, sr=self.sr, hop_length=512)
            
            self._append_log(f'[SUCCESS] Audio loaded. Found {len(self.video_beats)} video beats, {len(self.target_beats)} target beats\n')
            self.visualize_waveforms()
            
        except Exception as e:
            self._append_log(f'[ERROR] Failed to load audio: {e}\n')
    
    def visualize_waveforms(self):
        """Create graphical waveform visualization with color-coded matching regions."""
        if self.video_audio is None or self.target_audio is None:
            return
        
        # Downsample for visualization (show first 120 seconds)
        max_duration = 120.0  # seconds
        downsample_factor = int(self.sr * 0.05)  # 1 sample per 0.05s = 20 samples/sec
        
        video_viz = self.video_audio[::downsample_factor]
        target_viz = self.target_audio[::downsample_factor]
        
        # Apply current offset
        offset_samples = int(self.current_offset * self.sr / downsample_factor)
        if offset_samples > 0:
            target_viz = np.pad(target_viz, (offset_samples, 0), mode='constant')
        elif offset_samples < 0:
            target_viz = target_viz[abs(offset_samples):]
        
        # Limit to max duration
        max_samples = int(max_duration * 20)  # 20 samples per second
        video_viz = video_viz[:max_samples]
        target_viz = target_viz[:max_samples]
        
        # Match lengths
        min_len = min(len(video_viz), len(target_viz))
        video_viz = video_viz[:min_len]
        target_viz = target_viz[:min_len]
        
        # Normalize to [-1, 1]
        video_viz = video_viz / (np.max(np.abs(video_viz)) + 1e-8)
        target_viz = target_viz / (np.max(np.abs(target_viz)) + 1e-8)
        
        # Compute local similarity for color coding
        window_size = 10  # 0.5 second window
        similarity = []
        for i in range(len(video_viz)):
            start = max(0, i - window_size // 2)
            end = min(len(video_viz), i + window_size // 2 + 1)
            v_seg = video_viz[start:end]
            t_seg = target_viz[start:end]
            if len(v_seg) > 1 and len(t_seg) > 1:
                corr = np.corrcoef(v_seg, t_seg)[0, 1]
                similarity.append(corr if not np.isnan(corr) else 0.0)
            else:
                similarity.append(0.0)
        
        # Create time axis
        time_axis = np.arange(len(video_viz)) * 0.05  # 0.05 seconds per sample
        
        # Update the waveform widget with beats
        self.waveform_widget.set_waveforms(
            video_viz, target_viz, similarity, time_axis, self.current_offset,
            self.video_beats, self.target_beats
        )
        
        # Update similarity score
        avg_similarity = np.mean(similarity)
        self.lbl_similarity.setText(f'Similarity: {avg_similarity:.3f}')
        if avg_similarity > 0.7:
            self.lbl_similarity.setStyleSheet('color: #0a0; font-weight: bold;')
        elif avg_similarity > 0.4:
            self.lbl_similarity.setStyleSheet('color: #fa0; font-weight: bold;')
        else:
            self.lbl_similarity.setStyleSheet('color: #f00; font-weight: bold;')
    
    def on_manual_offset_changed(self, value):
        """Update visualization when manual offset changes."""
        self.current_offset = value
        if self.video_audio is not None and self.target_audio is not None:
            self.visualize_waveforms()
    
    def on_waveform_clicked(self, time_seconds):
        """Handle waveform click to set playhead position."""
        self.spin_playhead.setValue(time_seconds)
        self._append_log(f'[PLAYHEAD] Set to {time_seconds:.2f}s (click on waveform)\n')
    
    def snap_to_prev_beat(self):
        """Snap offset to align with previous beat pair."""
        if self.video_beats is None or self.target_beats is None:
            self._append_log('[ERROR] Please load waveforms first\n')
            return
        
        if len(self.video_beats) == 0 or len(self.target_beats) == 0:
            self._append_log('[ERROR] No beats detected\n')
            return
        
        # Find the best previous beat alignment
        current_offset = self.current_offset
        
        # Generate all possible offsets from beat pairs
        possible_offsets = []
        for v_beat in self.video_beats[:50]:  # Check first 50 beats
            for t_beat in self.target_beats[:50]:
                offset = t_beat - v_beat
                # Only consider offsets less than current (previous)
                if offset < current_offset - 0.01:  # Small epsilon to avoid same beat
                    possible_offsets.append(offset)
        
        if not possible_offsets:
            self._append_log('[BEAT SNAP] No previous beat alignment found\n')
            return
        
        # Find the closest offset to current
        possible_offsets.sort(reverse=True)  # Sort descending
        best_offset = possible_offsets[0]  # Largest offset that's still less than current
        
        self.spin_manual_offset.setValue(best_offset)
        self._append_log(f'[BEAT SNAP] Snapped to previous beat alignment: {best_offset:+.3f}s\n')
    
    def snap_to_next_beat(self):
        """Snap offset to align with next beat pair."""
        if self.video_beats is None or self.target_beats is None:
            self._append_log('[ERROR] Please load waveforms first\n')
            return
        
        if len(self.video_beats) == 0 or len(self.target_beats) == 0:
            self._append_log('[ERROR] No beats detected\n')
            return
        
        # Find the best next beat alignment
        current_offset = self.current_offset
        
        # Generate all possible offsets from beat pairs
        possible_offsets = []
        for v_beat in self.video_beats[:50]:  # Check first 50 beats
            for t_beat in self.target_beats[:50]:
                offset = t_beat - v_beat
                # Only consider offsets greater than current (next)
                if offset > current_offset + 0.01:  # Small epsilon to avoid same beat
                    possible_offsets.append(offset)
        
        if not possible_offsets:
            self._append_log('[BEAT SNAP] No next beat alignment found\n')
            return
        
        # Find the closest offset to current
        possible_offsets.sort()  # Sort ascending
        best_offset = possible_offsets[0]  # Smallest offset that's still greater than current
        
        self.spin_manual_offset.setValue(best_offset)
        self._append_log(f'[BEAT SNAP] Snapped to next beat alignment: {best_offset:+.3f}s\n')
    
    def start_playback(self):
        """Start playing both audio tracks with current offset from playhead position."""
        if self.video_audio is None or self.target_audio is None:
            self._append_log('[ERROR] Please load waveforms first\n')
            return
        
        if self.is_playing:
            return  # Already playing
        
        self.is_playing = True
        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.playhead_position = self.spin_playhead.value()
        
        # Create mixed audio for playback
        def playback_worker():
            try:
                # Apply offset to target
                offset_samples = int(self.current_offset * self.sr)
                if offset_samples > 0:
                    target_aligned = np.pad(self.target_audio, (offset_samples, 0), mode='constant')
                elif offset_samples < 0:
                    target_aligned = self.target_audio[abs(offset_samples):]
                else:
                    target_aligned = self.target_audio
                
                # Match lengths
                min_len = min(len(self.video_audio), len(target_aligned))
                video_clip = self.video_audio[:min_len]
                target_clip = target_aligned[:min_len]
                
                # Start from playhead position
                start_sample = int(self.playhead_position * self.sr)
                if start_sample >= min_len:
                    start_sample = 0
                video_clip = video_clip[start_sample:]
                target_clip = target_clip[start_sample:]
                
                # Apply muting
                if self.video_muted:
                    video_clip = np.zeros_like(video_clip)
                if self.target_muted:
                    target_clip = np.zeros_like(target_clip)
                
                # Mix to stereo (video=left, target=right for separation)
                stereo = np.column_stack((video_clip, target_clip))
                
                # Normalize
                stereo = stereo / (np.max(np.abs(stereo)) + 1e-8) * 0.8
                stereo = (stereo * 32767).astype(np.int16)
                
                # Play using pygame
                sound = pygame.sndarray.make_sound(stereo)
                sound.play()
                
                # Wait for playback to finish or stop
                while pygame.mixer.get_busy() and self.is_playing:
                    time.sleep(0.1)
                
                # Reset buttons
                self.btn_play.setEnabled(True)
                self.btn_pause.setEnabled(False)
                self.is_playing = False
                
            except Exception as e:
                self._append_log(f'[ERROR] Playback failed: {e}\n')
                self.is_playing = False
                self.btn_play.setEnabled(True)
                self.btn_pause.setEnabled(False)
        
        self.playback_thread = threading.Thread(target=playback_worker, daemon=True)
        self.playback_thread.start()
    
    def stop_playback(self):
        """Stop audio playback."""
        self.is_playing = False
        pygame.mixer.stop()
        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(False)
    
    def toggle_video_mute(self):
        """Toggle video audio mute."""
        self.video_muted = self.btn_mute_video.isChecked()
        if self.video_muted:
            self.btn_mute_video.setText('🔇 Video Audio (Muted)')
        else:
            self.btn_mute_video.setText('🔊 Video Audio')
    
    def toggle_target_mute(self):
        """Toggle target audio mute."""
        self.target_muted = self.btn_mute_target.isChecked()
        if self.target_muted:
            self.btn_mute_target.setText('🔇 Target Audio (Muted)')
        else:
            self.btn_mute_target.setText('🔊 Target Audio')
    
    def export_video(self):
        """Export video with current manual offset."""
        video = self.ed_video.text().strip()
        audio = self.ed_audio.text().strip()
        out = self.ed_out.text().strip()
        
        if not video or not os.path.isfile(video):
            self._append_log('[ERROR] Invalid video file\n')
            return
        if not audio or not os.path.isfile(audio):
            self._append_log('[ERROR] Invalid audio file\n')
            return
        if not out:
            self._append_log('[ERROR] Please specify output path\n')
            return
        
        if self.target_audio is None:
            self._append_log('[ERROR] Please load waveforms first\n')
            return
        
        try:
            self._append_log(f'[EXPORT] Exporting with offset: {self.current_offset:+.3f}s\n')
            
            # Load video to get duration
            video_clip = mpe.VideoFileClip(video)
            video_duration = float(video_clip.duration)
            video_clip.close()
            
            # Apply offset
            offset_samples = int(self.current_offset * self.sr)
            if offset_samples > 0:
                aligned_audio = np.pad(self.target_audio, (offset_samples, 0), mode='constant')
            elif offset_samples < 0:
                aligned_audio = self.target_audio[abs(offset_samples):]
            else:
                aligned_audio = self.target_audio
            
            # Trim/pad to video duration
            target_len = int(video_duration * self.sr)
            if len(aligned_audio) > target_len:
                aligned_audio = aligned_audio[:target_len]
            elif len(aligned_audio) < target_len:
                aligned_audio = np.pad(aligned_audio, (0, target_len - len(aligned_audio)), mode='constant')
            
            # Export
            self._append_log(f'[EXPORT] Writing video -> {out}\n')
            export_video_with_audio(video, aligned_audio, self.sr, out)
            self._append_log('[SUCCESS] Export complete!\n')
            
        except Exception as e:
            self._append_log(f'[ERROR] Export failed: {e}\n')

def gui_main():
    app = QtWidgets.QApplication(sys.argv)
    w = VideoMusicSyncGUI()
    w.show()
    sys.exit(app.exec_())

# ========================= Audio beat sync  =========================

def _get_local_temp_dir(reference_path: str) -> str:
    """Create a temp directory in the same folder as reference_path instead of AppData."""
    ref_dir = os.path.dirname(os.path.abspath(reference_path))
    temp_base = os.path.join(ref_dir, '.temp_video_sync')
    os.makedirs(temp_base, exist_ok=True)
    return temp_base

@dataclass
class SyncPoint:
    """Individual sync point from cross-correlation analysis."""
    segment_start_s: float
    offset_s: float
    correlation: float
    confidence: str  # 'high', 'medium', 'low'

@dataclass
class SyncResult:
    video_path: str
    audio_path: str
    output_path: str
    video_duration_s: float
    target_audio_duration_s: float
    final_offset_s: float
    sync_points: list  # List of SyncPoint dicts
    offset_method: str  # 'median', 'weighted_average', 'single_peak'
    sync_quality: str  # 'excellent', 'ok', 'fair', 'poor'
    notes: str = ""

def load_audio_from_video(video_path: str, sr: int) -> Tuple[np.ndarray, int, float]:
    """Extract audio from video using moviepy and resample to sr with librosa.
    Returns (mono_audio, sr, duration_seconds)."""
    video_clip = mpe.VideoFileClip(video_path)
    if video_clip.audio is None:
        raise RuntimeError("Video has no audio track.")
    # Write to temp wav in local folder to avoid AppData issues
    temp_dir = _get_local_temp_dir(video_path)
    temporary_wav_path = os.path.join(temp_dir, f"_temp_extract_{os.getpid()}.wav")
    try:
        video_clip.audio.write_audiofile(temporary_wav_path, fps=sr, codec="pcm_s16le", logger=None)
        audio_waveform, output_sample_rate = librosa.load(temporary_wav_path, sr=sr, mono=True)
    finally:
        duration_seconds = float(video_clip.duration)
        video_clip.close()
        # Clean up temp file
        try:
            if os.path.exists(temporary_wav_path):
                os.remove(temporary_wav_path)
        except Exception:
            pass
    return audio_waveform, output_sample_rate, duration_seconds

def load_audio_file(audio_path: str, sr: int) -> Tuple[np.ndarray, int, float]:
    """Load arbitrary audio file to mono with librosa at sr. Returns (y, sr, duration)."""
    audio_waveform, output_sample_rate = librosa.load(audio_path, sr=sr, mono=True)
    return audio_waveform, output_sample_rate, float(len(audio_waveform) / max(output_sample_rate, 1))

def load_audio_from_any(path: str, sr: int) -> Tuple[np.ndarray, int, float]:
    """Load audio from an audio file, or extract audio from a video if a video is provided."""
    file_extension = os.path.splitext(path)[1].lower()
    video_extensions = {'.mp4', '.mov', '.mkv', '.avi', '.webm'}
    if file_extension in video_extensions:
        print(f"[LOAD] Target is a video; extracting audio: {path}")
        return load_audio_from_video(path, sr)
    else:
        return load_audio_file(path, sr)

def onset_envelope(y: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    # Normalize for robust cross-correlation
    envelope = envelope.astype(np.float32)
    if np.max(np.abs(envelope)) > 0:
        envelope = envelope / (np.max(np.abs(envelope)) + 1e-8)
    return envelope

def compute_chromagram(y: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    """Compute chromagram (pitch class profile) for harmonic content matching."""
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    return chroma

def compute_spectral_contrast(y: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    """Compute spectral contrast for timbral matching."""
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop_length)
    return contrast

def compute_mfcc(y: np.ndarray, sr: int, hop_length: int, n_mfcc: int = 13) -> np.ndarray:
    """Compute MFCCs for timbral similarity."""
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop_length, n_mfcc=n_mfcc)
    return mfcc

def randomized_sampling_offset_search(video_y: np.ndarray, target_y: np.ndarray, sr: int, hop_length: int,
                               max_offset_s: float = 10.0, step_s: float = 0.1) -> list:
    """randomized sampling search for best offset using multiple similarity metrics.
    Tests offsets from -max_offset_s to +max_offset_s in step_s increments.
    Returns list of (offset_s, scores_dict) tuples.
    """
    print(f"[randomized sampling] Testing offsets from {-max_offset_s:.1f}s to +{max_offset_s:.1f}s in {step_s:.2f}s steps...")
    
    # Compute features for video audio 
    print("[FEATURES] Computing chromagram for video audio...")
    video_chroma = compute_chromagram(video_y, sr, hop_length)
    print("[FEATURES] Computing spectral contrast for video audio...")
    video_contrast = compute_spectral_contrast(video_y, sr, hop_length)
    print("[FEATURES] Computing MFCC for video audio...")
    video_mfcc = compute_mfcc(video_y, sr, hop_length)
    print("[FEATURES] Computing onset envelope for video audio...")
    video_onset = onset_envelope(video_y, sr, hop_length)
    
    # Compute features for target audio
    print("[FEATURES] Computing chromagram for target audio...")
    target_chroma = compute_chromagram(target_y, sr, hop_length)
    print("[FEATURES] Computing spectral contrast for target audio...")
    target_contrast = compute_spectral_contrast(target_y, sr, hop_length)
    print("[FEATURES] Computing MFCC for target audio...")
    target_mfcc = compute_mfcc(target_y, sr, hop_length)
    print("[FEATURES] Computing onset envelope for target audio...")
    target_onset = onset_envelope(target_y, sr, hop_length)
    
    # Test different offsets
    offset_step_frames = int(step_s * sr / hop_length)
    max_offset_frames = int(max_offset_s * sr / hop_length)
    
    results = []
    test_offsets = range(-max_offset_frames, max_offset_frames + 1, offset_step_frames)
    
    print(f"[randomized sampling] Testing {len(test_offsets)} different offsets...")
    
    for offset_frames in test_offsets:
        offset_s = float(offset_frames * hop_length / sr)
        
        # Align features by offset
        if offset_frames >= 0:
            # Target starts later - pad target at beginning
            v_chroma = video_chroma
            t_chroma = np.pad(target_chroma, ((0, 0), (offset_frames, 0)), mode='constant')
            v_contrast = video_contrast
            t_contrast = np.pad(target_contrast, ((0, 0), (offset_frames, 0)), mode='constant')
            v_mfcc = video_mfcc
            t_mfcc = np.pad(target_mfcc, ((0, 0), (offset_frames, 0)), mode='constant')
            v_onset = video_onset
            t_onset = np.pad(target_onset, (offset_frames, 0), mode='constant')
        else:
            # Target starts earlier - trim target from beginning
            trim_frames = abs(offset_frames)
            v_chroma = video_chroma
            t_chroma = target_chroma[:, trim_frames:]
            v_contrast = video_contrast
            t_contrast = target_contrast[:, trim_frames:]
            v_mfcc = video_mfcc
            t_mfcc = target_mfcc[:, trim_frames:]
            v_onset = video_onset
            t_onset = target_onset[trim_frames:]
        
        # Match lengths
        min_len = min(v_chroma.shape[1], t_chroma.shape[1])
        v_chroma = v_chroma[:, :min_len]
        t_chroma = t_chroma[:, :min_len]
        v_contrast = v_contrast[:, :min_len]
        t_contrast = t_contrast[:, :min_len]
        v_mfcc = v_mfcc[:, :min_len]
        t_mfcc = t_mfcc[:, :min_len]
        v_onset = v_onset[:min_len]
        t_onset = t_onset[:min_len]
        
        # Compute similarity scores for each feature
        # Chromagram correlation (harmonic similarity)
        chroma_corr = np.corrcoef(v_chroma.flatten(), t_chroma.flatten())[0, 1]
        
        # Spectral contrast correlation (timbral similarity)
        contrast_corr = np.corrcoef(v_contrast.flatten(), t_contrast.flatten())[0, 1]
        
        # MFCC correlation (timbral similarity)
        mfcc_corr = np.corrcoef(v_mfcc.flatten(), t_mfcc.flatten())[0, 1]
        
        # Onset envelope correlation (rhythmic similarity)
        onset_corr = np.corrcoef(v_onset, t_onset)[0, 1]
        
        # Combined score (weighted average)
        combined_score = (
            0.35 * chroma_corr +      # Harmonic content (melody/chords)
            0.25 * contrast_corr +     # Timbre
            0.20 * mfcc_corr +         # Timbre detail
            0.20 * onset_corr          # Rhythm
        )
        
        results.append({
            'offset_s': offset_s,
            'chroma_corr': float(chroma_corr),
            'contrast_corr': float(contrast_corr),
            'mfcc_corr': float(mfcc_corr),
            'onset_corr': float(onset_corr),
            'combined_score': float(combined_score)
        })
    
    return results

def compute_consensus_offset(sync_points: list) -> Tuple[float, str, str]:
    """Compute final offset from multiple sync points using robust consensus.
    ONLY uses high-confidence points. Rejects inconsistent data.
    Returns (final_offset_s, method_used, quality_assessment).
    """
    if not sync_points:
        return 0.0, 'none', 'poor'
    
    # ONLY use high confidence points - reject medium/low
    high_conf_points = [sp for sp in sync_points if sp.confidence == 'high']
    
    if len(high_conf_points) < 2:
        # Not enough reliable data
        print(f"[WARNING] Only {len(high_conf_points)} high-confidence sync points found. Need at least 2.")
        return 0.0, 'insufficient_confidence', 'poor'
    
    offsets = np.array([sp.offset_s for sp in high_conf_points])
    correlations = np.array([sp.correlation for sp in high_conf_points])
    
    # Check consistency - all offsets should be very close
    offset_std = float(np.std(offsets))
    offset_range = float(np.max(offsets) - np.min(offsets))
    
    print(f"[CONSENSUS] High-confidence offsets: {[f'{o:+.3f}' for o in offsets]}")
    print(f"[CONSENSUS] Offset std dev: {offset_std:.3f}s, range: {offset_range:.3f}s")
    
    # If offsets vary by more than 0.5 seconds, something is wrong
    if offset_range > 0.5:
        print(f"[WARNING] High-confidence offsets are inconsistent (range={offset_range:.3f}s > 0.5s)")
        print("[WARNING] This suggests beat detection failed or tracks are not the same song.")
        return 0.0, 'inconsistent_offsets', 'poor'
    
    # Use median for robustness
    final_offset = float(np.median(offsets))
    method = 'median_high_confidence'
    
    # Assess quality based on consistency
    avg_correlation = float(np.mean(correlations))
    
    if offset_std < 0.1 and avg_correlation > 0.8:
        quality = 'excellent'
    elif offset_std < 0.2 and avg_correlation > 0.7:
        quality = 'ok'
    elif offset_std < 0.3:
        quality = 'fair'
    else:
        quality = 'poor'
    
    return final_offset, method, quality

def apply_offset(y: np.ndarray, sr: int, offset_s: float) -> np.ndarray:
    """Apply offset by padding (offset>0) or trimming (offset<0)."""
    if abs(offset_s) < 1e-6:
        return y
    offset_samples = int(round(offset_s * sr))
    if offset_samples > 0:
        return np.concatenate([np.zeros(offset_samples, dtype=y.dtype), y], axis=0)
    else:
        return y[abs(offset_samples):]

def trim_or_pad_to_duration(y: np.ndarray, sr: int, duration_s: float) -> np.ndarray:
    target_length_samples = int(round(duration_s * sr))
    current_length_samples = len(y)
    if current_length_samples == target_length_samples:
        return y
    if current_length_samples > target_length_samples:
        return y[:target_length_samples]
    padding_samples = target_length_samples - current_length_samples
    return np.concatenate([y, np.zeros(padding_samples, dtype=y.dtype)], axis=0)

def export_video_with_audio(video_path: str, audio_waveform: np.ndarray, sr: int, out_path: str) -> None:
    """Replace audio track in video using moviepy by writing temp wav and setting new audio."""
    video_clip = mpe.VideoFileClip(video_path)
    # Use local temp directory instead of AppData
    temp_dir = _get_local_temp_dir(out_path)
    temporary_wav_path = os.path.join(temp_dir, f"_temp_audio_{os.getpid()}.wav")
    temporary_aac_path = os.path.join(temp_dir, f"_temp_aac_{os.getpid()}.m4a")
    
    try:
        sf.write(temporary_wav_path, audio_waveform, sr)
        new_audio_clip = mpe.AudioFileClip(temporary_wav_path)
        
        # Try set_audio first (MoviePy v1.x), fallback to with_audio (MoviePy v2.x)
        try:
            output_video_clip = video_clip.set_audio(new_audio_clip)
        except AttributeError:
            output_video_clip = video_clip.with_audio(new_audio_clip)
        
        # Use libx264 + aac defaults
        output_video_clip.write_videofile(
            out_path,
            audio_codec="aac",
            codec="libx264",
            temp_audiofile=temporary_aac_path,
            remove_temp=True,
            logger=None,
        )
        output_video_clip.close()
        new_audio_clip.close()
    finally:
        video_clip.close()
        # Clean up temp files
        for temp_file in [temporary_wav_path, temporary_aac_path]:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass

def search_sync_offset(
    video_path: str,
    target_audio_path: str,
    sr: int = 22050,
    hop_length: int = 512,
    max_seek_s: float = 10.0,
):
    """Search for best sync offset without exporting. Returns SyncResult with candidates."""
    # Load sources
    print(f"[LOAD] Video: {video_path}")
    video_audio_waveform, video_audio_sample_rate, video_duration_seconds = load_audio_from_video(video_path, sr)
    print(f"[LOAD] Target audio/video: {target_audio_path}")
    target_audio_waveform, target_audio_sample_rate, target_duration_seconds = load_audio_from_any(target_audio_path, sr)

    # randomized sampling offset search with similarity scoring
    print("\n[ANALYZE] Performing offset search...")
    search_results = randomized_sampling_offset_search(
        video_audio_waveform,
        target_audio_waveform,
        sr, hop_length,
        max_offset_s=max_seek_s,
        step_s=0.1
    )
    
    # selection: prioritize chroma (harmonic content) for music matching
    # Sort by chroma correlation first (most important for melody/harmony matching)
    sorted_by_chroma = sorted(search_results, key=lambda x: x['chroma_corr'], reverse=True)
    sorted_by_combined = sorted(search_results, key=lambda x: x['combined_score'], reverse=True)
    
    # Find best chroma match
    best_chroma = sorted_by_chroma[0]
    best_combined = sorted_by_combined[0]
    
    print("\n[TOP CANDIDATES BY CHROMA] Best 5 offsets by harmonic similarity:")
    for i, result in enumerate(sorted_by_chroma[:5], 1):
        print(f"  #{i}: offset={result['offset_s']:+.2f}s, chroma={result['chroma_corr']:.3f}, "
              f"onset={result['onset_corr']:.3f}, mfcc={result['mfcc_corr']:.3f}, combined={result['combined_score']:.3f}")
    
    print("\n[TOP CANDIDATES BY COMBINED] Best 5 offsets by combined score:")
    for i, result in enumerate(sorted_by_combined[:5], 1):
        print(f"  #{i}: offset={result['offset_s']:+.2f}s, combined={result['combined_score']:.3f}, "
              f"chroma={result['chroma_corr']:.3f}, onset={result['onset_corr']:.3f}")
    
    # Smart decision: Balance chroma (melody) with onset (rhythm)
    # Check if top chroma is significantly better than 2nd place
    chroma_gap = sorted_by_chroma[0]['chroma_corr'] - sorted_by_chroma[1]['chroma_corr'] if len(sorted_by_chroma) > 1 else 0
    
    # Check if best chroma is in a different offset range than best combined (indicates intro/outro difference)
    offset_difference = abs(best_chroma['offset_s'] - best_combined['offset_s'])
    
    # Get onset scores for comparison
    best_chroma_onset = best_chroma['onset_corr']
    best_combined_onset = best_combined['onset_corr']
    
    # Decision criteria - prefer combined unless chroma is MUCH better
    use_chroma = False
    
    # Criterion 1: Chroma is exceptional (>0.75) AND onset isn't terrible (>0.0)
    if best_chroma['chroma_corr'] > 0.75 and best_chroma_onset > 0.0:
        use_chroma = True
        reason = f"exceptional chroma ({best_chroma['chroma_corr']:.3f})"
    
    # Criterion 2: Combined has terrible onset (<0.2) but chroma has good onset AND much better chroma
    # This catches cases where combined picks wrong section
    elif best_combined_onset < 0.2 and best_chroma_onset > 0.5 and best_chroma['chroma_corr'] > best_combined['chroma_corr'] * 1.3:
        use_chroma = True
        reason = f"combined has poor onset ({best_combined_onset:.3f}), chroma has better rhythm"
    
    # Criterion 3: Combined score is very poor AND chroma is much better AND large offset difference
    # This handles intro/outro cases where combined completely fails
    elif best_combined['combined_score'] < 0.25 and best_chroma['chroma_corr'] > 0.6 and offset_difference > 15.0:
        use_chroma = True
        reason = f"combined score very poor, chroma peak with large offset difference ({offset_difference:.1f}s)"
    
    if use_chroma:
        # Use chroma-based offset
        final_offset_s = best_chroma['offset_s']
        best_score = best_chroma['chroma_corr']
        offset_method = 'chroma_priority'
        print(f"\n[DECISION] Using CHROMA-based offset ({reason})")
        
        if best_chroma['chroma_corr'] > 0.7:
            sync_quality = 'excellent'
        elif best_chroma['chroma_corr'] > 0.5:
            sync_quality = 'ok'
        elif best_chroma['chroma_corr'] > 0.4:
            sync_quality = 'fair'
        else:
            sync_quality = 'poor'
    else:
        # Use combined score
        final_offset_s = best_combined['offset_s']
        best_score = best_combined['combined_score']
        offset_method = 'multi_feature_combined'
        print(f"\n[DECISION] Using COMBINED score (no clear chroma advantage)")
        
        if best_score > 0.6:
            sync_quality = 'ok'
        elif best_score > 0.4:
            sync_quality = 'fair'
        else:
            sync_quality = 'poor'
    
    print(f"\n[RESULT] Selected offset: {final_offset_s:+.3f}s (method={offset_method}, quality={sync_quality}, score={best_score:.3f})")
    
    # Convert top results to sync_points format for JSON report
    # Use sorted_by_combined for report (shows all scoring methods)
    sync_points = [
        {
            'offset_s': r['offset_s'],
            'combined_score': r['combined_score'],
            'chroma_correlation': r['chroma_corr'],
            'contrast_correlation': r['contrast_corr'],
            'mfcc_correlation': r['mfcc_corr'],
            'onset_correlation': r['onset_corr']
        }
        for r in sorted_by_combined[:10]  # Top 10 for report
    ]

    # Return result  
    print(f"\n[SEARCH COMPLETE] Found best offset: {final_offset_s:+.3f}s")
    print("[INFO] Use 'Export Video' button to create output with chosen offset")

    synchronization_result = SyncResult(
        video_path=os.path.abspath(video_path),
        audio_path=os.path.abspath(target_audio_path),
        output_path="",  # No output yet
        video_duration_s=video_duration_seconds,
        target_audio_duration_s=target_duration_seconds,
        final_offset_s=final_offset_s,
        sync_points=sync_points,  # Top 10 candidates with all scores
        offset_method=offset_method,
        sync_quality=sync_quality,
        notes=f"Multi-feature randomized-sampling search: tested {len(search_results)} offsets. "
              f"Features: chromagram (harmonic), spectral contrast (timbre), MFCC (timbre detail), onset (rhythm). "
              f"Best score: {best_score:.3f}. No export performed - use Export button."
    )

    return synchronization_result

def sync_audio_to_video(
    video_path: str,
    target_audio_path: str,
    output_path: str,
    report_path: Optional[str] = None,
    sr: int = 22050,
    hop_length: int = 512,
    max_seek_s: float = 10.0,
):
    """Full sync with export - calls search_sync_offset then exports."""
    # Do search
    result = search_sync_offset(video_path, target_audio_path, sr, hop_length, max_seek_s)
    
    # Load audio again for export
    video_audio_waveform, _, video_duration_seconds = load_audio_from_video(video_path, sr)
    target_audio_waveform, _, _ = load_audio_from_any(target_audio_path, sr)
    
    # Apply offset and export
    print("[PROCESS] Applying offset and matching duration…")
    target_audio_time_aligned_waveform = apply_offset(target_audio_waveform, sr, result.final_offset_s)
    target_audio_final_waveform = trim_or_pad_to_duration(target_audio_time_aligned_waveform, sr, video_duration_seconds)

    print(f"[EXPORT] Writing video with replaced audio -> {output_path}")
    export_video_with_audio(video_path, target_audio_final_waveform, sr, output_path)
    print("[DONE] Export complete.")
    
    # Update result with output path
    result.output_path = os.path.abspath(output_path)

    if report_path:
        try:
            with open(report_path, "w", encoding="utf-8") as report_file_handle:
                json.dump(asdict(result), report_file_handle, indent=2)
            print(f"[REPORT] Saved sync metrics -> {report_path}")
        except Exception as report_save_exception:
            print(f"[REPORT] Failed to save report: {report_save_exception}")

    return result

def _positive_float(val: str) -> float:
    f = float(val)
    if f <= 0:
        raise argparse.ArgumentTypeError("Value must be > 0")
    return f

def cli_main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sync a target audio track to a video's timing using multi-point waveform analysis.",
    )
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument("--audio", required=True, help="Path to target audio OR video (audio will be extracted) to sync")
    parser.add_argument("--out", required=False, default=None, help="Path to output video (default: <video>_synced.mp4)")
    parser.add_argument("--report", required=False, default=None, help="Optional JSON report path for sync metrics")
    parser.add_argument("--sr", type=_positive_float, default=22050, help="Processing sample rate (Hz), default 22050")
    parser.add_argument("--hop", type=int, default=512, help="Onset/beat hop_length, default 512")
    parser.add_argument("--max-seek", type=float, default=10.0, help="Max absolute offset to search (seconds), default 10.0")

    args = parser.parse_args(argv)

    video_path = args.video
    audio_path = args.audio
    if not os.path.isfile(video_path):
        print(f"[ERROR] Video not found: {video_path}")
        sys.exit(2)
    if not os.path.isfile(audio_path):
        print(f"[ERROR] Audio not found: {audio_path}")
        sys.exit(2)

    out_path = args.out
    if not out_path:
        base, _ = os.path.splitext(video_path)
        out_path = base + "_synced.mp4"

    try:
        sync_audio_to_video(
            video_path=video_path,
            target_audio_path=audio_path,
            output_path=out_path,
            report_path=args.report,
            sr=int(args.sr),
            hop_length=int(args.hop),
            max_seek_s=float(args.max_seek),
        )
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)

if __name__ == '__main__':
    gui_main()
