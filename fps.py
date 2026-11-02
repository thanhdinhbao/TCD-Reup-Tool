import os
import time
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import random
import struct

class VideoProcessorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Tool Auto Video Processor (paschafps Quality Method)")
        self.root.geometry("650x550")
        
        self.supported_exts = ('.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v')
        self.audio_exts = ('.mp3', '.m4a', '.wav', '.aac', '.flac')
        
        # --- Variables Tab 1 ---
        self.is_running = False
        self.process = None
        self.processed_files = set()
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_dir = tk.StringVar(value=os.path.join(base_dir, "INPUT"))
        self.output_dir = tk.StringVar(value=os.path.join(base_dir, "OUTPUT"))
        self.fps_var = tk.StringVar(value="60")
        
        # --- Variables Tab 2 ---
        self.bgm_is_running = False
        self.bgm_process = None
        self.bgm_processed_files = set()
        
        self.bgm_input_dir = tk.StringVar(value=os.path.join(base_dir, "INPUT"))
        self.bgm_music_dir = tk.StringVar(value=os.path.join(base_dir, "AUDIO_BGM"))
        self.bgm_output_dir = tk.StringVar(value=os.path.join(base_dir, "OUTPUT"))
        self.bgm_mode_var = tk.StringVar(value="Trộn âm thanh (Mix)")
        self.bgm_vol_var = tk.DoubleVar(value=0.2)
        
        # Create default dirs if not exist
        for d in [self.input_dir.get(), self.output_dir.get(), self.bgm_music_dir.get()]:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
                
        # --- UI Setup ---
        self.setup_ui()

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # TAB 1: FPS Changer
        self.tab_fps = tk.Frame(self.notebook)
        self.notebook.add(self.tab_fps, text="1. Chỉnh FPS (Bơm Rác)")
        self.setup_fps_tab(self.tab_fps)
        
        # TAB 2: BGM Adder
        self.tab_bgm = tk.Frame(self.notebook)
        self.notebook.add(self.tab_bgm, text="2. Ghép Nhạc (BGM)")
        self.setup_bgm_tab(self.tab_bgm)

    # ================== TAB 1 (FPS) ==================
    def setup_fps_tab(self, parent):
        # Input Folder
        input_frame = tk.Frame(parent)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(input_frame, text="Thư mục INPUT:", width=15, anchor="w").pack(side=tk.LEFT)
        tk.Entry(input_frame, textvariable=self.input_dir, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(input_frame, text="Chọn", command=lambda: self.browse_folder(self.input_dir)).pack(side=tk.LEFT)

        # Output Folder
        output_frame = tk.Frame(parent)
        output_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(output_frame, text="Thư mục OUTPUT:", width=15, anchor="w").pack(side=tk.LEFT)
        tk.Entry(output_frame, textvariable=self.output_dir, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(output_frame, text="Chọn", command=lambda: self.browse_folder(self.output_dir)).pack(side=tk.LEFT)

        # FPS Selection
        fps_frame = tk.Frame(parent)
        fps_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(fps_frame, text="Chọn FPS:", width=15, anchor="w").pack(side=tk.LEFT)
        fps_combo = ttk.Combobox(fps_frame, textvariable=self.fps_var, values=["60", "120", "240"], state="readonly", width=10)
        fps_combo.pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        self.start_btn = tk.Button(btn_frame, text="START", command=self.start_processing, bg="green", fg="white", font=("Arial", 11, "bold"), width=10)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        self.stop_btn = tk.Button(btn_frame, text="STOP", command=self.stop_processing, bg="red", fg="white", font=("Arial", 11, "bold"), width=10, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # Log Box
        log_frame = tk.Frame(parent)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(log_frame, text="Logs (FPS):").pack(anchor="w")
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ================== TAB 2 (BGM) ==================
    def setup_bgm_tab(self, parent):
        # Input Video
        input_frame = tk.Frame(parent)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(input_frame, text="Video INPUT:", width=15, anchor="w").pack(side=tk.LEFT)
        tk.Entry(input_frame, textvariable=self.bgm_input_dir, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(input_frame, text="Chọn", command=lambda: self.browse_folder(self.bgm_input_dir)).pack(side=tk.LEFT)
        
        # Input Music
        music_frame = tk.Frame(parent)
        music_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(music_frame, text="Thư mục Nhạc:", width=15, anchor="w").pack(side=tk.LEFT)
        tk.Entry(music_frame, textvariable=self.bgm_music_dir, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(music_frame, text="Chọn", command=lambda: self.browse_folder(self.bgm_music_dir)).pack(side=tk.LEFT)

        # Output Folder
        output_frame = tk.Frame(parent)
        output_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(output_frame, text="Video OUTPUT:", width=15, anchor="w").pack(side=tk.LEFT)
        tk.Entry(output_frame, textvariable=self.bgm_output_dir, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(output_frame, text="Chọn", command=lambda: self.browse_folder(self.bgm_output_dir)).pack(side=tk.LEFT)

        # Settings BGM
        settings_frame = tk.Frame(parent)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(settings_frame, text="Chế độ âm thanh:", width=15, anchor="w").pack(side=tk.LEFT)
        mode_combo = ttk.Combobox(settings_frame, textvariable=self.bgm_mode_var, values=["Chỉ dùng nhạc mới (Xóa tiếng gốc)", "Trộn âm thanh (Mix)"], state="readonly", width=30)
        mode_combo.pack(side=tk.LEFT)
        
        vol_frame = tk.Frame(parent)
        vol_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(vol_frame, text="Âm lượng nhạc:", width=15, anchor="w").pack(side=tk.LEFT)
        vol_scale = tk.Scale(vol_frame, variable=self.bgm_vol_var, from_=0.0, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, length=200)
        vol_scale.pack(side=tk.LEFT)
        tk.Label(vol_frame, text="(Dùng khi Trộn)").pack(side=tk.LEFT, padx=5)

        # Buttons
        btn_frame = tk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        self.bgm_start_btn = tk.Button(btn_frame, text="START", command=self.start_bgm_processing, bg="green", fg="white", font=("Arial", 11, "bold"), width=10)
        self.bgm_start_btn.pack(side=tk.LEFT, padx=10)
        
        self.bgm_stop_btn = tk.Button(btn_frame, text="STOP", command=self.stop_bgm_processing, bg="red", fg="white", font=("Arial", 11, "bold"), width=10, state=tk.DISABLED)
        self.bgm_stop_btn.pack(side=tk.LEFT, padx=10)
        
        # Log Box
        log_frame = tk.Frame(parent)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(log_frame, text="Logs (BGM):").pack(anchor="w")
        self.bgm_log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.bgm_log_text.pack(fill=tk.BOTH, expand=True)

    # ================== UTILS ==================
    def browse_folder(self, string_var):
        folder = filedialog.askdirectory()
        if folder:
            string_var.set(os.path.normpath(folder))

    def log(self, message, is_bgm=False):
        text_widget = self.bgm_log_text if is_bgm else self.log_text
        text_widget.insert(tk.END, message + "\n")
        text_widget.see(tk.END)
        self.root.update_idletasks()

    def get_ffmpeg_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_exe = os.path.join(base_dir, "ffmpeg.exe")
        return ffmpeg_exe

    # ================== LOGIC TAB 1 (FPS) ==================
    def start_processing(self):
        self.processed_files.clear()
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log("=== BẮT ĐẦU CHẠY (FPS) ===")
        
        self.current_input_dir = self.input_dir.get()
        self.current_output_dir = self.output_dir.get()
        
        fps_str = self.fps_var.get()
        if fps_str == "60": self.current_fps_scale = "2"
        elif fps_str == "120": self.current_fps_scale = "6"
        elif fps_str == "240": self.current_fps_scale = "12"
        else: self.current_fps_scale = "2"
        
        threading.Thread(target=self.process_loop, daemon=True).start()

    def stop_processing(self):
        self.log("Yêu cầu dừng (FPS)...")
        self.is_running = False
        if self.process:
            try: self.process.kill()
            except: pass
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("=== ĐÃ DỪNG (FPS) ===")

    def process_loop(self):
        ffmpeg_exe = self.get_ffmpeg_path()
        if not os.path.exists(ffmpeg_exe):
            self.root.after(0, self.log, "LỖI: Không tìm thấy ffmpeg.exe trong thư mục hiện tại!")
            self.root.after(0, self.stop_processing)
            return

        scale = self.current_fps_scale
        
        while self.is_running:
            input_folder = self.current_input_dir
            output_folder = self.current_output_dir
            
            try:
                files = os.listdir(input_folder)
            except Exception as e:
                self.root.after(0, self.log, f"Lỗi khi đọc thư mục input: {e}")
                time.sleep(2)
                continue

            for file in files:
                if not self.is_running: break
                    
                if file.lower().endswith(self.supported_exts) and file not in self.processed_files:
                    base_name, ext = os.path.splitext(file)
                    input_path = os.path.join(input_folder, file)
                    output_path = os.path.join(output_folder, f"{base_name}{ext}")
                    
                    if os.path.abspath(input_path) == os.path.abspath(output_path):
                        self.root.after(0, self.log, f"-> BỎ QUA {file}: INPUT và OUTPUT trùng nhau!")
                        self.processed_files.add(file)
                        continue
                    
                    self.root.after(0, self.log, f"Đang xử lý FPS: {file}...")
                    
                    cmd = [
                        ffmpeg_exe, "-y",
                        "-itsscale", scale,
                        "-i", input_path,
                        "-c:v", "copy", "-c:a", "copy",
                        output_path
                    ]
                    
                    try:
                        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                        out_bytes, err_bytes = self.process.communicate()
                        err = err_bytes.decode('utf-8', errors='replace') if err_bytes else ""
                        
                        if self.process.returncode == 0:
                            self.root.after(0, self.log, f"-> HOÀN THÀNH: {file}")
                            
                            # --- BƠM RÁC (Chỉ áp dụng ở Tab 1) ---
                            try:
                                padding_data_size = random.randint(10240, 51200)
                                box_size = padding_data_size + 8
                                box_header = struct.pack('>I', box_size) + b'free'
                                box_payload = os.urandom(padding_data_size)
                                with open(output_path, 'ab') as f:
                                    f.write(box_header + box_payload)
                                self.root.after(0, self.log, f"   [+] Bơm thành công {box_size//1024}KB rác.")
                            except Exception as ex:
                                self.root.after(0, self.log, f"   [-] Lỗi bơm rác: {ex}")
                            
                            self.processed_files.add(file)
                        else:
                            if not self.is_running:
                                self.root.after(0, self.log, f"-> BỊ HỦY: {file}")
                                if os.path.exists(output_path): os.remove(output_path)
                            else:
                                err_trunc = err[-1000:] if len(err) > 1000 else err
                                self.root.after(0, self.log, f"-> LỖI: {file}\n{err_trunc}")
                                self.processed_files.add(file)
                    except Exception as e:
                        self.root.after(0, self.log, f"-> LỖI THỰC THI: {e}")
            
            if self.is_running:
                time.sleep(2)

    # ================== LOGIC TAB 2 (BGM) ==================
    def start_bgm_processing(self):
        self.bgm_processed_files.clear()
        self.bgm_is_running = True
        self.bgm_start_btn.config(state=tk.DISABLED)
        self.bgm_stop_btn.config(state=tk.NORMAL)
        self.log("=== BẮT ĐẦU GHÉP NHẠC ===", True)
        
        self.current_bgm_input = self.bgm_input_dir.get()
        self.current_bgm_music = self.bgm_music_dir.get()
        self.current_bgm_output = self.bgm_output_dir.get()
        self.current_bgm_mode = self.bgm_mode_var.get()
        self.current_bgm_vol = self.bgm_vol_var.get()
        
        threading.Thread(target=self.bgm_process_loop, daemon=True).start()

    def stop_bgm_processing(self):
        self.log("Yêu cầu dừng (Ghép Nhạc)...", True)
        self.bgm_is_running = False
        if self.bgm_process:
            try: self.bgm_process.kill()
            except: pass
        self.bgm_start_btn.config(state=tk.NORMAL)
        self.bgm_stop_btn.config(state=tk.DISABLED)
        self.log("=== ĐÃ DỪNG (GHÉP NHẠC) ===", True)

    def bgm_process_loop(self):
        ffmpeg_exe = self.get_ffmpeg_path()
        if not os.path.exists(ffmpeg_exe):
            self.root.after(0, self.log, "LỖI: Không tìm thấy ffmpeg.exe!", True)
            self.root.after(0, self.stop_bgm_processing)
            return
            
        while self.bgm_is_running:
            input_folder = self.current_bgm_input
            music_folder = self.current_bgm_music
            output_folder = self.current_bgm_output
            
            try:
                files = os.listdir(input_folder)
            except Exception as e:
                self.root.after(0, self.log, f"Lỗi đọc thư mục video: {e}", True)
                time.sleep(2)
                continue
                
            try:
                musics = [m for m in os.listdir(music_folder) if m.lower().endswith(self.audio_exts)]
            except:
                musics = []

            for file in files:
                if not self.bgm_is_running: break
                    
                if file.lower().endswith(self.supported_exts) and file not in self.bgm_processed_files:
                    if not musics:
                        self.root.after(0, self.log, "LỖI: Không tìm thấy file nhạc (.mp3, .wav...) nào trong thư mục Nhạc!", True)
                        time.sleep(3)
                        break
                        
                    base_name, ext = os.path.splitext(file)
                    input_path = os.path.join(input_folder, file)
                    output_path = os.path.join(output_folder, f"{base_name}_bgm{ext}")
                    
                    if os.path.abspath(input_path) == os.path.abspath(output_path):
                        self.root.after(0, self.log, f"-> BỎ QUA {file}: INPUT và OUTPUT trùng nhau!", True)
                        self.bgm_processed_files.add(file)
                        continue
                        
                    # Lấy nhạc ngẫu nhiên
                    chosen_music = random.choice(musics)
                    music_path = os.path.join(music_folder, chosen_music)
                    
                    self.root.after(0, self.log, f"Đang ghép {file} với nhạc {chosen_music}...", True)
                    
                    if "Mix" in self.current_bgm_mode:
                        # Trộn âm thanh (Mix) - Giữ giọng gốc, thêm BGM nhỏ hơn
                        cmd = [
                            ffmpeg_exe, "-y",
                            "-i", input_path,
                            "-stream_loop", "-1", "-i", music_path,
                            "-filter_complex", f"[1:a]volume={self.current_bgm_vol}[a1];[0:a][a1]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]",
                            "-map", "0:v:0",
                            "-map", "[a]",
                            "-c:v", "copy",
                            "-c:a", "aac",
                            output_path
                        ]
                    else:
                        # Thay thế hoàn toàn âm thanh gốc
                        cmd = [
                            ffmpeg_exe, "-y",
                            "-i", input_path,
                            "-stream_loop", "-1", "-i", music_path,
                            "-map", "0:v:0",
                            "-map", "1:a:0",
                            "-c:v", "copy",
                            "-c:a", "aac",
                            "-shortest",
                            output_path
                        ]
                        
                    try:
                        self.bgm_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                        out_bytes, err_bytes = self.bgm_process.communicate()
                        err = err_bytes.decode('utf-8', errors='replace') if err_bytes else ""
                        
                        if self.bgm_process.returncode == 0:
                            self.root.after(0, self.log, f"-> HOÀN THÀNH: {base_name}_bgm{ext}", True)
                            self.bgm_processed_files.add(file)
                        else:
                            if not self.bgm_is_running:
                                self.root.after(0, self.log, f"-> BỊ HỦY: {file}", True)
                                if os.path.exists(output_path): os.remove(output_path)
                            else:
                                err_trunc = err[-1000:] if len(err) > 1000 else err
                                self.root.after(0, self.log, f"-> LỖI ghép nhạc: {file}\n{err_trunc}", True)
                                self.bgm_processed_files.add(file)
                    except Exception as e:
                        self.root.after(0, self.log, f"-> LỖI THỰC THI (BGM): {e}", True)
                        
            if self.bgm_is_running:
                time.sleep(2)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoProcessorGUI(root)
    root.mainloop()
