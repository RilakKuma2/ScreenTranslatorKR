# app.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, colorchooser, font as tkFont
import configparser
import threading
import time
import pyautogui
from PIL import Image, ImageOps # ImageOps for potential better resizing
import io
import google.generativeai as genai
from ScreenRegionSelector import ScreenRegionSelector
from OverlayWindow import OverlayWindow
from ApiKeyPopup import ApiKeyPopup # API 키 팝업 import

CONFIG_FILE = 'transconfig.ini'
GEMINI_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("실시간 화면 번역기")
        # GUI 크기 조절 (리사이징 옵션 공간)
        self.root.geometry("550x850") # 세로 약간 더 증가

        # API 설정 (StringVar은 유지, Entry는 제거)
        self.api_key = tk.StringVar() # API 키는 내부적으로만 관리
        self.selected_model = tk.StringVar(value=GEMINI_MODELS[0])
        self.selected_region = None
        self.is_translating = False
        self.translation_thread = None
        self.gemini_client = None

        # 번역 주기 설정
        self.translation_interval = tk.DoubleVar(value=0.5)

        # --- 이미지 리사이징 설정 변수 ---
        self.use_resize = tk.BooleanVar(value=False) # 리사이징 사용 여부
        self.resize_percentage = tk.IntVar(value=50) # 리사이징 비율 (기본 50%)

        # 오버레이 창 설정
        self.overlay_font_family = tk.StringVar(value='Malgun Gothic')
        self.overlay_font_size = tk.IntVar(value=40)
        self.overlay_font_color = tk.StringVar(value='#FFFFFF')
        self.overlay_bg_color = tk.StringVar(value='#000000')
        self.overlay_alpha = tk.DoubleVar(value=0.7)

        self.load_config() # API 키 포함 모든 설정 로드

        overlay_initial_cfg = { # ... (이전과 동일) ...
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
        settings_frame = ttk.LabelFrame(root, text="번역 설정", padding=10) # "API 및" 제거
        settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        image_process_frame = ttk.LabelFrame(root, text="이미지 처리 설정", padding=10)
        image_process_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        overlay_settings_frame = ttk.LabelFrame(root, text="오버레이 창 설정", padding=10)
        overlay_settings_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew") # row 변경

        translation_output_frame = ttk.LabelFrame(root, text="번역 결과 (메인 창)", padding=10)
        translation_output_frame.grid(row=3, column=0, padx=10, pady=10, sticky="nsew") # row 변경

        # --- 번역 설정 GUI ---
        # API 키 설정 버튼
        self.api_key_button = ttk.Button(settings_frame, text="Gemini API 키 설정", command=self.open_api_key_popup)
        self.api_key_button.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        self.api_key_status_label = ttk.Label(settings_frame, text="API 키: " + ("설정됨" if self.api_key.get() else "미설정"))
        self.api_key_status_label.grid(row=0, column=3, padx=5, pady=5, sticky="w") # API 키 상태 표시


        ttk.Label(settings_frame, text="Gemini 모델:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.model_menu = ttk.OptionMenu(settings_frame, self.selected_model, self.selected_model.get(), *GEMINI_MODELS)
        self.model_menu.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

        ttk.Label(settings_frame, text="번역 주기 (초):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.interval_spinbox = ttk.Spinbox(
            settings_frame, from_=0.2, to=10.0, increment=0.1, textvariable=self.translation_interval, width=8
        )
        self.interval_spinbox.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.select_region_button = ttk.Button(settings_frame, text="번역 영역 지정", command=self.open_region_selector)
        self.select_region_button.grid(row=3, column=0, columnspan=4, padx=5, pady=10, sticky="ew")

        self.region_label = ttk.Label(settings_frame, text="선택된 영역: 없음")
        self.region_label.grid(row=4, column=0, columnspan=4, padx=5, pady=2, sticky="w")

        self.start_button = ttk.Button(settings_frame, text="번역 시작", command=self.start_translation, state=tk.DISABLED)
        self.start_button.grid(row=5, column=0, padx=5, pady=10, sticky="ew")
        self.stop_button = ttk.Button(settings_frame, text="번역 중지", command=self.stop_translation, state=tk.DISABLED)
        self.stop_button.grid(row=5, column=1, padx=5, pady=10, sticky="ew")
        self.show_overlay_button = ttk.Button(settings_frame, text="오버레이 표시/숨김", command=self.toggle_overlay_visibility)
        self.show_overlay_button.grid(row=5, column=2, padx=5, pady=10, sticky="ew")

        settings_frame.grid_columnconfigure(1, weight=1)


        # --- 이미지 처리 설정 GUI ---
        self.resize_checkbutton = ttk.Checkbutton(
            image_process_frame, text="이미지 리사이징 사용", variable=self.use_resize,
            command=self.toggle_resize_options_state
        )
        self.resize_checkbutton.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(image_process_frame, text="리사이징 비율 (%):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.resize_spinbox = ttk.Spinbox(
            image_process_frame, from_=10, to=100, increment=5, textvariable=self.resize_percentage, width=8,
            state=tk.DISABLED # 초기에는 비활성화
        )
        self.resize_spinbox.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        image_process_frame.grid_columnconfigure(1, weight=1)


        # --- 오버레이 창 설정 GUI 요소 (이전과 동일) ---
        # ... (이전 코드 유지) ...
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

        # Translated Text Display (메인 창)
        self.translated_text_area = scrolledtext.ScrolledText(translation_output_frame, wrap=tk.WORD, height=10)
        self.translated_text_area.pack(fill=tk.BOTH, expand=True)
        self.translated_text_area.config(state=tk.DISABLED)

        # Grid Sizing
        root.grid_columnconfigure(0, weight=1)
        overlay_settings_frame.grid_columnconfigure(1, weight=1)
        overlay_settings_frame.grid_columnconfigure(3, weight=1)
        root.grid_rowconfigure(3, weight=1) # 번역 결과 영역 (row 인덱스 변경)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_start_button_state()
        self.apply_overlay_settings()
        self.toggle_resize_options_state() # 초기 로드 시 리사이징 옵션 상태 반영

    def open_api_key_popup(self):
        ApiKeyPopup(self.root, self.api_key.get(), self.save_api_key_from_popup)

    def save_api_key_from_popup(self, new_key):
        self.api_key.set(new_key)
        self.api_key_status_label.config(text="API 키: " + ("설정됨" if new_key else "미설정"))
        self.update_start_button_state() # API 키 변경 시 시작 버튼 상태 업데이트
        self.save_config() # 변경된 API 키를 즉시 저장
        print("API 키가 업데이트되었습니다.")


    def toggle_resize_options_state(self):
        if self.use_resize.get():
            self.resize_spinbox.config(state=tk.NORMAL)
        else:
            self.resize_spinbox.config(state=tk.DISABLED)


    def choose_color(self, target): # ... (이전과 동일) ...
        color_code = colorchooser.askcolor(title=f"{target} 색상 선택")
        if color_code and color_code[1]:
            if target == 'font':
                self.overlay_font_color.set(color_code[1])
                self.font_color_preview.config(bg=color_code[1])
            elif target == 'bg':
                self.overlay_bg_color.set(color_code[1])
                self.bg_color_preview.config(bg=color_code[1])
            self.apply_overlay_settings()

    def apply_overlay_settings(self): # ... (이전과 동일) ...
        if hasattr(self, 'overlay_window') and self.overlay_window:
            try:
                font_size = self.overlay_font_size.get()
                alpha = self.overlay_alpha.get()
                self.overlay_window.update_appearance(
                    self.overlay_font_family.get(), font_size,
                    self.overlay_font_color.get(), self.overlay_bg_color.get(), alpha
                )
                self.font_color_preview.config(bg=self.overlay_font_color.get())
                self.bg_color_preview.config(bg=self.overlay_bg_color.get())
            except tk.TclError as e: print(f"오버레이 설정 적용 중 오류: {e}")


    def load_config(self):
        config = configparser.ConfigParser()
        self.overlay_x, self.overlay_y, self.overlay_width, self.overlay_height = 100, 100, 1200, 250

        if config.read(CONFIG_FILE):
            # Gemini 설정
            self.api_key.set(config.get('Gemini', 'api_key', fallback='')) # API 키 로드
            saved_model = config.get('Gemini', 'model', fallback=GEMINI_MODELS[0])
            self.selected_model.set(saved_model if saved_model in GEMINI_MODELS else GEMINI_MODELS[0])
            self.translation_interval.set(config.getfloat('Gemini', 'interval', fallback=1.0))

            # 이미지 처리 설정 로드
            self.use_resize.set(config.getboolean('ImageProcessing', 'use_resize', fallback=False))
            self.resize_percentage.set(config.getint('ImageProcessing', 'resize_percentage', fallback=50))

            # 오버레이 설정 로드
            # ... (이전과 동일) ...
            self.overlay_font_family.set(config.get('Overlay', 'font_family', fallback='Malgun Gothic'))
            self.overlay_font_size.set(config.getint('Overlay', 'font_size', fallback=40))
            self.overlay_font_color.set(config.get('Overlay', 'font_color', fallback='#FFFFFF'))
            self.overlay_bg_color.set(config.get('Overlay', 'bg_color', fallback='#000000'))
            self.overlay_alpha.set(config.getfloat('Overlay', 'alpha', fallback=0.7))
            self.overlay_x = config.getint('Overlay', 'x', fallback=100)
            self.overlay_y = config.getint('Overlay', 'y', fallback=100)
            self.overlay_width = config.getint('Overlay', 'width', fallback=1200)
            self.overlay_height = config.getint('Overlay', 'height', fallback=400)
        else:
            self.save_config()

        # API 키 상태 레이블 초기 업데이트
        if hasattr(self, 'api_key_status_label'): # GUI 생성 후 호출되도록
            self.api_key_status_label.config(text="API 키: " + ("설정됨" if self.api_key.get() else "미설정"))


    def save_config(self):
        config = configparser.ConfigParser()
        config['Gemini'] = {
            'api_key': self.api_key.get(), # API 키 저장
            'model': self.selected_model.get(),
            'interval': round(self.translation_interval.get(), 2)
        }
        config['ImageProcessing'] = { # 이미지 처리 섹션 추가
            'use_resize': self.use_resize.get(),
            'resize_percentage': self.resize_percentage.get()
        }
        # 오버레이 설정 저장
        # ... (이전과 동일) ...
        overlay_cfg_to_save = {}
        if hasattr(self, 'overlay_window') and self.overlay_window:
             overlay_current_geom_cfg = self.overlay_window.get_current_config()
             overlay_cfg_to_save = {
                'font_family': self.overlay_font_family.get(), 'font_size': self.overlay_font_size.get(),
                'font_color': self.overlay_font_color.get(), 'bg_color': self.overlay_bg_color.get(),
                'alpha': round(self.overlay_alpha.get(), 2), 'x': overlay_current_geom_cfg['x'],
                'y': overlay_current_geom_cfg['y'], 'width': overlay_current_geom_cfg['width'],
                'height': overlay_current_geom_cfg['height']
            }
        else:
            overlay_cfg_to_save = {
                'font_family': self.overlay_font_family.get(), 'font_size': self.overlay_font_size.get(),
                'font_color': self.overlay_font_color.get(), 'bg_color': self.overlay_bg_color.get(),
                'alpha': round(self.overlay_alpha.get(), 2), 'x': self.overlay_x, 'y': self.overlay_y,
                'width': self.overlay_width, 'height': self.overlay_height
            }
        config['Overlay'] = overlay_cfg_to_save

        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        print("설정이 저장되었습니다.")


    def open_region_selector(self): # ... (이전과 동일) ...
        self.root.withdraw(); ScreenRegionSelector(self.root, self.on_region_selected)

    def on_region_selected(self, region): # ... (이전과 동일) ...
        self.root.deiconify(); self.root.focus_force()
        if region:
            self.selected_region = region
            self.region_label.config(text=f"선택된 영역: X={region['left']}, Y={region['top']}, W={region['width']}, H={region['height']}")
        else:
            self.selected_region = None; self.region_label.config(text="선택된 영역: 없음 (취소됨)")
        self.update_start_button_state()

    def update_start_button_state(self):
        # API 키가 설정되어 있는지 확인하는 조건 추가
        can_start = self.api_key.get() and self.selected_region and not self.is_translating
        self.start_button.config(state=tk.NORMAL if can_start else tk.DISABLED)

        # API 키 상태 레이블 업데이트
        if hasattr(self, 'api_key_status_label'):
            self.api_key_status_label.config(text="API 키: " + ("설정됨" if self.api_key.get() else "미설정"))

        if self.is_translating:
            self.stop_button.config(state=tk.NORMAL)
            # 번역 중 비활성화할 컨트롤들
            for widget in [self.select_region_button, self.api_key_button, # api_key_entry 제거됨
                           self.model_menu, self.interval_spinbox,
                           self.resize_checkbutton, self.resize_spinbox]:
                if widget: widget.config(state=tk.DISABLED)
        else:
            self.stop_button.config(state=tk.DISABLED)
            # 번역 중지 시 활성화할 컨트롤들
            for widget in [self.select_region_button, self.api_key_button,
                           self.model_menu, self.interval_spinbox,
                           self.resize_checkbutton]: # resize_spinbox는 체크박스 상태에 따라 결정
                if widget: widget.config(state=tk.NORMAL)
            self.toggle_resize_options_state() # 리사이즈 스핀박스 상태는 체크박스에 따라 다시 설정


    def toggle_overlay_visibility(self): # ... (이전과 동일) ...
        if self.overlay_window.winfo_viewable(): self.overlay_window.hide()
        else:
            self.apply_overlay_settings()
            self.overlay_window.show_text(self.overlay_window.current_config.get('text', '번역 대기 중...'))


    def start_translation(self):
        if not self.api_key.get(): messagebox.showerror("오류", "Gemini API 키를 먼저 설정해주세요."); return
        if not self.selected_region: messagebox.showerror("오류", "번역할 화면 영역을 먼저 지정해주세요."); return

        self.save_config()
        try:
            genai.configure(api_key=self.api_key.get())
            self.gemini_client = genai.GenerativeModel(self.selected_model.get())
        except Exception as e:
            messagebox.showerror("API 오류", f"Gemini 클라이언트 초기화 실패: {e}"); return

        self.is_translating = True
        self.update_start_button_state()
        # ... (메인 창, 오버레이 창 초기화 동일) ...
        self.translated_text_area.config(state=tk.NORMAL); self.translated_text_area.delete('1.0', tk.END)
        self.translated_text_area.insert(tk.END, "번역을 시작합니다...\n"); self.translated_text_area.config(state=tk.DISABLED)
        self.apply_overlay_settings(); self.overlay_window.show_text("번역 준비 중...")

        self.translation_thread = threading.Thread(target=self.translation_loop, daemon=True)
        self.translation_thread.start()

    def stop_translation(self): # ... (이전과 동일) ...
        self.is_translating = False; self.update_start_button_state()
        self.update_translated_text("번역이 중지되었습니다.\n", on_overlay=True)
        if self.overlay_window: self.overlay_window.show_text("번역 중지됨")


    def translation_loop(self):
        prompt = "이 이미지의 일본어를 한국어로 번역해줘. 다른 설명이나 마크다운 없이 오직 한국어 번역문만 제공해줘."
        last_image_hash = None
        no_change_count = 0
        current_interval = self.translation_interval.get()
        if current_interval <= 0: current_interval = 0.2

        # 리사이징 설정값 가져오기 (스레드 시작 시 한 번)
        should_resize = self.use_resize.get()
        resize_percent = self.resize_percentage.get() / 100.0 # 0.0 ~ 1.0 사이 값으로

        while self.is_translating:
            if not self.selected_region: break
            try:
                screenshot_pil = pyautogui.screenshot(region=(
                    self.selected_region['left'], self.selected_region['top'],
                    self.selected_region['width'], self.selected_region['height']
                ))
                if screenshot_pil.mode == 'RGBA':
                    screenshot_pil = screenshot_pil.convert('RGB')

                # --- 이미지 리사이징 로직 ---
                if should_resize and resize_percent > 0 and resize_percent < 1.0:
                    original_width, original_height = screenshot_pil.size
                    new_width = int(original_width * resize_percent)
                    new_height = int(original_height * resize_percent)
                    if new_width > 0 and new_height > 0: # 유효한 크기일 때만 리사이징
                        screenshot_pil = screenshot_pil.resize((new_width, new_height), Image.LANCZOS) # 고품질 리사이징
                        print(f"이미지 리사이징됨: {original_width}x{original_height} -> {new_width}x{new_height}")

                current_image_hash = hash(screenshot_pil.tobytes())
                if current_image_hash == last_image_hash:
                    no_change_count += 1
                    if no_change_count >= 3: time.sleep(current_interval); continue
                else:
                    last_image_hash = current_image_hash; no_change_count = 0

                img_byte_arr = io.BytesIO()
                screenshot_pil.save(img_byte_arr, format='JPEG')
                img_bytes = img_byte_arr.getvalue()
                image_parts = [{"mime_type": "image/jpeg", "data": img_bytes}]

                if self.gemini_client:
                    response = self.gemini_client.generate_content([prompt] + image_parts, stream=False)
                    # ... (응답 처리 동일) ...
                    translated_text = "번역 실패"
                    if response.parts: translated_text = response.text.strip()
                    elif response.prompt_feedback and response.prompt_feedback.block_reason:
                        translated_text = f"차단됨: {response.prompt_feedback.block_reason_message}"
                    elif not response.candidates: translated_text = "응답 후보 없음"
                    self.update_translated_text(translated_text + "\n---\n", on_overlay=True)

                time.sleep(current_interval)

            except Exception as e: # ... (에러 처리 동일) ...
                error_message = f"번역 중 오류: {type(e).__name__} - {e}\n"
                print(error_message); self.update_translated_text(error_message, on_overlay=True)
                if "resource_exhausted" in str(e).lower() or "rate limit" in str(e).lower():
                    self.update_translated_text("API 사용량 제한. 잠시 후 재시도.\n", on_overlay=True)
                    time.sleep(max(30.0, current_interval * 5))
                else: time.sleep(max(2.0, current_interval))
        print("번역 루프 종료.")

    def update_translated_text(self, text, on_overlay=False): # ... (이전과 동일) ...
        def _update_main_window():
            if self.translated_text_area.winfo_exists():
                self.translated_text_area.config(state=tk.NORMAL); self.translated_text_area.insert(tk.END, text)
                self.translated_text_area.see(tk.END); self.translated_text_area.config(state=tk.DISABLED)
        if self.root.winfo_exists(): self.root.after(0, _update_main_window)
        if on_overlay and hasattr(self, 'overlay_window') and self.overlay_window:
            overlay_text = text.replace("\n---\n", "").strip()
            if not overlay_text: overlay_text = self.overlay_window.current_config.get('text', '...')
            self.root.after(0, lambda: self.overlay_window.show_text(overlay_text))


    def on_closing(self): # ... (이전과 동일) ...
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
