# ScreenRegionSelector.py
import tkinter as tk
import platform
import pyautogui

class ScreenRegionSelector(tk.Toplevel):
    def __init__(self, master, callback): # __init__으로 변경
        super().__init__(master)
        self.master = master
        self.callback = callback
        self.start_x = None
        self.start_y = None
        self.rect = None

        # OS 및 화면 크기 확인
        self.os_name = platform.system()
        screen_width, screen_height = pyautogui.size()

        # 화면 전체를 덮는 투명한 창 생성
        self.overrideredirect(True)
        self.geometry(f"{screen_width}x{screen_height}+0+0")
        self.attributes("-alpha", 0.3)  # 투명도 설정
        self.attributes("-topmost", True)

        # 캔버스를 사용하여 영역을 선택
        self.canvas = tk.Canvas(self, cursor="cross", bg="grey")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 마우스 이벤트 바인딩
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # ESC로 취소
        self.bind("<Escape>", self.cancel_selection)

        # 화면 포커스 설정
        self.lift()
        self.focus_force()
        self.grab_set()

    def on_button_press(self, event):
        """마우스 버튼을 누를 때 시작 좌표를 기록"""
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
            self.rect = None

    def on_mouse_drag(self, event):
        """마우스 드래그로 선택 영역을 표시"""
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        if self.start_x is None or self.start_y is None:
            return
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, cur_x, cur_y, outline="red", width=2)

    def on_button_release(self, event):
        """마우스 버튼을 떼면 선택 영역을 반환"""
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        if self.start_x is None or self.start_y is None:
            self.cancel_selection()
            return

        # 마우스 드래그 방향에 관계없이 좌표 정렬
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        width = x2 - x1
        height = y2 - y1

        self.grab_release()
        if width > 5 and height > 5:  # 유효한 영역인지 확인
            self.callback({'left': int(x1), 'top': int(y1), 'width': int(width), 'height': int(height)})
        else:
            self.callback(None)  # 선택이 너무 작으면 None 반환
        self.destroy()

    def cancel_selection(self, event=None):
        """ESC 키를 누르면 선택 영역을 취소"""
        self.grab_release()
        self.callback(None)
        self.destroy()

if __name__ == '__main__':
    # 테스트용 메인 코드
    def on_region_selected_test(region):
        if region:
            print(f"선택된 영역: {region}")
        else:
            print("영역 선택이 취소되었습니다.")
        root.quit() # 테스트 후 종료

    root = tk.Tk()
    root.withdraw()  # 메인 윈도우 숨기기
    selector = ScreenRegionSelector(root, on_region_selected_test)
    root.mainloop()
