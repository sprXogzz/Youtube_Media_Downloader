import sys
import os
import threading
import winreg  # masaüstüne video kaydederken sapıtmasın diye (bende onedriveden patladıgı icin)
import yt_dlp
import imageio_ffmpeg
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QLabel, QRadioButton, 
                             QProgressBar, QComboBox)
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QIcon


APP_NAME = "YouTube Media Downloader by ORŞevik"  
ICON_NAME = "ogiyticon.ico"                 
# ------------------------

def get_true_desktop_path():
    """Windows için oneDrive dan patlamamaları için."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        desktop_path, _ = winreg.QueryValueEx(key, "Desktop")
        winreg.CloseKey(key)
        # %USERPROFILE% gibi ortam değişkenleri varsa onları gerçek yola doönüştürüyor
        return os.path.expandvars(desktop_path)
    except Exception:
        # Hata olursa klasik yoldan devam et
        return os.path.join(os.path.expanduser("~"), "Desktop")

class DownloadSignals(QObject):
    progress_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    download_finished = pyqtSignal(str)

class YoutubeDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.signals = DownloadSignals()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setFixedSize(480, 240)
        
        # İkon tanımlama
        if os.path.exists(ICON_NAME):
            self.setWindowIcon(QIcon(ICON_NAME))
        
        
        main_layout = QVBoxLayout()
        
        # URL nin alındığı label
        self.url_label = QLabel("YouTube Video URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        
        # kalite ve mp3/mp3 seçme
        options_layout = QHBoxLayout()
        
        self.radio_mp3 = QRadioButton("MP3 (Audio)")
        self.radio_mp4 = QRadioButton("MP4 (Video)")
        self.radio_mp4.setChecked(True)
        
        self.quality_combobox = QComboBox()
        self.quality_combobox.addItems(["Best Quality", "1080p", "720p", "480p", "360p"])
        
        options_layout.addWidget(self.radio_mp3)
        options_layout.addWidget(self.radio_mp4)
        options_layout.addWidget(QLabel("Quality:"))
        options_layout.addWidget(self.quality_combobox)
        
        # mp3 seçilirse kalite yi pasif hale getir
        self.radio_mp3.toggled.connect(lambda: self.quality_combobox.setEnabled(False))
        self.radio_mp4.toggled.connect(lambda: self.quality_combobox.setEnabled(True))
        
        # ilerleme barı
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Status: Idle")
        
        # indirme butonu
        self.download_button = QPushButton("Start Download")
        self.download_button.clicked.connect(self.trigger_download)
        
        #program da ki layout
        main_layout.addWidget(self.url_label)
        main_layout.addWidget(self.url_input)
        main_layout.addLayout(options_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.download_button)
        
        self.setLayout(main_layout)
        
        # bağlantı
        self.signals.progress_changed.connect(self.progress_bar.setValue)
        self.signals.status_changed.connect(self.status_label.setText)
        self.signals.download_finished.connect(self.on_download_finished)

    def progress_hook(self, data):
        if data.get("status") == "downloading":
            percentage = 0.0
            if "_percent_str" in data:
                try:
                    clean_text = data["_percent_str"].replace('%', '').strip()
                    percentage = float(clean_text)
                except:
                    pass
            elif "downloaded_bytes" in data and "total_bytes" in data:
                percentage = (data["downloaded_bytes"] / data["total_bytes"]) * 100
                
            speed = data.get("_speed_str", "Unknown")
            self.signals.progress_changed.emit(int(percentage))
            self.signals.status_changed.emit(f"Status: Downloading... Speed: {speed}")
            
        elif data.get("status") == "finished":
            self.signals.status_changed.emit("Status: Processing file (FFmpeg)...")

    def download_worker(self, url, format_type, selected_quality):
        try:
            self.signals.status_changed.emit("Status: Fetching video info...")
            desktop_path = get_true_desktop_path() # Garanti altına alınan masaüstü yolu
            
            ydl_opts = {
                "outtmpl": os.path.join(desktop_path, "%(title)s.%(ext)s"),
                "progress_hooks": [self.progress_hook],
                "noplaylist": True,
                "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe()
            }
            
            if format_type == "mp3":
                ydl_opts.update({
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192"
                    }]
                })
            else:
                if selected_quality == "1080p":
                    quality_filter = "bestvideo[height<=1080]+bestaudio/best"
                elif selected_quality == "720p":
                    quality_filter = "bestvideo[height<=720]+bestaudio/best"
                elif selected_quality == "480p":
                    quality_filter = "bestvideo[height<=480]+bestaudio/best"
                elif selected_quality == "360p":
                    quality_filter = "bestvideo[height<=360]+bestaudio/best"
                else:
                    quality_filter = "bestvideo+bestaudio/best"
                
                ydl_opts.update({
                    "format": quality_filter,
                    "merge_output_format": "mp4"
                })
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            self.signals.download_finished.emit("Success: File saved directly to your Desktop!")
        except Exception as e:
            self.signals.download_finished.emit(f"Error: {str(e)}")

    def trigger_download(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Status: Please enter a valid URL!")
            return
            
        format_type = "mp3" if self.radio_mp3.isChecked() else "mp4"
        selected_quality = self.quality_combobox.currentText()
        
        self.download_button.setEnabled(False)
        self.progress_bar.setValue(0)
        
        threading.Thread(
            target=self.download_worker, 
            args=(url, format_type, selected_quality), 
            daemon=True
        ).start()

    def on_download_finished(self, message):
        self.status_label.setText(message)
        self.download_button.setEnabled(True)
        if "Success" in message:
            self.progress_bar.setValue(100)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YoutubeDownloaderApp()
    window.show()
    sys.exit(app.exec())