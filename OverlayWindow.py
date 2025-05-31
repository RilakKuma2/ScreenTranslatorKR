# OverlayWindow.py
import tkinter as tk
from tkinter import font as tkFont

class OverlayWindow(tk.Toplevel):
    def __init__(self, master, initial_config=None):
        super().__init__(master)
        self.master = master

        # 기본 설정
        default_config = {
            'x': 100, 'y': 100, 'width': 300, 'height': 150,
            'font_family': 'Malgun Gothic', 'font_size': 12, 'font_color': '#FFFFFF',
            'bg_color': '#000000', 'alpha': 0.7, 'text': '번역 대기 중...'
        }
        if initial_config:
            default_config.update(initial_config)
        self.current_config = default_config

        # 창 기본 설정
        self.overrideredirect(True)  # 창 테두리 및 제목 표시줄 제거
        self.attributes("-topmost", True) # 항상 위에 표시
        self.set_alpha(self.current_config['alpha'])
        self.geometry(f"{self.current_config['width']}x{self.current_config['height']}+{self.current_config['x']}+{self.current_config['y']}")

        # 텍스트 표시 레이블
        self.label_font = tkFont.Font(family=self.current_config['font_family'], size=self.current_config['font_size'])
        self.text_label = tk.Label(
            self,
            text=self.current_config['text'],
            font=self.label_font,
            fg=self.current_config['font_color'],
            bg=self.current_config['bg_color'],
            wraplength=self.current_config['width'] - 20 # 여백 고려
        )
        self.text_label.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # 창 이동을 위한 변수 및 이벤트 바인딩
        self._offset_x = 0
        self._offset_y = 0
        self.text_label.bind("<ButtonPress-1>", self.on_window_press)
        self.text_label.bind("<B1-Motion>", self.on_window_drag)
        # 창 전체에 대한 드래그도 가능하게 하려면 self.bind 사용
        self.bind("<ButtonPress-1>", self.on_window_press)
        self.bind("<B1-Motion>", self.on_window_drag)


        # 창 크기 조절 핸들 (우측 하단)
        self.resize_handle = tk.Frame(self, bg="gray", cursor="sizing") # 눈에 보이게 하려면 색상 지정
        self.resize_handle.place(relx=1.0, rely=1.0, anchor="se", width=15, height=15)

        self._resize_start_width = 0
        self._resize_start_height = 0
        self._resize_press_x = 0
        self._resize_press_y = 0

        self.resize_handle.bind("<ButtonPress-1>", self.on_resize_press)
        self.resize_handle.bind("<B1-Motion>", self.on_resize_drag)
        self.resize_handle.bind("<ButtonRelease-1>", self.on_resize_release) # 크기 조절 후 설정 저장

        self.withdraw() # 처음에는 숨김

    def show_text(self, text):
        self.current_config['text'] = text
        self.text_label.config(text=text)
        self.update_wraplength()
        if not self.winfo_viewable():
            self.deiconify()

    def hide(self):
        self.withdraw()
        self.save_geometry_to_config() # 숨길 때 현재 위치/크기 저장

    def set_alpha(self, alpha_value):
        self.current_config['alpha'] = float(alpha_value)
        try:
            self.attributes("-alpha", self.current_config['alpha'])
        except tk.TclError:
            print("알파 채널 설정 실패 (일부 OS에서는 지원하지 않을 수 있습니다)")


    def update_appearance(self, font_family, font_size, font_color, bg_color, alpha):
        self.current_config.update({
            'font_family': font_family, 'font_size': int(font_size),
            'font_color': font_color, 'bg_color': bg_color
        })
        self.label_font.config(family=self.current_config['font_family'], size=self.current_config['font_size'])
        self.text_label.config(
            font=self.label_font,
            fg=self.current_config['font_color'],
            bg=self.current_config['bg_color']
        )
        self.set_alpha(alpha)
        self.update_wraplength()


    def update_wraplength(self):
        # 레이블의 wraplength를 현재 창 너비에 맞게 조절
        new_wraplength = self.winfo_width() - 20 # 양쪽 여백 10px씩 고려
        if new_wraplength < 1: new_wraplength = 1 # 최소값
        self.text_label.config(wraplength=new_wraplength)


    def on_window_press(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def on_window_drag(self, event):
        x = self.winfo_x() + event.x - self._offset_x
        y = self.winfo_y() + event.y - self._offset_y
        self.geometry(f"+{x}+{y}")

    def on_resize_press(self, event):
        self._resize_start_width = self.winfo_width()
        self._resize_start_height = self.winfo_height()
        self._resize_press_x = event.x_root
        self._resize_press_y = event.y_root
        # 드래그 중에는 부모 창의 업데이트를 막기 위해 grab_set 시도 (선택 사항)
        # self.grab_set()


    def on_resize_drag(self, event):
        delta_width = event.x_root - self._resize_press_x
        delta_height = event.y_root - self._resize_press_y
        new_width = self._resize_start_width + delta_width
        new_height = self._resize_start_height + delta_height

        # 최소 크기 제한
        new_width = max(80, new_width)  # 최소 너비
        new_height = max(40, new_height) # 최소 높이

        self.geometry(f"{new_width}x{new_height}")
        self.update_wraplength() # 크기 변경 시 wraplength 업데이트

    def on_resize_release(self, event):
        # self.grab_release() # grab_set 사용 시
        self.save_geometry_to_config() # 크기 조절 완료 후 위치/크기 저장

    def save_geometry_to_config(self):
        if self.winfo_exists(): # 창이 존재할 때만
            self.current_config['x'] = self.winfo_x()
            self.current_config['y'] = self.winfo_y()
            self.current_config['width'] = self.winfo_width()
            self.current_config['height'] = self.winfo_height()
            # print(f"Overlay geometry saved: {self.current_config}") # 디버깅용

    def get_current_config(self):
        self.save_geometry_to_config() # 최신 지오메트리 반영
        return self.current_config

    def apply_config(self, config_dict):
        self.current_config.update(config_dict)
        self.geometry(f"{self.current_config['width']}x{self.current_config['height']}+{self.current_config['x']}+{self.current_config['y']}")
        self.update_appearance(
            self.current_config['font_family'],
            self.current_config['font_size'],
            self.current_config['font_color'],
            self.current_config['bg_color'],
            self.current_config['alpha']
        )
        self.show_text(self.current_config.get('text', ''))
