"""
VIDEO EDITOR WORD BASED RATING SYSTEM
- Review a video, mark good/bad parts by painting the timeline (left/right click)
- Loop original playback or preview what the output video will look like if skip over 'bad' regions

TRANSCRIPTION
- Analyze audio using Vosk to auto-flag filler words ("uh", "um", "you know", "basically") as 'bad' regions
- load transcriptions from .SRT , or from copied transcription text 
- transcribed words are shown below , like descrypt enables editing of the video by cutting words , right click words to remove , click to approve

CONTROLS
- middle mouse click to jump to a place on the timeline
- left click = mark good section , right click = mark bad section
- spacebar will play or stop video playback
- consider a cumulative rating for sections with a quick input like up or down arrow , these rough indicators could be useful in finding places to cut based on a threshold . as well could indicate a highlight or very important moment 
"""

import os
import sys
import tempfile
import subprocess
import re
import traceback
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QSlider, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QScrollArea, QWidget, QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from vosk import Model, KaldiRecognizer
import wave
import json
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtWidgets import QFileDialog
import datetime, shutil

class TimelineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(32)
        self.setMaximumHeight(32)
        self.setMouseTracking(True)
        self.regions = []  # List of (start_frac, end_frac, 'good'|'bad')
        self.dragging = False
        self.drag_type = None
        self.drag_start = None
        self.current_pos = 0.0
        self.duration = 1.0

    def set_duration(self, duration):
        self.duration = max(duration, 1e-6)
        self.update()

    def set_position(self, pos):
        self.current_pos = pos / self.duration if self.duration else 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(40, 40, 40))
        for start, end, typ in self.regions:
            x1 = int(start * w)
            x2 = int(end * w)
            color = QColor(60, 180, 60) if typ == 'good' else QColor(60, 60, 60)
            painter.fillRect(x1, 0, x2 - x1, h, color)
        pos_x = int(self.current_pos * w)
        painter.setPen(QColor(220, 220, 40))
        painter.drawLine(pos_x, 0, pos_x, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_type = 'good'
        elif event.button() == Qt.RightButton:
            self.drag_type = 'bad'
        else:
            return
        self.dragging = True
        self.drag_start = event.x() / self.width()
        self.drag_end = self.drag_start
        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.drag_end = max(0.0, min(1.0, event.x() / self.width()))
            self.update()

    def mouseReleaseEvent(self, event):
        if self.dragging:
            start = min(self.drag_start, self.drag_end)
            end = max(self.drag_start, self.drag_end)
            new_regions = []
            for s, e, t in self.regions:
                if t == self.drag_type and not (e > start and s < end):
                    new_regions.append((s, e, t))
                elif t != self.drag_type:
                    new_regions.append((s, e, t))
            if end - start > 0.01:
                new_regions.append((start, end, self.drag_type))
            self.regions = self._merge_regions(new_regions)
            self.dragging = False
            self.drag_type = None
            self.update()

    def _merge_regions(self, regions):
        regions = sorted(regions, key=lambda r: (r[2], r[0], r[1]))
        merged = []
        for r in regions:
            if not merged or merged[-1][2] != r[2] or merged[-1][1] < r[0] - 1e-4:
                merged.append(list(r))
            else:
                merged[-1][1] = max(merged[-1][1], r[1])
        return [tuple(x) for x in merged]

    def get_good_regions(self):
        return [(s * self.duration, e * self.duration) for s, e, t in self.regions if t == 'good']

    def get_bad_regions(self):
        return [(s * self.duration, e * self.duration) for s, e, t in self.regions if t == 'bad']

    def clear(self):
        self.regions = []
        self.update()


class WordsTimelineWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.inner = QWidget()
        self.setWidget(self.inner)
        self.vlayout = QVBoxLayout(self.inner)
        self.inner.setLayout(self.vlayout)
        self.inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.words = []  # list of dicts: {word, start, end, row, status}
        self.duration = 1.0
        self.rows = 1
        self.hovered_word = None
        self.word_height = 18
        self.row_gap = 2
        self.srt_blocks = None

    def set_words(self, words, duration, srt_blocks=None):
        self.duration = max(duration, 1e-6)
        self.words = words
        self.srt_blocks = srt_blocks
        # Clear layout
        while self.vlayout.count():
            item = self.vlayout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if srt_blocks:
            for block in srt_blocks:
                self.vlayout.addWidget(SRTBlockTimeline(block, self.duration, self))
        else:
            # fallback: all words in one row
            self.vlayout.addWidget(SRTBlockTimeline({'words': words, 'start': 0, 'end': self.duration}, self.duration, self))
        self.inner.setMinimumHeight(len(srt_blocks or [1]) * (self.word_height + self.row_gap + 8))
        self.update()


class SRTBlockTimeline(QWidget):
    wordStatusChanged = pyqtSignal(dict)
    jumpToWord = pyqtSignal(dict)

    def __init__(self, block, video_duration, parent=None):
        super().__init__(parent)
        self.block = block
        self.words = block['words']
        self.start = block['start']
        self.end = block['end']
        self.word_height = 22
        self.row_gap = 2
        self.setMinimumHeight(self.word_height + self.row_gap + 8)
        # self.setMaximumHeight(self.word_height + self.row_gap + 8)  # Allow block to expand
        self.setMouseTracking(True)
        self.hovered_word = None
        self.wordStatusChanged.connect(self._relay_word_status_changed)
        self.jumpToWord.connect(self._relay_jump_to_word)

    def _relay_word_status_changed(self, word):
        # Bubble up to main window
        parent = self.parent()
        while parent and not hasattr(parent, 'on_word_status_changed'):
            parent = parent.parent()
        if parent:
            parent.on_word_status_changed(word)

    def _relay_jump_to_word(self, word):
        parent = self.parent()
        while parent and not hasattr(parent, 'jump_to_word'):
            parent = parent.parent()
        if parent:
            parent.jump_to_word(word)

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(28, 28, 28))
        block_dur = max(self.end - self.start, 1e-6)
        for word in self.words:
            # Localize word position to block
            frac_start = (word['start'] - self.start) / block_dur
            frac_end = (word['end'] - self.start) / block_dur
            x1 = int(frac_start * w)
            x2 = int(frac_end * w)
            color = QColor(90, 90, 90)
            if word.get('status') == 'approved':
                color = QColor(60, 180, 60)
            elif word.get('status') == 'removed':
                color = QColor(200, 60, 60)
            elif self.hovered_word == word:
                color = QColor(120, 120, 180)
            painter.fillRect(x1, 4, max(18, x2 - x1), self.word_height, color)
            painter.setPen(QColor(255,255,255))
            painter.drawText(x1+3, 4+self.word_height-4, word['word'])

    def mouseMoveEvent(self, event):
        self.hovered_word = self._word_at(event.pos())
        self.update()

    def leaveEvent(self, event):
        self.hovered_word = None
        self.update()

    def mousePressEvent(self, event):
        word = self._word_at(event.pos())
        if not word:
            return
        if event.button() == Qt.LeftButton:
            word['status'] = 'approved'
            self.wordStatusChanged.emit(word)
        elif event.button() == Qt.RightButton:
            word['status'] = 'removed'
            self.wordStatusChanged.emit(word)
        elif event.button() == Qt.MiddleButton:
            self.jumpToWord.emit(word)
        self.update()

    def _word_at(self, pos):
        w = self.width()
        block_dur = max(self.end - self.start, 1e-6)
        for word in self.words:
            frac_start = (word['start'] - self.start) / block_dur
            frac_end = (word['end'] - self.start) / block_dur
            x1 = int(frac_start * w)
            x2 = int(frac_end * w)
            rect = (x1, 4, max(18, x2 - x1), self.word_height)
            if rect[0] <= pos.x() <= rect[0]+rect[2] and rect[1] <= pos.y() <= rect[1]+rect[3]:
                return word
        return None


class VideoEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Editor Filler Flagger")
        self.setGeometry(100, 100, 1000, 900)
        self.video_path = None
        self.duration = 0
        self.position = 0
        self.filter_words = ["uh", "um", "you know", "basically"]

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)
        self.central.setStyleSheet("background-color: #111;")

        # --- Video and timelines splitter ---
        self.splitter = QSplitter(Qt.Vertical)
        self.layout.addWidget(self.splitter, stretch=1)

        # Video playback and timelines splitter (ONLY ONCE)
        self.player = QMediaPlayer(self)
        self.video_widget = QVideoWidget(self)
        self.splitter.addWidget(self.video_widget)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)

        self.timeline = TimelineWidget(self)
        self.splitter.addWidget(self.timeline)
        self.words_timeline = WordsTimelineWidget(self)
        self.splitter.addWidget(self.words_timeline)
        self.splitter.setSizes([400, 32, 300])

        # --- Filter words UI ---
        filter_row = QHBoxLayout()
        self.filter_label = QLabel("Auto-filter words:")
        self.filter_label.setStyleSheet("color: #bbb; font-size: 13px;")
        filter_row.addWidget(self.filter_label)
        self.filter_list = QLabel(", ".join(self.filter_words))
        self.filter_list.setStyleSheet("color: #7fd; font-size: 13px;")
        filter_row.addWidget(self.filter_list)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Add new word...")
        self.filter_input.setStyleSheet("background: #222; color: #fff; border: 1px solid #444; padding: 2px 6px;")
        filter_row.addWidget(self.filter_input)
        self.add_filter_btn = QPushButton("Add")
        self.add_filter_btn.clicked.connect(self.add_filter_word)
        self.add_filter_btn.setStyleSheet("background-color: #292947; color: #b7b7ff; border-radius: 6px; padding: 4px 12px;")
        filter_row.addWidget(self.add_filter_btn)
        filter_row.addStretch(1)
        self.layout.addLayout(filter_row)

        self.open_btn = QPushButton("Open Video")
        self.open_btn.clicked.connect(self.open_video)
        self.open_btn.setStyleSheet("background-color: #1a2b21; color: #7fd; border-radius: 6px; padding: 6px 18px; font-weight: bold;")
        self.layout.addWidget(self.open_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #b7b7ff; font-size: 13px;")
        self.layout.addWidget(self.status_label)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("Play (Loop)")
        self.play_btn.clicked.connect(self.play_loop)
        self.play_btn.setStyleSheet("background-color: #223b3b; color: #7fd; border-radius: 6px; padding: 6px 18px;")
        self.play_skip_btn = QPushButton("Play (Skip Bad)")
        self.play_skip_btn.clicked.connect(self.play_skip_bad)
        self.play_skip_btn.setStyleSheet("background-color: #23234b; color: #b7b7ff; border-radius: 6px; padding: 6px 18px;")
        self.analyze_btn = QPushButton("Analyze Voice")
        self.analyze_btn.clicked.connect(self.analyze_voice)
        self.analyze_btn.setStyleSheet("background-color: #2c1a2b; color: #e7a7ff; border-radius: 6px; padding: 6px 18px;")
        self.save_btn = QPushButton("Save Progress")
        self.save_btn.clicked.connect(self.save_progress)
        self.save_btn.setStyleSheet("background-color: #1a2b21; color: #7fd; border-radius: 6px; padding: 6px 18px; font-weight: bold;")
        self.load_btn = QPushButton("Load Progress")
        self.load_btn.clicked.connect(self.load_progress)
        self.load_btn.setStyleSheet("background-color: #292947; color: #b7b7ff; border-radius: 6px; padding: 6px 18px;")
        self.export_btn = QPushButton("Export Edited Video")
        self.export_btn.clicked.connect(self.export_edited_video)
        self.export_btn.setStyleSheet("background-color: #2c1a2b; color: #e7a7ff; border-radius: 6px; padding: 6px 18px; font-weight: bold;")
        self.transcript_btn = QPushButton("Load Transcript")
        self.transcript_btn.clicked.connect(self.load_transcript)
        self.transcript_btn.setStyleSheet("background-color: #23234b; color: #b7b7ff; border-radius: 6px; padding: 6px 18px;")
        self.srt_btn = QPushButton("Load SRT Transcript")
        self.srt_btn.clicked.connect(self.load_srt_transcript)
        self.srt_btn.setStyleSheet("background-color: #23234b; color: #e7a7ff; border-radius: 6px; padding: 6px 18px;")
        controls.addWidget(self.play_btn)
        controls.addWidget(self.play_skip_btn)
        controls.addWidget(self.analyze_btn)
        controls.addWidget(self.save_btn)
        controls.addWidget(self.load_btn)
        controls.addWidget(self.export_btn)
        controls.addWidget(self.transcript_btn)
        controls.addWidget(self.srt_btn)
        self.layout.addLayout(controls)

        self.skip_mode = False
        self.skip_regions = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_skip)
        self.words = []
        self.setFocusPolicy(Qt.StrongFocus)

    def add_filter_word(self):
        word = self.filter_input.text().strip()
        if word and word not in self.filter_words:
            self.filter_words.append(word)
            self.filter_list.setText(", ".join(self.filter_words))
            self.filter_input.clear()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            if self.player:
                if self.player.state() == QMediaPlayer.PlayingState:
                    self.player.pause()
                else:
                    self.player.play()

    def on_word_status_changed(self, word):
        # Update main timeline regions for this word
        start, end = word['start'], word['end']
        frac_start = start / self.timeline.duration
        frac_end = end / self.timeline.duration
        # Remove any existing region for this word
        self.timeline.regions = [r for r in self.timeline.regions if not (abs(r[0]-frac_start)<1e-4 and abs(r[1]-frac_end)<1e-4)]
        if word.get('status') == 'approved':
            self.timeline.regions.append((frac_start, frac_end, 'good'))
        elif word.get('status') == 'removed':
            self.timeline.regions.append((frac_start, frac_end, 'bad'))
        self.timeline.regions = self.timeline._merge_regions(self.timeline.regions)
        self.timeline.update()

    def jump_to_word(self, word):
        if self.player:
            self.player.setPosition(int(word['start'] * 1000))

    def save_progress(self):
        data = {
            'video_path': self.video_path,
            'timeline': self.timeline.regions,
            'words': self.words,
            'filter_words': self.filter_words,
        }
        file, _ = QFileDialog.getSaveFileName(self, "Save Progress", "progress.json", "JSON Files (*.json)")
        if file:
            try:
                with open(file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                self.status_label.setText(f"Progress saved to {os.path.basename(file)}")
            except Exception as e:
                self.status_label.setText(f"Error saving: {e}")

    def load_progress(self):
        file, _ = QFileDialog.getOpenFileName(self, "Load Progress", "", "JSON Files (*.json)")
        if file:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.video_path = data.get('video_path')
                self.timeline.regions = data.get('timeline', [])
                self.timeline.update()
                self.words = data.get('words', [])
                self.words_timeline.set_words(self.words, self.timeline.duration)
                self.filter_words = data.get('filter_words', ["uh", "um", "you know", "basically"])
                self.filter_list.setText(", ".join(self.filter_words))
                # Load video if path exists
                if self.video_path and os.path.exists(self.video_path):
                    self.open_loaded_video(self.video_path)
                self.status_label.setText(f"Progress loaded from {os.path.basename(file)}")
            except Exception as e:
                self.status_label.setText(f"Error loading: {e}")

    def open_loaded_video(self, file):
        # Like open_video, but skip file dialog and don't clear markers
        if hasattr(self, 'temp_proxy') and self.temp_proxy and os.path.exists(self.temp_proxy):
            try:
                os.remove(self.temp_proxy)
            except Exception:
                pass
        self.video_path = file
        base = os.path.splitext(os.path.basename(file))[0]
        temp_dir = tempfile.gettempdir()
        proxy_path = os.path.join(temp_dir, base + "_proxy.mpg")
        self.status_label.setText("Converting for playback...")
        QApplication.processEvents()
        if not os.path.exists(proxy_path) or os.path.getsize(proxy_path) == 0:
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", file,
                "-c:v", "mpeg1video", "-c:a", "mp2",
                "-b:v", "2M", "-b:a", "192k",
                "-vf", "scale=960:720:force_original_aspect_ratio=decrease",
                proxy_path
            ]
            try:
                subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except Exception as e:
                self.status_label.setText(f"ffmpeg failed: {e}")
                return
        self.temp_proxy = proxy_path
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(proxy_path)))
        self.player.setPosition(0)
        self.player.pause()
        self.status_label.setText(f"Loaded: {os.path.basename(file)} (proxy)")

    def export_edited_video(self):
        if not self.video_path or not os.path.exists(self.video_path):
            self.status_label.setText("No original video loaded!")
            return
        bads = [(r[0], r[1]) for r in self.timeline.regions if r[2] == 'bad']
        # Merge and sort bads
        bads = sorted(bads, key=lambda x: x[0])
        # Compute keep regions (all not-bad)
        keep = []
        last = 0.0
        for b in bads:
            if b[0] > last:
                keep.append((last, b[0]))
            last = max(last, b[1])
        duration = self.timeline.duration
        if last < 1.0:
            keep.append((last, 1.0))
        # If no bads, just copy
        if not bads or keep == [(0.0, 1.0)]:
            out_path = self._export_filename()
            shutil.copy2(self.video_path, out_path)
            self.status_label.setText(f"Exported (no edits): {os.path.basename(out_path)}")
            return
        # Get actual times
        keep_times = [(float(start)*duration, float(end)*duration) for start, end in keep if end > start]
        if not keep_times:
            self.status_label.setText("Nothing to export!")
            return
        # Export each segment
        temp_dir = tempfile.gettempdir()
        segment_files = []
        for idx, (start, end) in enumerate(keep_times):
            seg_path = os.path.join(temp_dir, f"segment_{idx}.mp4")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", self.video_path,
                "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
                "-c", "copy", seg_path
            ]
            result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not os.path.exists(seg_path) or os.path.getsize(seg_path) == 0:
                self.status_label.setText(f"ffmpeg segment failed at {start:.2f}-{end:.2f}")
                # Clean up
                for f in segment_files:
                    try: os.remove(f)
                    except: pass
                return
            segment_files.append(seg_path)
        # Create concat file
        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for seg in segment_files:
                seg_fixed = seg.replace('\\', '/')
                f.write(f"file '{seg_fixed}'\n")
        out_path = self._export_filename()
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
            "-c", "copy", out_path
        ]
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Clean up segments
        for f in segment_files:
            try: os.remove(f)
            except: pass
        try: os.remove(concat_list_path)
        except: pass
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            self.status_label.setText(f"Exported: {os.path.basename(out_path)}")
        else:
            self.status_label.setText("Export failed!")

    def _export_filename(self):
        base, ext = os.path.splitext(os.path.basename(self.video_path))
        dt = datetime.datetime.now().strftime("_%Y%m%d")
        out_name = f"{base}{dt}{ext}"
        out_path = os.path.join(os.path.dirname(self.video_path), out_name)
        return out_path

    def open_video(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file:
            # Clean up previous temp file if exists
            if hasattr(self, 'temp_proxy') and self.temp_proxy and os.path.exists(self.temp_proxy):
                try:
                    os.remove(self.temp_proxy)
                except Exception:
                    pass
            self.video_path = file
            # Create temp MPEG-1 proxy for playback
            base = os.path.splitext(os.path.basename(file))[0]
            temp_dir = tempfile.gettempdir()
            proxy_path = os.path.join(temp_dir, base + "_proxy.mpg")
            self.status_label.setText("Converting for playback...")
            QApplication.processEvents()
            if not os.path.exists(proxy_path) or os.path.getsize(proxy_path) == 0:
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", file,
                    "-c:v", "mpeg1video", "-c:a", "mp2",
                    "-b:v", "2M", "-b:a", "192k",
                    "-vf", "scale=960:720:force_original_aspect_ratio=decrease",
                    proxy_path
                ]
                try:
                    subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                except Exception as e:
                    self.status_label.setText(f"ffmpeg failed: {e}")
                    return
            self.temp_proxy = proxy_path
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(proxy_path)))
            self.player.setPosition(0)
            self.player.pause()
            self.status_label.setText(f"Loaded: {os.path.basename(file)} (proxy)")
            self.timeline.regions = []
            self.timeline.update()
            self.words = []
            self.words_timeline.set_words([], 1.0)
            self.filter_words = ["uh", "um", "you know", "basically"]
            self.filter_list.setText(", ".join(self.filter_words))
    def play_loop(self):
        if self.player:
            self.skip_mode = False
            self.player.setPosition(0)
            self.player.play()
            self.timer.stop()

    def play_skip_bad(self):
        if self.player:
            self.skip_mode = True
            self.player.setPosition(0)
            self.player.play()
            self.timer.start(100)

    def check_skip(self):
        if self.player:
            pos = self.player.position() / 1000.0
            for s, e in self.timeline.get_bad_regions():
                if s <= pos < e:
                    self.skip_to_next_good()
                    break

    def skip_to_next_good(self):
        good = sorted(self.timeline.get_good_regions())
        for s, e in good:
            if e > self.position:
                self.player.setPosition(int(s * 1000))
                return
        self.player.stop()
        self.timer.stop()

    def analyze_voice(self):
        if not self.video_path:
            self.status_label.setText("No video loaded!")
            print("[VOSK] No video loaded!")
            return
        self.status_label.setText("Extracting audio...")
        QApplication.processEvents()
        wav_path = self.extract_audio_wav()
        print(f"[VOSK] Extracted wav path: {wav_path}")
        if not wav_path or not os.path.exists(wav_path):
            self.status_label.setText("Audio extraction failed.")
            print(f"[VOSK] Audio extraction failed: {wav_path}")
            return
        self.status_label.setText("Analyzing audio...")
        QApplication.processEvents()
        words = self.transcribe_words(wav_path)
        if not words:
            self.status_label.setText("No words detected.")
            print("[VOSK] No words detected.")
            self.words = []
            self.words_timeline.set_words([], self.timeline.duration)
            return
        self.words = words
        self.words_timeline.set_words(self.words, self.timeline.duration)
        # Auto-flag filter words as 'bad' on main timeline
        filter_set = set(w.lower() for w in self.filter_words)
        for word in self.words:
            if word['word'].lower() in filter_set:
                word['status'] = 'removed'
                self.on_word_status_changed(word)
        self.words_timeline.update()
        self.status_label.setText(f"Analyzed {len(words)} words.")
        print(f"[VOSK] Analyzed {len(words)} words.")
        # --- Save Vosk transcript as JSON ---
        if self.video_path:
            base = os.path.splitext(os.path.basename(self.video_path))[0]
            out_dir = os.path.dirname(self.video_path)
            vosk_json_path = os.path.join(out_dir, base + ".vosk.json")
            try:
                with open(vosk_json_path, 'w', encoding='utf-8') as f:
                    json.dump(self.words, f, ensure_ascii=False, indent=2)
                print(f"[VOSK] Transcript saved to {vosk_json_path}")
            except Exception as e:
                print(f"[VOSK] Failed to save transcript: {e}")


    def on_position_changed(self, ms):
        self.position = ms / 1000.0
        self.timeline.set_position(self.position)
        if self.skip_mode:
            for s, e in self.timeline.get_bad_regions():
                if s <= self.position < e:
                    self.skip_to_next_good()
                    break

    def on_duration_changed(self, ms):
        self.duration = ms / 1000.0
        self.timeline.set_duration(self.duration)
        self.words_timeline.duration = self.duration
        self.timeline.update()
        self.words_timeline.update()

    def transcribe_words(self, wav_path):
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vosk-model-en-us-0.42-gigaspeech")
        print(f"[VOSK] Model path: {model_path}")
        if not os.path.exists(model_path):
            self.status_label.setText("Vosk model not found!")
            print("[VOSK] Model not found!")
            return []
        try:
            model = Model(model_path)
            print("[VOSK] Model loaded.")
        except Exception as e:
            print(f"[VOSK] Model load failed: {e}")
            traceback.print_exc()
            self.status_label.setText(f"Vosk model load failed: {e}")
            return []
        try:
            wf = wave.open(wav_path, "rb")
            print(f"[VOSK] WAV file opened: nchannels={wf.getnchannels()}, sampwidth={wf.getsampwidth()}, framerate={wf.getframerate()}, nframes={wf.getnframes()}")
        except Exception as e:
            print(f"[VOSK] WAV open failed: {e}")
            traceback.print_exc()
            self.status_label.setText(f"WAV open failed: {e}")
            return []
        rec = KaldiRecognizer(model, 16000)
        words = []
        chunk = 4000
        frame_count = 0
        try:
            while True:
                data = wf.readframes(chunk)
                if len(data) == 0:
                    break
                frame_count += 1
                if rec.AcceptWaveform(data):
                    res = rec.Result()
                    print(f"[VOSK] Chunk {frame_count} result: {res}")
                    res = json.loads(res)
                    if "result" in res:
                        for word in res["result"]:
                            words.append({
                                'word': word["word"],
                                'start': word["start"],
                                'end': word["end"],
                                'status': None
                            })
            res = rec.FinalResult()
            print(f"[VOSK] Final result: {res}")
            res = json.loads(res)
            if "result" in res:
                for word in res["result"]:
                    words.append({
                        'word': word["word"],
                        'start': word["start"],
                        'end': word["end"],
                        'status': None
                    })
            wf.close()
        except Exception as e:
            print(f"[ERROR] Vosk recognition failed: {e}")
            traceback.print_exc()
            self.status_label.setText(f"Vosk error: {e}")
        print(f"[VOSK] Total words: {len(words)}")
        return words

    def extract_audio_wav(self):
        base = os.path.splitext(os.path.basename(self.video_path))[0]
        wav_path = os.path.join(tempfile.gettempdir(), base + "_audio.wav")
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", self.video_path,
            "-ar", "16000", "-ac", "1", "-f", "wav", wav_path
        ]
        try:
            subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return wav_path
        except Exception as e:
            print(f"[ERROR] ffmpeg audio extraction failed: {e}")
            return None

    def load_transcript(self):
        file, _ = QFileDialog.getOpenFileName(self, "Load Transcript", "", "Text Files (*.txt);;JSON Files (*.json)")
        if not file:
            return

        # Try to load as JSON first (for Vosk transcripts)
        if file.lower().endswith('.json'):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Check if this is a Vosk transcript (list of dicts with word/start/end)
                if isinstance(data, list) and all(isinstance(w, dict) and 'word' in w and 'start' in w and 'end' in w for w in data):
                    self.words = data
                    self.words_timeline.set_words(self.words, self.timeline.duration)
                    self.status_label.setText(f"Loaded Vosk transcript: {os.path.basename(file)} ({len(self.words)} words)")
                    return
                else:
                    self.status_label.setText("JSON file format not recognized as Vosk transcript.")
                    return
            except Exception as e:
                self.status_label.setText(f"Error loading JSON transcript: {e}")
                return
        # Otherwise, fallback to legacy text transcript parsing
        with open(file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        # Expect alternating timestamp/text lines (YouTube format)
        transcript = []
        i = 0
        while i < len(lines) - 1:
            ts_line = lines[i]
            text_line = lines[i+1]
            # Parse timestamp
            ts_match = re.match(r'(\d+):(\d+)', ts_line)
            if ts_match:
                m, s = int(ts_match.group(1)), int(ts_match.group(2))
                start = m*60 + s
                words = text_line.split()
                for idx, word in enumerate(words):
                    w_start = start + idx * 0.5  # crude estimate: 0.5s per word
                    w_end = w_start + 0.5
                    transcript.append({'word': word, 'start': w_start, 'end': w_end, 'status': None})
            i += 2
        # Only keep words within video duration
        video_duration = getattr(self, 'duration', 0) or 0
        filtered = [w for w in transcript if w['start'] < video_duration]
        if not filtered:
            self.status_label.setText("No transcript words within video duration or transcript format not recognized.")
            self.words = []
            self.words_timeline.set_words([], self.timeline.duration)
            return
        self.words = filtered
        self.words_timeline.set_words(self.words, self.timeline.duration)
        self.status_label.setText(f"Loaded transcript: {os.path.basename(file)} ({len(self.words)} words in video)")

    def load_srt_transcript(self):
        file, _ = QFileDialog.getOpenFileName(self, "Load SRT Transcript", "", "SRT Files (*.srt)")
        if not file:
            return
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        # Parse SRT blocks
        blocks = re.split(r'\n\s*\n', content)
        srt_blocks = []
        video_duration = getattr(self, 'duration', 0) or 0
        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) >= 3:
                ts_line = lines[1]
                text_line = ' '.join(lines[2:])
                ts_match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})', ts_line)
                if ts_match:
                    sh, sm, ss, sms, eh, em, es, ems = map(int, ts_match.groups())
                    start = sh*3600 + sm*60 + ss + sms/1000.0
                    end = eh*3600 + em*60 + es + ems/1000.0
                    if start >= video_duration:
                        continue
                    end = min(end, video_duration)
                    words = text_line.split()
                    n = len(words)
                    if n > 0 and end > start:
                        dur = (end - start) / n
                        word_objs = []
                        for idx, word in enumerate(words):
                            w_start = start + idx * dur
                            w_end = w_start + dur
                            if w_start < end:
                                word_objs.append({'word': word, 'start': w_start, 'end': w_end, 'status': None})
                        if word_objs:
                            srt_blocks.append({'start': start, 'end': end, 'words': word_objs})
        if not srt_blocks:
            self.status_label.setText("No SRT words within video duration or SRT format not recognized.")
            self.words = []
            self.words_timeline.set_words([], self.timeline.duration, srt_blocks=None)
            return
        # Flatten all words for save/load compatibility
        all_words = [w for block in srt_blocks for w in block['words']]
        self.words = all_words
        self.words_timeline.set_words(self.words, self.timeline.duration, srt_blocks=srt_blocks)
        self.status_label.setText(f"Loaded SRT: {os.path.basename(file)} ({len(self.words)} words in video)")

        file, _ = QFileDialog.getOpenFileName(self, "Load Transcript", "", "Text Files (*.txt)")
        if not file:
            return
        with open(file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        # Expect alternating timestamp/text lines (YouTube format)
        transcript = []
        i = 0
        while i < len(lines) - 1:
            ts_line = lines[i]
            text_line = lines[i+1]
            # Parse timestamp
            ts_match = re.match(r'(\d+):(\d+)', ts_line)
            if ts_match:
                m, s = int(ts_match.group(1)), int(ts_match.group(2))
                start = m*60 + s
                words = text_line.split()
                for idx, word in enumerate(words):
                    w_start = start + idx * 0.5  # crude estimate: 0.5s per word
                    w_end = w_start + 0.5
                    transcript.append({'word': word, 'start': w_start, 'end': w_end, 'status': None})
            i += 2
        if not transcript:
            self.status_label.setText("Transcript format not recognized or empty.")
            return
        self.words = transcript
        self.words_timeline.set_words(self.words, self.timeline.duration)
        self.status_label.setText(f"Loaded transcript: {os.path.basename(file)} ({len(self.words)} words)")

    def find_filler_words(self, wav_path):
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vosk-model-en-us-0.42-gigaspeech")
        if not os.path.exists(model_path):
            self.status_label.setText("Vosk model not found!")
            return []
        model = Model(model_path)
        rec = KaldiRecognizer(model, 16000)
        filler_words = {"uh", "um", "you know", "basically"}
        regions = []
        try:
            wf = wave.open(wav_path, "rb")
            chunk = 4000
            while True:
                data = wf.readframes(chunk)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    if "result" in res:
                        for word in res["result"]:
                            w = word["word"].lower()
                            if w in filler_words:
                                start = max(0, word["start"] - 0.25)
                                end = word["end"] + 0.25
                                regions.append((start, end))
            res = json.loads(rec.FinalResult())
            if "result" in res:
                for word in res["result"]:
                    w = word["word"].lower()
                    if w in filler_words:
                        start = max(0, word["start"] - 0.25)
                        end = word["end"] + 0.25
                        regions.append((start, end))
            wf.close()
        except Exception as e:
            print(f"[ERROR] Vosk recognition failed: {e}")
        return regions

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VideoEditorWindow()
    win.show()
    app.exec_()