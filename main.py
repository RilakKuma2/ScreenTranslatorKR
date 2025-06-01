# app.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, colorchooser, font as tkFont
import configparser
import threading
import time
import pyautogui
from PIL import Image, ImageOps
import io
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import webbrowser
import re

from ScreenRegionSelector import ScreenRegionSelector
from OverlayWindow import OverlayWindow
from ApiKeyPopup import ApiKeyPopup
from PromptEditPopup import PromptEditPopup, DEFAULT_PROMPT

CONFIG_FILE = 'transconfig.ini'
GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

DEFAULT_APP_SETTINGS = {
    "api_key": "",
    "prompt": DEFAULT_PROMPT,
    "model": GEMINI_MODELS[0],
    "interval": 0.5,
    "use_resize": True,
    "resize_percentage": 50,
    "overlay_font_family": 'Malgun Gothic',
    "overlay_font_size": 40,
    "overlay_font_color": '#FFFFFF',
    "overlay_bg_color": '#000000',
    "overlay_alpha": 0.7,
    "overlay_x": 100,
    "overlay_y": 100,
    "overlay_width": 1200,
    "overlay_height": 250,
}

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("실시간 화면 번역기")
        self.root.geometry("550x920")

        self.api_key = tk.StringVar(value=DEFAULT_APP_SETTINGS["api_key"])
        self.selected_model = tk.StringVar(value=DEFAULT_APP_SETTINGS["model"])
        self.custom_prompt = tk.StringVar(value=DEFAULT_APP_SETTINGS["prompt"])
        self.translation_interval = tk.DoubleVar(value=DEFAULT_APP_SETTINGS["interval"])
        self.use_resize = tk.BooleanVar(value=DEFAULT_APP_SETTINGS["use_resize"])
        self.resize_percentage = tk.IntVar(value=DEFAULT_APP_SETTINGS["resize_percentage"])
        self.overlay_font_family = tk.StringVar(value=DEFAULT_APP_SETTINGS["overlay_font_family"])
        self.overlay_font_size = tk.IntVar(value=DEFAULT_APP_SETTINGS["overlay_font_size"])
        self.overlay_font_color = tk.StringVar(value=DEFAULT_APP_SETTINGS["overlay_font_color"])
        self.overlay_bg_color = tk.StringVar(value=DEFAULT_APP_SETTINGS["overlay_bg_color"])
        self.overlay_alpha = tk.DoubleVar(value=DEFAULT_APP_SETTINGS["overlay_alpha"])

        self.overlay_x = DEFAULT_APP_SETTINGS["overlay_x"]
        self.overlay_y = DEFAULT_APP_SETTINGS["overlay_y"]
        self.overlay_width = DEFAULT_APP_SETTINGS["overlay_width"]
        self.overlay_height = DEFAULT_APP_SETTINGS["overlay_height"]

        self.selected_region = None
        self.is_translating = False
        self.translation_thread = None
        self.gemini_client = None

        self.load_config()

        overlay_initial_cfg = {
            'x': self.overlay_x, 'y': self.overlay_y,
            'width': self.overlay_width, 'height': self.overlay_height,
            'font_family': self.overlay_font_family.get(),
            'font_size': self.overlay_font_size.get(),
            'font_color': self.overlay_font_color.get(),
            'bg_color': self.overlay_bg_color.get(),
            'alpha': self.overlay_alpha.get()
        }
        self.overlay_window = OverlayWindow(self.root, initial_config=overlay_initial_cfg)

        # --- GUI 구성 ---
        main_controls_frame = ttk.Frame(root, padding=5)
        main_controls_frame.grid(row=0, column=0, sticky="ew")
        # main_controls_frame의 0번째 열이 확장되도록 설정
        main_controls_frame.grid_columnconfigure(0, weight=1)


        settings_frame = ttk.LabelFrame(main_controls_frame, text="번역 설정", padding=10)
        # *** 오류 수정: _weight 옵션 제거 ***
        settings_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        image_process_frame = ttk.LabelFrame(main_controls_frame, text="이미지 처리 설정", padding=10)
        # *** 오류 수정: _weight 옵션 제거 ***
        image_process_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        overlay_settings_frame = ttk.LabelFrame(main_controls_frame, text="오버레이 창 설정", padding=10)
        # *** 오류 수정: _weight 옵션 제거 ***
        overlay_settings_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        reset_frame = ttk.Frame(main_controls_frame, padding=10)
        reset_frame.grid(row=3, column=0, padx=5, pady=10, sticky="ew")
        self.reset_settings_button = ttk.Button(reset_frame, text="모든 설정 초기화", command=self.reset_all_settings)
        self.reset_settings_button.pack(fill=tk.X)

        translation_output_frame = ttk.LabelFrame(root, text="번역 결과 (메인 창)", padding=10)
        translation_output_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # 루트 윈도우의 0번째 열과 1번째 행(번역 결과 영역)이 확장되도록 설정
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        # --- 번역 설정 GUI ---
        self.api_key_button = ttk.Button(settings_frame, text="Gemini API 키 설정", command=self.open_api_key_popup)
        self.api_key_button.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        self.api_key_status_label = ttk.Label(settings_frame, text="API 키: 미설정")
        self.api_key_status_label.grid(row=0, column=2, columnspan=2, padx=5, pady=5, sticky="w")

        self.prompt_edit_button = ttk.Button(settings_frame, text="프롬프트 수정", command=self.open_prompt_edit_popup)
        self.prompt_edit_button.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        ttk.Label(settings_frame, text="Gemini 모델:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.model_menu = ttk.OptionMenu(settings_frame, self.selected_model, self.selected_model.get(), *GEMINI_MODELS)
        self.model_menu.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

        ttk.Label(settings_frame, text="번역 주기 (초):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.interval_spinbox = ttk.Spinbox(
            settings_frame, from_=0.2, to=10.0, increment=0.1, textvariable=self.translation_interval, width=8
        )
        self.interval_spinbox.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        self.select_region_button = ttk.Button(settings_frame, text="번역 영역 지정", command=self.open_region_selector)
        self.select_region_button.grid(row=4, column=0, columnspan=4, padx=5, pady=10, sticky="ew")

        self.region_label = ttk.Label(settings_frame, text="선택된 영역: 없음")
        self.region_label.grid(row=5, column=0, columnspan=4, padx=5, pady=2, sticky="w")

        self.start_button = ttk.Button(settings_frame, text="번역 시작", command=self.start_translation, state=tk.DISABLED)
        self.start_button.grid(row=6, column=0, padx=5, pady=10, sticky="ew")
        self.stop_button = ttk.Button(settings_frame, text="번역 중지", command=self.stop_translation, state=tk.DISABLED)
        self.stop_button.grid(row=6, column=1, padx=5, pady=10, sticky="ew")
        self.show_overlay_button = ttk.Button(settings_frame, text="오버레이 표시/숨김", command=self.toggle_overlay_visibility)
        self.show_overlay_button.grid(row=6, column=2, padx=5, pady=10, sticky="ew")

        # settings_frame 내부 열 확장 설정
        settings_frame.grid_columnconfigure(1, weight=1) # 모델, 주기 스핀박스 등이 있는 열
        settings_frame.grid_columnconfigure(2, weight=0) # API 키 상태 레이블, 오버레이 버튼 (확장 필요 없을 수 있음)
        settings_frame.grid_columnconfigure(3, weight=0) # (확장 필요 없을 수 있음)


        # --- 이미지 처리 설정 GUI ---
        self.resize_checkbutton = ttk.Checkbutton(
            image_process_frame, text="이미지 리사이징 사용", variable=self.use_resize,
            command=self.toggle_resize_options_state
        )
        self.resize_checkbutton.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(image_process_frame, text="리사이징 비율 (%):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.resize_spinbox = ttk.Spinbox(
            image_process_frame, from_=10, to=100, increment=5, textvariable=self.resize_percentage, width=8,
            state=(tk.NORMAL if self.use_resize.get() else tk.DISABLED)
        )
        self.resize_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        image_process_frame.grid_columnconfigure(1, weight=0) # 리사이즈 스핀박스 열 (확장 필요 없을 수 있음)

        # --- 오버레이 창 설정 GUI 요소 ---
        ttk.Label(overlay_settings_frame, text="글꼴 크기:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.font_size_spinbox = ttk.Spinbox(overlay_settings_frame, from_=8, to=72, textvariable=self.overlay_font_size, width=5, command=self.apply_overlay_settings)
        self.font_size_spinbox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(overlay_settings_frame, text="글꼴 색:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.font_color_button = ttk.Button(overlay_settings_frame, text="선택", command=lambda: self.choose_color('font'))
        self.font_color_button.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        self.font_color_preview = tk.Frame(overlay_settings_frame, width=20, height=20, bg=self.overlay_font_color.get())
        self.font_color_preview.grid(row=0, column=4, padx=5, pady=5)
        ttk.Label(overlay_settings_frame, text="배경 색:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.bg_color_button = ttk.Button(overlay_settings_frame, text="선택", command=lambda: self.choose_color('bg'))
        self.bg_color_button.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.bg_color_preview = tk.Frame(overlay_settings_frame, width=20, height=20, bg=self.overlay_bg_color.get())
        self.bg_color_preview.grid(row=1, column=2, padx=5, pady=5)
        ttk.Label(overlay_settings_frame, text="창 투명도:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.alpha_scale = ttk.Scale(overlay_settings_frame, from_=0.1, to=1.0, variable=self.overlay_alpha, orient=tk.HORIZONTAL, command=lambda x: self.apply_overlay_settings())
        self.alpha_scale.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        ttk.Label(overlay_settings_frame, text="글꼴:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        available_fonts = sorted(list(tkFont.families())); common_fonts = ['Arial', 'Calibri', 'Consolas', 'Courier New', 'Georgia', 'Malgun Gothic', 'NanumGothic', 'Tahoma', 'Times New Roman', 'Verdana']
        display_fonts = [f for f in common_fonts if f in available_fonts]
        if not self.overlay_font_family.get() in display_fonts and self.overlay_font_family.get() in available_fonts: display_fonts.append(self.overlay_font_family.get())
        if not display_fonts : display_fonts = [self.overlay_font_family.get()]
        self.font_family_menu = ttk.OptionMenu(overlay_settings_frame, self.overlay_font_family, self.overlay_font_family.get() , *display_fonts, command=lambda x: self.apply_overlay_settings())
        self.font_family_menu.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        # overlay_settings_frame 내부 열 확장 설정
        overlay_settings_frame.grid_columnconfigure(1, weight=0) # 글꼴 크기, 배경색 선택 등
        overlay_settings_frame.grid_columnconfigure(3, weight=1) # 글꼴색 선택, 투명도, 글꼴 메뉴

        # Translated Text Display (메인 창)
        self.translated_text_area = scrolledtext.ScrolledText(translation_output_frame, wrap=tk.WORD, height=10)
        self.translated_text_area.pack(fill=tk.BOTH, expand=True)
        self.translated_text_area.config(state=tk.DISABLED)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_start_button_state()
        self.apply_overlay_settings()
        self.toggle_resize_options_state()

    def reset_all_settings(self):
        if messagebox.askyesno("설정 초기화 확인", "모든 설정을 기본값으로 초기화하시겠습니까?\nAPI 키 정보도 삭제됩니다."):
            self.api_key.set(DEFAULT_APP_SETTINGS["api_key"])
            self.custom_prompt.set(DEFAULT_APP_SETTINGS["prompt"])
            self.selected_model.set(DEFAULT_APP_SETTINGS["model"])
            self.translation_interval.set(DEFAULT_APP_SETTINGS["interval"])
            self.use_resize.set(DEFAULT_APP_SETTINGS["use_resize"])
            self.resize_percentage.set(DEFAULT_APP_SETTINGS["resize_percentage"])
            self.overlay_font_family.set(DEFAULT_APP_SETTINGS["overlay_font_family"])
            self.overlay_font_size.set(DEFAULT_APP_SETTINGS["overlay_font_size"])
            self.overlay_font_color.set(DEFAULT_APP_SETTINGS["overlay_font_color"])
            self.overlay_bg_color.set(DEFAULT_APP_SETTINGS["overlay_bg_color"])
            self.overlay_alpha.set(DEFAULT_APP_SETTINGS["overlay_alpha"])
            self.overlay_x = DEFAULT_APP_SETTINGS["overlay_x"]
            self.overlay_y = DEFAULT_APP_SETTINGS["overlay_y"]
            self.overlay_width = DEFAULT_APP_SETTINGS["overlay_width"]
            self.overlay_height = DEFAULT_APP_SETTINGS["overlay_height"]
            if hasattr(self, 'overlay_window') and self.overlay_window:
                self.overlay_window.current_config.update({
                    'x': self.overlay_x, 'y': self.overlay_y,
                    'width': self.overlay_width, 'height': self.overlay_height,
                    'font_family': self.overlay_font_family.get(),
                    'font_size': self.overlay_font_size.get(),
                    'font_color': self.overlay_font_color.get(),
                    'bg_color': self.overlay_bg_color.get(),
                    'alpha': self.overlay_alpha.get(), 'text': '번역 대기 중...'
                })
                self.overlay_window.apply_config(self.overlay_window.current_config)
            self.save_config()
            self.toggle_resize_options_state()
            self.apply_overlay_settings()
            self.update_start_button_state()
            messagebox.showinfo("초기화 완료", "모든 설정이 기본값으로 초기화되었습니다.")

    def open_api_key_popup(self):
        ApiKeyPopup(self.root, self.api_key.get(), self.save_api_key_from_popup)

    def save_api_key_from_popup(self, new_key):
        self.api_key.set(new_key)
        self.update_start_button_state()
        self.save_config()
        print("API 키가 업데이트되었습니다.")

    def open_prompt_edit_popup(self):
        PromptEditPopup(self.root, self.custom_prompt.get(), self.save_prompt_from_popup)

    def save_prompt_from_popup(self, new_prompt):
        self.custom_prompt.set(new_prompt)
        self.save_config()
        print("프롬프트가 업데이트되었습니다.")

    def toggle_resize_options_state(self):
        if self.use_resize.get(): self.resize_spinbox.config(state=tk.NORMAL)
        else: self.resize_spinbox.config(state=tk.DISABLED)

    def choose_color(self, target):
        color_code = colorchooser.askcolor(title=f"{target} 색상 선택")
        if color_code and color_code[1]:
            if target == 'font': self.overlay_font_color.set(color_code[1]); self.font_color_preview.config(bg=color_code[1])
            elif target == 'bg': self.overlay_bg_color.set(color_code[1]); self.bg_color_preview.config(bg=color_code[1])
            self.apply_overlay_settings()

    def apply_overlay_settings(self):
        if hasattr(self, 'overlay_window') and self.overlay_window:
            try:
                font_size = self.overlay_font_size.get(); alpha = self.overlay_alpha.get()
                self.overlay_window.update_appearance(
                    self.overlay_font_family.get(), font_size,
                    self.overlay_font_color.get(), self.overlay_bg_color.get(), alpha
                )
                self.font_color_preview.config(bg=self.overlay_font_color.get())
                self.bg_color_preview.config(bg=self.overlay_bg_color.get())
            except tk.TclError as e: print(f"오버레이 설정 적용 중 오류: {e}")

    def load_config(self):
        config = configparser.ConfigParser()
        if config.read(CONFIG_FILE):
            self.api_key.set(config.get('Gemini', 'api_key', fallback=DEFAULT_APP_SETTINGS["api_key"]))
            self.custom_prompt.set(config.get('Gemini', 'prompt', fallback=DEFAULT_APP_SETTINGS["prompt"]))
            saved_model = config.get('Gemini', 'model', fallback=DEFAULT_APP_SETTINGS["model"])
            self.selected_model.set(saved_model if saved_model in GEMINI_MODELS else DEFAULT_APP_SETTINGS["model"])
            self.translation_interval.set(config.getfloat('Gemini', 'interval', fallback=DEFAULT_APP_SETTINGS["interval"]))
            self.use_resize.set(config.getboolean('ImageProcessing', 'use_resize', fallback=DEFAULT_APP_SETTINGS["use_resize"]))
            self.resize_percentage.set(config.getint('ImageProcessing', 'resize_percentage', fallback=DEFAULT_APP_SETTINGS["resize_percentage"]))
            self.overlay_font_family.set(config.get('Overlay', 'font_family', fallback=DEFAULT_APP_SETTINGS["overlay_font_family"]))
            self.overlay_font_size.set(config.getint('Overlay', 'font_size', fallback=DEFAULT_APP_SETTINGS["overlay_font_size"]))
            self.overlay_font_color.set(config.get('Overlay', 'font_color', fallback=DEFAULT_APP_SETTINGS["overlay_font_color"]))
            self.overlay_bg_color.set(config.get('Overlay', 'bg_color', fallback=DEFAULT_APP_SETTINGS["overlay_bg_color"]))
            self.overlay_alpha.set(config.getfloat('Overlay', 'alpha', fallback=DEFAULT_APP_SETTINGS["overlay_alpha"]))
            self.overlay_x = config.getint('Overlay', 'x', fallback=DEFAULT_APP_SETTINGS["overlay_x"])
            self.overlay_y = config.getint('Overlay', 'y', fallback=DEFAULT_APP_SETTINGS["overlay_y"])
            self.overlay_width = config.getint('Overlay', 'width', fallback=DEFAULT_APP_SETTINGS["overlay_width"])
            self.overlay_height = config.getint('Overlay', 'height', fallback=DEFAULT_APP_SETTINGS["overlay_height"])
        else: self.save_config()

    def save_config(self):
        config = configparser.ConfigParser()
        config['Gemini'] = {
            'api_key': self.api_key.get(), 'prompt': self.custom_prompt.get(),
            'model': self.selected_model.get(), 'interval': round(self.translation_interval.get(), 2)
        }
        config['ImageProcessing'] = {
            'use_resize': self.use_resize.get(), 'resize_percentage': self.resize_percentage.get()
        }
        current_overlay_geom = {}
        if hasattr(self, 'overlay_window') and self.overlay_window.winfo_exists():
            current_overlay_geom = self.overlay_window.get_current_config()
        overlay_cfg_to_save = {
            'font_family': self.overlay_font_family.get(), 'font_size': self.overlay_font_size.get(),
            'font_color': self.overlay_font_color.get(), 'bg_color': self.overlay_bg_color.get(),
            'alpha': round(self.overlay_alpha.get(), 2),
            'x': current_overlay_geom.get('x', self.overlay_x), 'y': current_overlay_geom.get('y', self.overlay_y),
            'width': current_overlay_geom.get('width', self.overlay_width), 'height': current_overlay_geom.get('height', self.overlay_height)
        }
        config['Overlay'] = overlay_cfg_to_save
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile: config.write(configfile)
        print("설정이 저장되었습니다.")

    def open_region_selector(self):
        self.root.withdraw(); ScreenRegionSelector(self.root, self.on_region_selected)

    def on_region_selected(self, region):
        self.root.deiconify(); self.root.focus_force()
        if region:
            self.selected_region = region
            self.region_label.config(text=f"선택된 영역: X={region['left']}, Y={region['top']}, W={region['width']}, H={region['height']}")
        else:
            self.selected_region = None; self.region_label.config(text="선택된 영역: 없음 (취소됨)")
        self.update_start_button_state()

    def update_start_button_state(self):
        can_start = self.api_key.get() and self.selected_region and not self.is_translating
        self.start_button.config(state=tk.NORMAL if can_start else tk.DISABLED)
        if hasattr(self, 'api_key_status_label'):
            self.api_key_status_label.config(text="API 키: " + ("설정됨" if self.api_key.get() else "미설정"))
        controls_to_disable_during_translation = [
            self.select_region_button, self.api_key_button, self.prompt_edit_button,
            self.model_menu, self.interval_spinbox,
            self.resize_checkbutton, self.resize_spinbox, self.reset_settings_button
        ]
        if self.is_translating:
            self.stop_button.config(state=tk.NORMAL)
            for widget in controls_to_disable_during_translation:
                if widget: widget.config(state=tk.DISABLED)
        else:
            self.stop_button.config(state=tk.DISABLED)
            for widget in controls_to_disable_during_translation:
                if widget and widget != self.resize_spinbox : widget.config(state=tk.NORMAL)
            self.toggle_resize_options_state()

    def toggle_overlay_visibility(self):
        if self.overlay_window.winfo_viewable(): self.overlay_window.hide()
        else:
            self.apply_overlay_settings()
            self.overlay_window.show_text(self.overlay_window.current_config.get('text', '번역 대기 중...'))

    def start_translation(self):
        if not self.api_key.get(): messagebox.showerror("오류", "Gemini API 키를 먼저 설정해주세요."); return
        if not self.selected_region: messagebox.showerror("오류", "번역할 화면 영역을 먼저 지정해주세요."); return
        if not self.custom_prompt.get(): messagebox.showerror("오류", "프롬프트가 비어있습니다. 프롬프트를 설정해주세요."); return
        self.save_config()
        try:
            genai.configure(api_key=self.api_key.get())
            self.gemini_client = genai.GenerativeModel(self.selected_model.get())
        except Exception as e: messagebox.showerror("API 오류", f"Gemini 클라이언트 초기화 실패: {e}"); return
        self.is_translating = True; self.update_start_button_state()
        self.translated_text_area.config(state=tk.NORMAL); self.translated_text_area.delete('1.0', tk.END)
        self.translated_text_area.insert(tk.END, "번역을 시작합니다...\n"); self.translated_text_area.config(state=tk.DISABLED)
        self.apply_overlay_settings(); self.overlay_window.show_text("번역 준비 중...")
        self.translation_thread = threading.Thread(target=self.translation_loop, daemon=True)
        self.translation_thread.start()

    def stop_translation(self):
        self.is_translating = False; self.update_start_button_state()
        self.update_translated_text("번역이 중지되었습니다.\n", on_overlay=True)
        if self.overlay_window: self.overlay_window.show_text("번역 중지됨")

    def translation_loop(self):
        current_prompt = self.custom_prompt.get()
        if not current_prompt: current_prompt = DEFAULT_PROMPT; self.root.after(0, lambda: self.custom_prompt.set(DEFAULT_PROMPT))
        last_image_hash = None; no_change_count = 0
        current_interval = self.translation_interval.get()
        if current_interval <= 0: current_interval = 0.2
        should_resize = self.use_resize.get()
        resize_percent = self.resize_percentage.get() / 100.0

        while self.is_translating:
            if not self.selected_region: break
            try:
                screenshot_pil = pyautogui.screenshot(region=(
                    self.selected_region['left'], self.selected_region['top'],
                    self.selected_region['width'], self.selected_region['height']
                ))
                if screenshot_pil.mode == 'RGBA': screenshot_pil = screenshot_pil.convert('RGB')
                if should_resize and resize_percent > 0 and resize_percent < 1.0:
                    original_width, original_height = screenshot_pil.size
                    new_width = int(original_width * resize_percent); new_height = int(original_height * resize_percent)
                    if new_width > 0 and new_height > 0: screenshot_pil = screenshot_pil.resize((new_width, new_height), Image.LANCZOS)
                current_image_hash = hash(screenshot_pil.tobytes())
                if current_image_hash == last_image_hash:
                    no_change_count += 1
                    if no_change_count >= 3: time.sleep(current_interval); continue
                else: last_image_hash = current_image_hash; no_change_count = 0
                img_byte_arr = io.BytesIO(); screenshot_pil.save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()
                image_parts = [{"mime_type": "image/jpeg", "data": img_bytes}]

                if self.gemini_client:
                    response = self.gemini_client.generate_content([current_prompt] + image_parts, stream=False)
                    translated_text = "번역 실패"
                    if response.parts: translated_text = response.text.strip()
                    elif response.prompt_feedback and response.prompt_feedback.block_reason:
                        translated_text = f"차단됨: {response.prompt_feedback.block_reason_message}"
                    elif not response.candidates: translated_text = "응답 후보 없음"
                    self.update_translated_text(translated_text + "\n---\n", on_overlay=True)
                time.sleep(current_interval)

            except ResourceExhausted as e:
                error_message_detail = str(e)
                parsed_details = self.parse_quota_error_details(error_message_detail)
                user_message = f"API 할당량 초과: {error_message_detail}\n"
                wait_time_for_user_info = "정보 없음"
                if parsed_details:
                    quota_id_str = parsed_details.get("quota_id", "정보 없음")
                    quota_value_str = parsed_details.get("quota_value", "정보 없음")
                    retry_delay_str = parsed_details.get("retry_delay", "정보 없음")
                    user_message = (
                        "API 할당량 초과\n"
                        f"초과 사항 : {quota_id_str}\n할당량 : {quota_value_str}\n"
                    )
                    if retry_delay_str and retry_delay_str != "정보 없음":
                         wait_time_for_user_info = f"{retry_delay_str}초"
                user_message += f"권장 재시도 대기: {wait_time_for_user_info}."
                print(user_message); self.update_translated_text(user_message + "\n", on_overlay=True)
                time.sleep(max(2.0, current_interval))

            except Exception as e:
                error_message = f"번역 중 오류: {type(e).__name__} - {e}\n"
                print(error_message); self.update_translated_text(error_message, on_overlay=True)
                if "rate limit" in str(e).lower():
                    self.update_translated_text("API 요청 빈도 제한. 잠시 후 재시도.\n", on_overlay=True)
                    time.sleep(max(10.0, current_interval * 2))
                else: time.sleep(max(2.0, current_interval))
        print("번역 루프 종료.")

    def parse_quota_error_details(self, error_message_string):
        details = {}
        try:
            quota_id_match = re.search(r'quota_id:\s*"([^"]+)"', error_message_string, re.IGNORECASE)
            if quota_id_match: details["quota_id"] = quota_id_match.group(1)
            quota_value_match = re.search(r'quota_value:\s*(\d+)', error_message_string, re.IGNORECASE)
            if quota_value_match: details["quota_value"] = quota_value_match.group(1)
            retry_delay_match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)\s*}', error_message_string, re.IGNORECASE)
            if retry_delay_match: details["retry_delay"] = retry_delay_match.group(1)
            else:
                retry_delay_simple_match = re.search(r'retry_delay[:\s]*(\d+)', error_message_string, re.IGNORECASE)
                if retry_delay_simple_match : details["retry_delay"] = retry_delay_simple_match.group(1)
            return details if details else None
        except Exception as parse_error: print(f"할당량 오류 메시지 파싱 중 에러: {parse_error}"); return None

    def update_translated_text(self, text, on_overlay=False):
        def _update_main_window():
            if self.translated_text_area.winfo_exists():
                self.translated_text_area.config(state=tk.NORMAL); self.translated_text_area.insert(tk.END, text)
                self.translated_text_area.see(tk.END); self.translated_text_area.config(state=tk.DISABLED)
        if self.root.winfo_exists(): self.root.after(0, _update_main_window)
        if on_overlay and hasattr(self, 'overlay_window') and self.overlay_window:
            overlay_text = text.replace("\n---\n", "").strip()
            if not overlay_text: overlay_text = self.overlay_window.current_config.get('text', '...')
            self.root.after(0, lambda: self.overlay_window.show_text(overlay_text))

    def on_closing(self):
        if self.is_translating:
            if messagebox.askokcancel("종료 확인", "번역 중입니다. 정말로 종료하시겠습니까?"): self.is_translating = False
            else: return
        self.save_config()
        if hasattr(self, 'overlay_window') and self.overlay_window.winfo_exists(): self.overlay_window.destroy()
        self.root.destroy()

if __name__ == '__main__':
    main_root = tk.Tk()
    app = App(main_root)
    main_root.mainloop()
