# PromptEditPopup.py
import tkinter as tk
from tkinter import ttk, scrolledtext

DEFAULT_PROMPT = "이 이미지의 일본어를 한국어로 번역해줘. 다른 설명이나 마크다운 없이 오직 한국어 번역문만 제공해줘."

class PromptEditPopup(tk.Toplevel):
    def __init__(self, master, current_prompt, callback):
        super().__init__(master)
        self.master = master
        self.callback = callback # 프롬프트 저장 후 호출될 콜백

        self.title("프롬프트 수정")
        self.geometry("500x300")
        self.resizable(True, True) # 크기 조절 가능
        self.grab_set()
        self.focus_force()

        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(main_frame, text="번역 요청 프롬프트:").pack(anchor="w", pady=(0, 5))

        self.prompt_text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=10)
        self.prompt_text_area.insert(tk.END, current_prompt if current_prompt else DEFAULT_PROMPT)
        self.prompt_text_area.pack(expand=True, fill=tk.BOTH, pady=(0, 10))
        self.prompt_text_area.focus()

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)

        save_button = ttk.Button(buttons_frame, text="저장", command=self.save_and_close)
        save_button.pack(side=tk.LEFT, padx=5)

        reset_button = ttk.Button(buttons_frame, text="기본값으로 초기화", command=self.reset_to_default)
        reset_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = ttk.Button(buttons_frame, text="취소", command=self.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5) # 오른쪽 정렬

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        # Enter는 ScrolledText에서 줄바꿈으로 사용되므로 저장 단축키는 다른 것으로 하거나 생략

    def reset_to_default(self):
        self.prompt_text_area.delete('1.0', tk.END)
        self.prompt_text_area.insert(tk.END, DEFAULT_PROMPT)

    def save_and_close(self):
        new_prompt = self.prompt_text_area.get("1.0", tk.END).strip()
        if self.callback:
            self.callback(new_prompt)
        self.destroy()