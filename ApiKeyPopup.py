# ApiKeyPopup.py
import tkinter as tk
from tkinter import ttk
import webbrowser # 하이퍼링크용

class ApiKeyPopup(tk.Toplevel):
    def __init__(self, master, current_api_key, callback):
        super().__init__(master)
        self.master = master
        self.current_api_key_var = tk.StringVar(value=current_api_key)
        self.callback = callback # API 키 저장 후 호출될 콜백

        self.title("Gemini API 키 설정")
        self.geometry("400x150")
        self.resizable(False, False)
        self.grab_set() # 팝업창이 떠있는 동안 다른 창 비활성화
        self.focus_force() # 팝업창에 포커스

        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(main_frame, text="Gemini API Key:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.api_key_entry = ttk.Entry(main_frame, textvariable=self.current_api_key_var, width=40, show="*") # 입력값 가리기
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.api_key_entry.focus() # 입력창에 바로 포커스

        # API 발급 링크
        link_label = ttk.Label(main_frame, text="API 발급 (Google AI Studio)", foreground="blue", cursor="hand2")
        link_label.grid(row=1, column=0, columnspan=2, padx=5, pady=10)
        link_label.bind("<Button-1>", lambda e: self.open_link("https://aistudio.google.com/app/apikey"))

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=10)

        save_button = ttk.Button(buttons_frame, text="저장", command=self.save_and_close)
        save_button.pack(side=tk.LEFT, padx=5)
        cancel_button = ttk.Button(buttons_frame, text="취소", command=self.destroy)
        cancel_button.pack(side=tk.LEFT, padx=5)

        main_frame.grid_columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy) # X 버튼으로 닫을 때

        # Enter 키로 저장
        self.bind("<Return>", lambda event: self.save_and_close())
        # ESC 키로 취소
        self.bind("<Escape>", lambda event: self.destroy())


    def open_link(self, url):
        webbrowser.open_new_tab(url)

    def save_and_close(self):
        new_api_key = self.current_api_key_var.get()
        if self.callback:
            self.callback(new_api_key) # 콜백 함수 호출하여 부모 창에 API 키 전달
        self.destroy()
