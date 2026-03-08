import ctypes
import concurrent.futures
import multiprocessing
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

def configure_tcl_tk_early() -> None:
    if not (getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")):
        return
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return
    base_dir = Path(__file__).resolve().parent
    tcl_dir = base_dir / "tcl8.6"
    tk_dir = base_dir / "tk8.6"
    if tcl_dir.exists():
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if tk_dir.exists():
        os.environ["TK_LIBRARY"] = str(tk_dir)


configure_tcl_tk_early()

import tkinter as tk
from tkinter import filedialog, messagebox


def load_cover_bytes(path: str, width: int, height: int) -> Optional[bytes]:
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        with Image.open(path) as img:
            try:
                img.draft("RGB", (width, height))
            except Exception:
                pass
            img = img.convert("RGB")
            src_w, src_h = img.size
            if src_w <= 0 or src_h <= 0:
                return None
            scale = max(width / src_w, height / src_h)
            new_w = max(int(round(src_w * scale)), 1)
            new_h = max(int(round(src_h * scale)), 1)
            if new_w != src_w or new_h != src_h:
                img = img.resize((new_w, new_h), Image.BILINEAR)
            left = max((new_w - width) // 2, 0)
            top = max((new_h - height) // 2, 0)
            right = left + width
            bottom = top + height
            img = img.crop((left, top, right, bottom))
            return img.tobytes()
    except Exception:
        return None

# Nuitka build:
# Startup note: sub-100ms startup on Windows is not realistic with --onefile,
# because extraction happens before Python code runs. Use --standalone for low latency.
# python -m nuitka ^
#   --onefile ^
#   --onefile-cache-mode=cached ^
#   --onefile-tempdir-spec="{PROGRAM_DIR}\.myapp_cache" ^
#   --windows-console-mode=disable ^
#   --enable-plugin=tk-inter ^
#   --include-data-file=mumuxiao.png=mumuxiao.png ^
#   --include-data-dir=".\tcl8.6"=tcl8.6 ^
#   --include-data-dir=".\tk8.6"=tk8.6 ^
#   --windows-icon-from-ico=mumuxiao.ico ^
#   main.py

# python -m nuitka ^
#   --standalone ^
#   --windows-console-mode=disable ^
#   --enable-plugin=tk-inter ^
#   --include-data-file=mumuxiao.png=mumuxiao.png ^
#   --include-data-dir=".\tcl8.6"=tcl8.6 ^
#   --include-data-dir=".\tk8.6"=tk8.6 ^
#   --windows-icon-from-ico=mumuxiao.ico ^
#   main.py





class PatternApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Pattern Test")
        self.pattern = "none"
        self.gray_level = 127
        self.gray_mode = "white"
        self.vline_mode = "1line"
        self.hline_mode = "1line"
        self.monitors = []
        self.monitor_index = 0
        self.last_monitor_switch = 0.0
        self.switch_cooldown = 0.3
        self.tab_down = False
        self.show_hud = True
        self.crosshair_enabled = False
        self.crosshair_mode = "cross"
        self.crosshair_x = 0
        self.crosshair_y = 0
        self.crosshair_color_mode = "white"
        self.taskbar_window = None
        self.flip_mode = "none"
        self.pattern_width = 0
        self.pattern_height = 0
        self.checker_level = 255
        self.checker_mode = "white"
        self.checker_start = time.monotonic()
        self.checker_sizes = [2, 4, 5, 8, 16, 32, 64]
        self.checker_size_index = 3
        self.gradient_steps = 256
        self.image_path = None
        self.loaded_image = None
        self.image_cache_key = None
        self.image_flip_warning_shown = False
        self.crosshair_overlay_ids = []
        self.dot_pil = None
        self.dot_photo = None
        self.dot_cache_key = None
        self.pattern_base_pil = None
        self.pattern_base_key = None
        self.pattern_photo = None
        self.last_pil = None
        self.bicolor_mask_cache = {}
        self.align_pil = None
        self.align_photo = None
        self.align_cache_key = None
        self.crosstalk_bg_level = 127
        self.crosstalk_block_level = 0
        self.crosstalk_rect = None
        self.crosstalk_initialized = False
        self.crosstalk_bg_image_path = None
        self.crosstalk_block_image_path = None
        self.crosstalk_bg_cache_key = None
        self.crosstalk_block_cache_key = None
        self.crosstalk_bg_pil = None
        self.crosstalk_block_pil = None
        self.crosstalk_bg_loading = False
        self.crosstalk_block_loading = False
        self.crosstalk_bg_load_token = 0
        self.crosstalk_block_load_token = 0
        self.crosstalk_executor: Optional[concurrent.futures.Executor] = None
        self.crosstalk_bg_photo = None
        self.crosstalk_block_photo = None
        self.crosstalk_bg_photo_key = None
        self.crosstalk_block_photo_key = None
        self.crosstalk_block_image_id = None

        self.root.overrideredirect(True)
        self.root.bind("<Escape>", self.exit_app)
        self.root.bind("<KeyPress-Tab>", self.on_tab_press)
        self.root.bind("<KeyRelease-Tab>", self.on_tab_release)
        self.icon_image = None
        self.icon_path = self.resource_path("mumuxiao.png")
        self.root.bind("<Control-s>", self.save_pattern)

        self.canvas = tk.Canvas(root, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.on_resize)

        self.menu = tk.Menu(root, tearoff=0)
        self.gray_h_menu = tk.Menu(self.menu, tearoff=0)
        self.gray_v_menu = tk.Menu(self.menu, tearoff=0)
        self.gray_center_menu = tk.Menu(self.menu, tearoff=0)
        self.vline_menu = tk.Menu(self.menu, tearoff=0)
        self.hline_menu = tk.Menu(self.menu, tearoff=0)

        self.root.bind("<Button-3>", self.show_menu)
        self.root.bind("<Button-2>", self.show_menu)
        self.root.bind("<KeyPress>", self.on_key)

        self.image = None
        self.image_id = None
        self.image_size = (0, 0)
        self.text_id = None
        self.hud_rect_id = None

        self.draw()
        self.root.after_idle(self.finish_startup)
        self.root.after(100, self.on_tick)

    def finish_startup(self) -> None:
        self.load_icon()
        self.build_menu()
        self.monitors = self.get_monitors()
        self.apply_monitor(self.monitor_index)
        self.root.after(200, self.configure_taskbar)

    def build_menu(self) -> None:
        self.menu.delete(0, "end")
        self.gray_h_menu.delete(0, "end")
        self.gray_v_menu.delete(0, "end")
        self.gray_center_menu.delete(0, "end")
        self.vline_menu.delete(0, "end")
        self.hline_menu.delete(0, "end")

        self.menu.add_command(label="Grayscale", command=lambda: self.set_pattern("grayscale"))
        self.menu.add_command(label="Checkerboard", command=lambda: self.set_pattern("checkerboard"))
        self.menu.add_command(label="Align", command=lambda: self.set_pattern("align"))
        self.menu.add_command(label="Image", command=self.open_image)
        for steps in (9, 64, 256):
            self.gray_h_menu.add_command(
                label=str(steps),
                command=lambda s=steps: self.set_gradient("gray_h", s),
            )
        self.menu.add_cascade(label="Horizontal grayscale", menu=self.gray_h_menu)
        for steps in (9, 64, 256):
            self.gray_v_menu.add_command(
                label=str(steps),
                command=lambda s=steps: self.set_gradient("gray_v", s),
            )
        self.menu.add_cascade(label="Vertical grayscale", menu=self.gray_v_menu)
        for steps in (9, 64, 256):
            self.gray_center_menu.add_command(
                label=str(steps),
                command=lambda s=steps: self.set_gradient("gray_center", s),
            )
        self.menu.add_cascade(label="Center grayscale", menu=self.gray_center_menu)
        self.vline_menu.add_command(label="1line", command=lambda: self.set_vline_mode("1line"))
        self.vline_menu.add_command(label="2line", command=lambda: self.set_vline_mode("2line"))
        self.vline_menu.add_command(label="subline", command=lambda: self.set_vline_mode("subline"))
        self.menu.add_cascade(label="Vertical line", menu=self.vline_menu)
        self.hline_menu.add_command(label="1line", command=lambda: self.set_hline_mode("1line"))
        self.hline_menu.add_command(label="2line", command=lambda: self.set_hline_mode("2line"))
        self.menu.add_cascade(label="Horizontal line", menu=self.hline_menu)
        self.menu.add_command(label="1dot", command=lambda: self.set_pattern("1dot"))
        self.menu.add_command(label="2dot", command=lambda: self.set_pattern("2dot"))
        self.menu.add_command(label="sub dot", command=lambda: self.set_pattern("subdot"))
        self.menu.add_command(label="CrossTalk", command=lambda: self.set_pattern("crosstalk"))
        self.menu.add_command(label="one third", command=lambda: self.set_pattern("one_third"))

    def ensure_crosstalk_executor(self) -> concurrent.futures.Executor:
        if self.crosstalk_executor is None:
            self.crosstalk_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="crosstalk",
            )
        return self.crosstalk_executor

    def exit_app(self, event: Optional[tk.Event] = None) -> None:
        if self.crosstalk_executor is not None:
            try:
                self.crosstalk_executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
        self.root.destroy()

    def on_tab_press(self, event: Optional[tk.Event] = None) -> None:
        if self.tab_down:
            return
        self.tab_down = True
        self.next_monitor()

    def on_tab_release(self, event: Optional[tk.Event] = None) -> None:
        self.tab_down = False

    def next_monitor(self) -> None:
        now = time.monotonic()
        if now - self.last_monitor_switch < self.switch_cooldown:
            return
        self.last_monitor_switch = now
        self.monitors = self.get_monitors()
        if not self.monitors:
            return
        self.monitor_index = (self.monitor_index + 1) % len(self.monitors)
        self.apply_monitor(self.monitor_index)

    def apply_monitor(self, index: int) -> None:
        x, y, width, height = self.monitors[index]
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.update_idletasks()
        self.root.lift()
        self.root.focus_force()
        self.draw()

    def configure_taskbar(self) -> None:
        if self.taskbar_window is not None:
            return
        self.taskbar_window = tk.Toplevel(self.root)
        self.taskbar_window.title("Pattern Test")
        if self.icon_image is not None:
            self.taskbar_window.iconphoto(True, self.icon_image)
        self.taskbar_window.geometry("200x100+0+0")
        self.taskbar_window.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.taskbar_window.bind("<Map>", self.on_taskbar_restore)
        self.taskbar_window.iconify()

    def resource_path(self, name: str) -> str:
        return str(Path(__file__).resolve().parent / name)

    def load_icon(self) -> None:
        try:
            self.icon_image = tk.PhotoImage(file=self.icon_path)
            self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            self.icon_image = None

    def on_taskbar_restore(self, event: Optional[tk.Event] = None) -> None:
        self.root.lift()
        self.root.focus_force()
        if self.taskbar_window is not None:
            self.taskbar_window.after(0, self.taskbar_window.iconify)

    def show_menu(self, event: tk.Event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def save_pattern(self, event: Optional[tk.Event] = None) -> None:
        prev_show_hud = self.show_hud
        self.show_hud = True
        self.draw()
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            title="Save Pattern As",
        )
        if not filename:
            self.show_hud = prev_show_hud
            self.draw()
            return
        try:
            if self.pattern == "crosstalk":
                img = self.build_crosstalk_pil()
                if img is not None:
                    img.save(filename, format="PNG")
                else:
                    self.image.write(filename, format="png")
            elif self.last_pil is not None:
                self.last_pil.save(filename, format="PNG")
            elif self.pattern in ("1dot", "2dot") and self.dot_pil is not None:
                self.dot_pil.save(filename, format="PNG")
            elif self.pattern == "align" and self.align_pil is not None:
                self.align_pil.save(filename, format="PNG")
            elif self.loaded_image is not None:
                self.loaded_image.write(filename, format="png")
            else:
                self.image.write(filename, format="png")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save Failed", f"Unable to save PNG: {exc}")
        finally:
            self.show_hud = prev_show_hud
            self.draw()

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Image",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.image_path = path
        self.loaded_image = None
        self.flip_mode = "none"
        self.pattern = "image"
        self.draw()

    def set_pattern(self, pattern: str) -> None:
        if pattern in ("grayscale", "1dot", "2dot", "subdot") and self.pattern != pattern:
            self.gray_level = 127
        if pattern == "checkerboard" and self.pattern != "checkerboard":
            self.checker_level = 255
            self.checker_mode = "white"
            self.checker_start = time.monotonic()
            self.checker_size_index = 3
        self.flip_mode = "none"
        self.pattern = pattern
        if pattern == "crosstalk" and not self.crosstalk_initialized:
            self.crosstalk_bg_level = 127
            self.crosstalk_block_level = 0
            self.crosstalk_rect = None
            self.crosstalk_bg_image_path = None
            self.crosstalk_block_image_path = None
            self.crosstalk_bg_cache_key = None
            self.crosstalk_block_cache_key = None
            self.crosstalk_bg_pil = None
            self.crosstalk_block_pil = None
            self.crosstalk_initialized = True
        self.draw()

    def set_gradient(self, pattern: str, steps: int) -> None:
        self.gradient_steps = steps
        self.flip_mode = "none"
        self.pattern = pattern
        self.draw()

    def set_vline_mode(self, mode: str) -> None:
        self.vline_mode = mode
        self.gray_level = 127
        self.flip_mode = "none"
        self.pattern = "vline"
        self.draw()

    def set_hline_mode(self, mode: str) -> None:
        self.hline_mode = mode
        self.gray_level = 127
        self.flip_mode = "none"
        self.pattern = "hline"
        self.draw()

    def on_resize(self, event: tk.Event) -> None:
        if event.widget == self.canvas:
            self.draw()

    def ensure_image(self, width: int, height: int) -> None:
        if self.image is None or self.image_size != (width, height):
            self.image = tk.PhotoImage(width=width, height=height)
            self.image_size = (width, height)
            if self.image_id is None:
                self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.image)
        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.image)
        else:
            self.canvas.itemconfig(self.image_id, image=self.image)
        self.image.put("white", to=(0, 0, width, height))

    def draw_image_pattern(self, width: int, height: int) -> None:
        if not self.image_path:
            return
        cache_key = (self.image_path, width, height, self.flip_mode)
        if self.loaded_image is None or self.image_size != (width, height) or self.image_cache_key != cache_key:
            self.loaded_image = self.load_image_scaled(self.image_path, width, height, self.flip_mode)
            self.image_size = (width, height)
            self.image_cache_key = cache_key
        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.loaded_image)
        else:
            self.canvas.itemconfig(self.image_id, image=self.loaded_image)

    def load_image_scaled(self, path: str, width: int, height: int, flip_mode: str) -> tk.PhotoImage:
        try:
            from PIL import Image, ImageTk  # type: ignore[import-not-found]
        except Exception:
            if flip_mode != "none" and not self.image_flip_warning_shown:
                self.image_flip_warning_shown = True
                messagebox.showwarning("Image flip", "Image flip requires Pillow (PIL).")
            return self.scale_image_tk(path, width, height)
        with Image.open(path) as img:
            img = img.convert("RGB")
            if flip_mode == "h":
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif flip_mode == "v":
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            img = img.resize((width, height), Image.LANCZOS)
            return ImageTk.PhotoImage(img)

    def scale_image_tk(self, path: str, width: int, height: int) -> tk.PhotoImage:
        from fractions import Fraction

        img = tk.PhotoImage(file=path)
        src_w = max(img.width(), 1)
        src_h = max(img.height(), 1)
        fx = Fraction(width, src_w).limit_denominator(32)
        fy = Fraction(height, src_h).limit_denominator(32)
        scaled = img.zoom(fx.numerator, fy.numerator).subsample(fx.denominator, fy.denominator)
        if scaled.width() == width and scaled.height() == height:
            return scaled
        dest = tk.PhotoImage(width=width, height=height)
        copy_w = min(scaled.width(), width)
        copy_h = min(scaled.height(), height)
        x_off = max((width - copy_w) // 2, 0)
        y_off = max((height - copy_h) // 2, 0)
        dest.tk.call(
            dest,
            "copy",
            scaled,
            "-from",
            0,
            0,
            copy_w,
            copy_h,
            "-to",
            x_off,
            y_off,
        )
        return dest

    def clear_crosshair_overlay(self) -> None:
        if not self.crosshair_overlay_ids:
            return
        for item_id in self.crosshair_overlay_ids:
            self.canvas.delete(item_id)
        self.crosshair_overlay_ids = []

    def draw_crosshair_overlay(self, width: int, height: int) -> None:
        self.clear_crosshair_overlay()
        self.crosshair_x = max(0, min(width - 1, self.crosshair_x))
        self.crosshair_y = max(0, min(height - 1, self.crosshair_y))
        r, g, b = self.mode_to_rgb(self.crosshair_color_mode, 255)
        color = f"#{r:02x}{g:02x}{b:02x}"
        if self.crosshair_mode in ("cross", "vline"):
            self.crosshair_overlay_ids.append(
                self.canvas.create_line(self.crosshair_x, 0, self.crosshair_x, height, fill=color)
            )
        if self.crosshair_mode in ("cross", "hline"):
            self.crosshair_overlay_ids.append(
                self.canvas.create_line(0, self.crosshair_y, width, self.crosshair_y, fill=color)
            )
        if self.crosshair_mode == "point":
            self.crosshair_overlay_ids.append(
                self.canvas.create_rectangle(
                    self.crosshair_x,
                    self.crosshair_y,
                    self.crosshair_x + 1,
                    self.crosshair_y + 1,
                    outline=color,
                    fill=color,
                )
            )

    def draw(self) -> None:
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.pattern_width = width
        self.pattern_height = height
        if self.pattern == "none":
            self.canvas.configure(bg="#7f7f7f")
        else:
            self.canvas.configure(bg="white")

        if self.pattern != "crosstalk":
            self.clear_crosstalk_overlay()

        if self.text_id is not None:
            self.canvas.delete(self.text_id)
            self.text_id = None
        if self.hud_rect_id is not None:
            self.canvas.delete(self.hud_rect_id)
            self.hud_rect_id = None

        if self.pattern == "image":
            self.draw_image_pattern(width, height)
            if self.crosshair_enabled:
                self.draw_crosshair_overlay(width, height)
            else:
                self.clear_crosshair_overlay()
            self.last_pil = None
            return

        if self.pattern == "crosstalk":
            self.draw_crosstalk(width, height)
            return

        if self.pattern == "none":
            instructions = (
                "右键/中键打开菜单选择图案。\n"
                "ESC 退出   Tab 切换显示器   Ctrl+S 保存 PNG\n"
                "灰阶/竖线/横线：上下调节灰阶，Shift 加速\n"
                "棋盘格：上下调节亮度，Shift 加速，左右切换格数\n"
                "Home=255 End=0，数字 1-8 切换颜色模式\n"
                "Ctrl+R 翻转图案/图片（水平/垂直）\n"
                "Ctrl+F 寻线模式，方向键移动，Ctrl+1/2/3/4 切换形态\n"
                "串扰：Ctrl+1/2 载入背景/遮挡图，方向键移动框，Ctrl+方向键调整框"
            )
            self.text_id = self.canvas.create_text(
                width // 2,
                height // 2,
                text=instructions,
                fill="#444444",
                font=("Segoe UI", 16),
                justify="center",
            )
            self.last_pil = None
            return

        base_img = self.get_pattern_base_pil(width, height)
        if base_img is None:
            self.ensure_image(width, height)
            self.clear_crosshair_overlay()
            if self.pattern == "grayscale":
                self.draw_grayscale(width, height)
            elif self.pattern == "checkerboard":
                self.draw_checkerboard(width, height)
                self.draw_checker_level(width, height)
                self.draw_checker_timer(width, height)
            elif self.pattern == "gray_h":
                self.draw_horizontal_gradient(width, height)
            elif self.pattern == "gray_v":
                self.draw_vertical_gradient(width, height)
            elif self.pattern == "gray_center":
                self.draw_center_gradient(width, height)
            elif self.pattern == "align":
                self.draw_align(width, height)
            elif self.pattern == "vline":
                self.draw_vertical_lines(width, height)
            elif self.pattern == "hline":
                self.draw_horizontal_lines(width, height)
            elif self.pattern == "1dot":
                self.draw_dot_pattern(width, height, 1)
            elif self.pattern == "2dot":
                self.draw_dot_pattern(width, height, 2)
            elif self.pattern == "subdot":
                self.draw_subdot_pattern(width, height)
            if self.crosshair_enabled:
                self.draw_crosshair(width, height)
                self.draw_coord_hud(width, height)
            self.last_pil = None
            return

        img = base_img
        if self.crosshair_enabled:
            img = base_img.copy()
            if img.mode != "RGB":
                img = img.convert("RGB")
            self.draw_crosshair_pil(img)
            self.draw_coord_hud_pil(img)
        elif self.show_hud:
            img = base_img.copy()
            self.draw_pattern_hud_pil(img)

        self.clear_crosshair_overlay()
        self.update_canvas_from_pil(img)
        self.last_pil = img

    def on_tick(self) -> None:
        if self.pattern == "checkerboard" and self.show_hud and not self.crosshair_enabled:
            self.draw()
        self.root.after(100, self.on_tick)

    def draw_grayscale(self, width: int, height: int) -> None:
        level = self.gray_level
        r, g, b = self.level_to_rgb(level)
        color = f"#{r:02x}{g:02x}{b:02x}"
        self.pattern_put(color, (0, 0, width, height))

        self.draw_level_hud(width, height, level)

    def quantize_level(self, value: float, steps: int) -> int:
        if steps <= 1:
            return 0
        if steps >= 256:
            return int(round(max(0.0, min(255.0, value))))
        ratio = max(0.0, min(1.0, value / 255.0))
        idx = int(round(ratio * (steps - 1)))
        return int(round(idx * 255 / (steps - 1)))

    def draw_horizontal_gradient(self, width: int, height: int) -> None:
        steps = self.gradient_steps
        denom = max(width - 1, 1)
        for x in range(width):
            level = self.quantize_level((x / denom) * 255.0, steps)
            r, g, b = self.level_to_rgb(level)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.pattern_put(color, (x, 0, x + 1, height))

    def draw_vertical_gradient(self, width: int, height: int) -> None:
        steps = self.gradient_steps
        denom = max(height - 1, 1)
        for y in range(height):
            level = self.quantize_level((y / denom) * 255.0, steps)
            r, g, b = self.level_to_rgb(level)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.pattern_put(color, (0, y, width, y + 1))

    def draw_center_gradient(self, width: int, height: int) -> None:
        steps = self.gradient_steps
        if steps <= 1:
            return
        bands = 256 if steps >= 256 else steps
        half_w = width // 2
        half_h = height // 2

        def build_insets(half: int, count: int) -> list[int]:
            base = half // count
            rem = half % count
            insets = [0]
            acc = 0
            for i in range(count):
                acc += base + (1 if i < rem else 0)
                insets.append(acc)
            return insets

        inset_x = build_insets(half_w, bands)
        inset_y = build_insets(half_h, bands)

        for band in range(bands):
            level = self.quantize_level((band / (bands - 1)) * 255.0 if bands > 1 else 255.0, steps)
            r, g, b = self.level_to_rgb(level)
            color = f"#{r:02x}{g:02x}{b:02x}"
            x1 = inset_x[band]
            y1 = inset_y[band]
            x2 = width - inset_x[band]
            y2 = height - inset_y[band]
            nx1 = inset_x[band + 1]
            ny1 = inset_y[band + 1]
            nx2 = width - inset_x[band + 1]
            ny2 = height - inset_y[band + 1]
            if ny1 > y1:
                self.pattern_put(color, (x1, y1, x2, ny1))
            if y2 > ny2:
                self.pattern_put(color, (x1, ny2, x2, y2))
            if nx1 > x1 and ny2 > ny1:
                self.pattern_put(color, (x1, ny1, nx1, ny2))
            if x2 > nx2 and ny2 > ny1:
                self.pattern_put(color, (nx2, ny1, x2, ny2))

        last_x = inset_x[-1]
        last_y = inset_y[-1]
        if last_x < width - last_x and last_y < height - last_y:
            level = self.quantize_level(255.0, steps)
            r, g, b = self.level_to_rgb(level)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.pattern_put(color, (last_x, last_y, width - last_x, height - last_y))

    def draw_level_hud(self, width: int, height: int, level: int) -> None:
        if not self.show_hud or self.crosshair_enabled:
            return
        self.draw_hud(width, height, f"L{level}")

    def draw_checker_level(self, width: int, height: int) -> None:
        if not self.show_hud or self.crosshair_enabled:
            return
        self.draw_hud(width, height, f"L{self.checker_level}")

    def draw_checker_timer(self, width: int, height: int) -> None:
        if not self.show_hud or self.crosshair_enabled:
            return
        elapsed = max(0.0, time.monotonic() - self.checker_start)
        days = int(elapsed // 86400)
        hours = int((elapsed % 86400) // 3600)
        minutes = int((elapsed % 3600) // 60)
        label = f"{days}:{hours}:{minutes}"
        self.draw_hud_right(width, height, label)

    def draw_coord_hud(self, width: int, height: int) -> None:
        if not self.show_hud:
            return
        label = f"X{self.crosshair_x} Y{self.crosshair_y}"
        self.draw_hud(width, height, label)

    def draw_hud(self, width: int, height: int, label: str) -> None:
        scale = 2
        pad_x = 6
        pad_y = 4
        text_w, text_h = self.measure_text(label, scale)
        hud_width = min(text_w + pad_x * 2, width)
        hud_height = min(text_h + pad_y * 2, height)
        hud_x = 2
        hud_y = 2
        self.image.put(
            "black",
            to=(
                hud_x,
                hud_y,
                min(hud_x + hud_width, width),
                min(hud_y + hud_height, height),
            ),
        )
        self.draw_text_on_image(hud_x + pad_x, hud_y + pad_y, label, "#ffffff", scale)

    def draw_hud_right(self, width: int, height: int, label: str) -> None:
        scale = 2
        pad_x = 6
        pad_y = 4
        text_w, text_h = self.measure_text(label, scale)
        hud_width = min(text_w + pad_x * 2, width)
        hud_height = min(text_h + pad_y * 2, height)
        hud_x = max(width - hud_width - 2, 0)
        hud_y = 2
        self.image.put(
            "black",
            to=(
                hud_x,
                hud_y,
                min(hud_x + hud_width, width),
                min(hud_y + hud_height, height),
            ),
        )
        self.draw_text_on_image(hud_x + pad_x, hud_y + pad_y, label, "#ffffff", scale)

    def measure_text(self, text: str, scale: int) -> tuple[int, int]:
        font = self.get_font_5x7()
        char_w = 5 * scale
        char_h = 7 * scale
        spacing = 1 * scale
        width = 0
        for char in text:
            if char == " ":
                width += 3 * scale
                continue
            if char in font:
                width += char_w + spacing
        if width > 0:
            width -= spacing
        return width, char_h

    def draw_text_on_image(self, x: int, y: int, text: str, color: str, scale: int) -> None:
        for char in text:
            if char == " ":
                x += 3 * scale
                continue
            if self.draw_char_on_image(x, y, char, color, scale):
                x += (5 + 1) * scale

    def draw_char_on_image(self, x: int, y: int, char: str, color: str, scale: int) -> bool:
        font = self.get_font_5x7()
        bitmap = font.get(char)
        if not bitmap:
            return False
        for row, line in enumerate(bitmap):
            for col, bit in enumerate(line):
                if bit == "1":
                    x0 = x + col * scale
                    y0 = y + row * scale
                    self.image.put(color, to=(x0, y0, x0 + scale, y0 + scale))
        return True

    def get_font_5x7(self) -> dict[str, list[str]]:
        return {
            "L": [
                "10000",
                "10000",
                "10000",
                "10000",
                "10000",
                "10000",
                "11111",
            ],
            "0": [
                "01110",
                "10001",
                "10011",
                "10101",
                "11001",
                "10001",
                "01110",
            ],
            "1": [
                "00100",
                "01100",
                "00100",
                "00100",
                "00100",
                "00100",
                "01110",
            ],
            "2": [
                "01110",
                "10001",
                "00001",
                "00010",
                "00100",
                "01000",
                "11111",
            ],
            "3": [
                "11110",
                "00001",
                "00001",
                "01110",
                "00001",
                "00001",
                "11110",
            ],
            "4": [
                "00010",
                "00110",
                "01010",
                "10010",
                "11111",
                "00010",
                "00010",
            ],
            "5": [
                "11111",
                "10000",
                "10000",
                "11110",
                "00001",
                "00001",
                "11110",
            ],
            "6": [
                "01110",
                "10000",
                "10000",
                "11110",
                "10001",
                "10001",
                "01110",
            ],
            "7": [
                "11111",
                "00001",
                "00010",
                "00100",
                "01000",
                "01000",
                "01000",
            ],
            "8": [
                "01110",
                "10001",
                "10001",
                "01110",
                "10001",
                "10001",
                "01110",
            ],
            "9": [
                "01110",
                "10001",
                "10001",
                "01111",
                "00001",
                "00001",
                "01110",
            ],
            ":": [
                "00000",
                "00100",
                "00100",
                "00000",
                "00100",
                "00100",
                "00000",
            ],
            "X": [
                "10001",
                "01010",
                "00100",
                "01010",
                "10001",
                "00000",
                "00000",
            ],
            "Y": [
                "10001",
                "01010",
                "00100",
                "00100",
                "00100",
                "00100",
                "00100",
            ],
            "&": [
                "01100",
                "10010",
                "10100",
                "01010",
                "10101",
                "10010",
                "01101",
            ],
            "E": [
                "11111",
                "10000",
                "10000",
                "11110",
                "10000",
                "10000",
                "11111",
            ],
            "I": [
                "11111",
                "00100",
                "00100",
                "00100",
                "00100",
                "00100",
                "11111",
            ],
            "M": [
                "10001",
                "11011",
                "10101",
                "10101",
                "10001",
                "10001",
                "10001",
            ],
            "N": [
                "10001",
                "11001",
                "10101",
                "10011",
                "10001",
                "10001",
                "10001",
            ],
            "O": [
                "01110",
                "10001",
                "10001",
                "10001",
                "10001",
                "10001",
                "01110",
            ],
            "R": [
                "11110",
                "10001",
                "10001",
                "11110",
                "10100",
                "10010",
                "10001",
            ],
            "S": [
                "01111",
                "10000",
                "10000",
                "01110",
                "00001",
                "00001",
                "11110",
            ],
            "T": [
                "11111",
                "00100",
                "00100",
                "00100",
                "00100",
                "00100",
                "00100",
            ],
            "U": [
                "10001",
                "10001",
                "10001",
                "10001",
                "10001",
                "10001",
                "01110",
            ],
            "V": [
                "10001",
                "10001",
                "10001",
                "10001",
                "10001",
                "01010",
                "00100",
            ],
            "Z": [
                "11111",
                "00001",
                "00010",
                "00100",
                "01000",
                "10000",
                "11111",
            ],
        }

    def draw_checkerboard(self, width: int, height: int) -> None:
        r, g, b = self.mode_to_rgb(self.checker_mode, self.checker_level)
        white_color = f"#{r:02x}{g:02x}{b:02x}"
        black_color = "#000000"
        size = self.checker_sizes[self.checker_size_index]
        cell_w = max(width // size, 1)
        cell_h = max(height // size, 1)
        for row in range(size):
            y1 = row * cell_h
            y2 = height if row == size - 1 else min((row + 1) * cell_h, height)
            for col in range(size):
                x1 = col * cell_w
                x2 = width if col == size - 1 else min((col + 1) * cell_w, width)
                color = white_color if (row + col) % 2 == 0 else black_color
                self.pattern_put(color, (x1, y1, x2, y2))

    def draw_vertical_lines(self, width: int, height: int) -> None:
        level = self.gray_level
        if self.vline_mode == "subline":
            magenta = f"#{level:02x}00{level:02x}"
            green = f"#00{level:02x}00"
            for x in range(0, width):
                color = magenta if x % 2 == 0 else green
                self.pattern_put(color, (x, 0, x + 1, height))
            self.draw_level_hud(width, height, level)
            return

        r, g, b = self.level_to_rgb(level)
        color = f"#{r:02x}{g:02x}{b:02x}"
        if self.vline_mode == "1line":
            for x in range(0, width):
                col_color = color if x % 2 == 0 else "#000000"
                self.pattern_put(col_color, (x, 0, x + 1, height))
            self.draw_level_hud(width, height, level)
            return

        if self.vline_mode == "2line":
            for x in range(0, width):
                col_color = color if x % 3 == 0 else "#000000"
                self.pattern_put(col_color, (x, 0, x + 1, height))
            self.draw_level_hud(width, height, level)

    def draw_horizontal_lines(self, width: int, height: int) -> None:
        r, g, b = self.level_to_rgb(self.gray_level)
        color = f"#{r:02x}{g:02x}{b:02x}"
        if self.hline_mode == "1line":
            for y in range(0, height):
                row_color = color if y % 2 == 0 else "#000000"
                self.pattern_put(row_color, (0, y, width, y + 1))
            self.draw_level_hud(width, height, self.gray_level)
            return
        if self.hline_mode == "2line":
            for y in range(0, height):
                row_color = color if y % 4 < 2 else "#000000"
                self.pattern_put(row_color, (0, y, width, y + 1))
            self.draw_level_hud(width, height, self.gray_level)

    def draw_dot_pattern(self, width: int, height: int, size: int) -> None:
        try:
            from PIL import Image, ImageTk  # type: ignore[import-not-found]
        except Exception:
            return

        level = self.gray_level
        r, g, b = self.level_to_rgb(level)
        on_color = (r, g, b)
        off_color = (0, 0, 0)
        cache_key = (width, height, size, level, self.gray_mode, self.flip_mode, self.show_hud)
        if cache_key == self.dot_cache_key and self.dot_pil is not None:
            self.dot_photo = ImageTk.PhotoImage(self.dot_pil)
        else:
            row_on: list[tuple[int, int, int]] = []
            row_off: list[tuple[int, int, int]] = []
            on = True
            x = 0
            while x < width:
                run = min(size, width - x)
                row_on.extend([on_color if on else off_color] * run)
                row_off.extend([off_color if on else on_color] * run)
                on = not on
                x += run

            img = Image.new("RGB", (width, height), off_color)
            row_on_img = Image.new("RGB", (width, 1))
            row_off_img = Image.new("RGB", (width, 1))
            row_on_img.putdata(row_on)
            row_off_img.putdata(row_off)
            for y in range(height):
                img.paste(row_on_img if y % 2 == 0 else row_off_img, (0, y))

            if self.flip_mode == "h":
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif self.flip_mode == "v":
                img = img.transpose(Image.FLIP_TOP_BOTTOM)

            if self.show_hud:
                self.draw_hud_pil(img, f"L{level}")

            self.dot_pil = img
            self.dot_cache_key = cache_key
            self.dot_photo = ImageTk.PhotoImage(img)

        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.dot_photo)
        else:
            self.canvas.itemconfig(self.image_id, image=self.dot_photo)

    def ensure_crosstalk_rect(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        if self.crosstalk_rect is None:
            rect_w = max(1, width // 3)
            rect_h = max(1, height // 3)
            x1 = max((width - rect_w) // 2, 0)
            y1 = max((height - rect_h) // 2, 0)
            self.crosstalk_rect = [x1, y1, x1 + rect_w, y1 + rect_h]
        self.clamp_crosstalk_rect(width, height)

    def clamp_crosstalk_rect(self, width: int, height: int) -> None:
        if self.crosstalk_rect is None:
            return
        x1, y1, x2, y2 = self.crosstalk_rect
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(x1 + 1, min(x2, width))
        y2 = max(y1 + 1, min(y2, height))
        self.crosstalk_rect = [x1, y1, x2, y2]

    def clear_crosstalk_overlay(self) -> None:
        if self.crosstalk_block_image_id is not None:
            self.canvas.delete(self.crosstalk_block_image_id)
            self.crosstalk_block_image_id = None
        self.crosstalk_block_photo = None
        self.crosstalk_block_photo_key = None

    def build_crosstalk_pil(self):
        try:
            from PIL import Image  # type: ignore[import-not-found]
        except Exception:
            return None
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.ensure_crosstalk_rect(width, height)
        if self.crosstalk_rect is None:
            return None
        x1, y1, x2, y2 = self.crosstalk_rect
        rect_w = max(x2 - x1, 1)
        rect_h = max(y2 - y1, 1)
        if self.crosstalk_bg_pil is not None:
            bg = self.crosstalk_bg_pil.copy()
        else:
            bg = Image.new("RGB", (width, height), (self.crosstalk_bg_level,) * 3)
        if self.crosstalk_block_pil is not None:
            block = self.crosstalk_block_pil.crop((x1, y1, x2, y2))
        else:
            block = Image.new("RGB", (rect_w, rect_h), (self.crosstalk_block_level,) * 3)
        bg.paste(block, (x1, y1))
        return bg

    def open_crosstalk_image(self, target: str) -> None:
        path = filedialog.askopenfilename(
            title="Open Image",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        if target == "background":
            self.crosstalk_bg_image_path = path
            self.crosstalk_bg_cache_key = None
            self.crosstalk_bg_pil = None
            self.crosstalk_bg_loading = False
        else:
            self.crosstalk_block_image_path = path
            self.crosstalk_block_cache_key = None
            self.crosstalk_block_pil = None
            self.crosstalk_block_loading = False
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.start_crosstalk_load(target, width, height)
        self.draw()

    def start_crosstalk_load(self, target: str, width: int, height: int) -> None:
        path = self.crosstalk_bg_image_path if target == "background" else self.crosstalk_block_image_path
        if not path:
            return
        if target == "background":
            self.crosstalk_bg_load_token += 1
            token = self.crosstalk_bg_load_token
            self.crosstalk_bg_loading = True
        else:
            self.crosstalk_block_load_token += 1
            token = self.crosstalk_block_load_token
            self.crosstalk_block_loading = True
        try:
            future = self.ensure_crosstalk_executor().submit(load_cover_bytes, path, width, height)
        except Exception:
            if target == "background":
                self.crosstalk_bg_loading = False
            else:
                self.crosstalk_block_loading = False
            return

        def done(fut: concurrent.futures.Future) -> None:
            try:
                data = fut.result()
            except Exception:
                data = None

            def apply() -> None:
                current_w = max(self.canvas.winfo_width(), 1)
                current_h = max(self.canvas.winfo_height(), 1)
                if current_w != width or current_h != height:
                    return
                try:
                    from PIL import Image  # type: ignore[import-not-found]
                except Exception:
                    return
                if target == "background":
                    if token != self.crosstalk_bg_load_token or self.crosstalk_bg_image_path != path:
                        return
                    if data is not None:
                        img = Image.frombytes("RGB", (width, height), data)
                        self.crosstalk_bg_pil = img
                        self.crosstalk_bg_cache_key = (path, width, height)
                    self.crosstalk_bg_loading = False
                else:
                    if token != self.crosstalk_block_load_token or self.crosstalk_block_image_path != path:
                        return
                    if data is not None:
                        img = Image.frombytes("RGB", (width, height), data)
                        self.crosstalk_block_pil = img
                        self.crosstalk_block_cache_key = (path, width, height)
                    self.crosstalk_block_loading = False
                self.draw()

            self.root.after(0, apply)

        future.add_done_callback(done)

    def draw_crosstalk(self, width: int, height: int) -> None:
        self.ensure_crosstalk_rect(width, height)
        if self.crosstalk_rect is None:
            return
        x1, y1, x2, y2 = self.crosstalk_rect
        rect_w = max(x2 - x1, 1)
        rect_h = max(y2 - y1, 1)
        try:
            from PIL import Image, ImageTk  # type: ignore[import-not-found]
        except Exception:
            self.clear_crosstalk_overlay()
            self.ensure_image(width, height)
            bg_color = f"#{self.crosstalk_bg_level:02x}{self.crosstalk_bg_level:02x}{self.crosstalk_bg_level:02x}"
            self.pattern_put(bg_color, (0, 0, width, height))
            block_color = f"#{self.crosstalk_block_level:02x}{self.crosstalk_block_level:02x}{self.crosstalk_block_level:02x}"
            self.pattern_put(block_color, (x1, y1, x2, y2))
            if self.crosshair_enabled:
                self.draw_crosshair(width, height)
                self.draw_coord_hud(width, height)
            self.last_pil = None
            return

        bg_base = None
        bg_from_image = False
        if self.crosstalk_bg_image_path:
            bg_key = (self.crosstalk_bg_image_path, width, height)
            if bg_key == self.crosstalk_bg_cache_key and self.crosstalk_bg_pil is not None:
                bg_base = self.crosstalk_bg_pil
                bg_from_image = True
            elif not self.crosstalk_bg_loading:
                self.start_crosstalk_load("background", width, height)
            else:
                bg_base = None
        if bg_base is None:
            bg_photo_key = ("solid", self.crosstalk_bg_level, width, height)
        else:
            bg_photo_key = ("image", self.crosstalk_bg_cache_key)
        if bg_photo_key != self.crosstalk_bg_photo_key:
            if bg_base is None:
                bg_img = Image.new("RGB", (width, height), (self.crosstalk_bg_level,) * 3)
            else:
                bg_img = bg_base
            self.crosstalk_bg_photo = ImageTk.PhotoImage(bg_img)
            self.crosstalk_bg_photo_key = bg_photo_key
        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.crosstalk_bg_photo)
        else:
            self.canvas.itemconfig(self.image_id, image=self.crosstalk_bg_photo)

        block_base = None
        block_from_image = False
        if self.crosstalk_block_image_path:
            block_key = (self.crosstalk_block_image_path, width, height)
            if (
                self.crosstalk_block_image_path == self.crosstalk_bg_image_path
                and self.crosstalk_bg_cache_key == block_key
                and self.crosstalk_bg_pil is not None
            ):
                block_base = self.crosstalk_bg_pil
                self.crosstalk_block_cache_key = block_key
                self.crosstalk_block_pil = block_base
                block_from_image = True
            if block_key == self.crosstalk_block_cache_key and self.crosstalk_block_pil is not None:
                block_base = self.crosstalk_block_pil
                block_from_image = True
            elif not self.crosstalk_block_loading:
                self.start_crosstalk_load("block", width, height)
            else:
                block_base = None
        if block_from_image:
            block_photo_key = ("image", self.crosstalk_block_cache_key, x1, y1, x2, y2)
        else:
            block_photo_key = ("solid", self.crosstalk_block_level, rect_w, rect_h)
        if block_photo_key != self.crosstalk_block_photo_key:
            if block_from_image and block_base is not None:
                block_img = block_base.crop((x1, y1, x2, y2))
            else:
                block_img = Image.new("RGB", (rect_w, rect_h), (self.crosstalk_block_level,) * 3)
            self.crosstalk_block_photo = ImageTk.PhotoImage(block_img)
            self.crosstalk_block_photo_key = block_photo_key
        if self.crosstalk_block_photo is not None:
            if self.crosstalk_block_image_id is None:
                self.crosstalk_block_image_id = self.canvas.create_image(
                    x1,
                    y1,
                    anchor="nw",
                    image=self.crosstalk_block_photo,
                )
            else:
                self.canvas.itemconfig(self.crosstalk_block_image_id, image=self.crosstalk_block_photo)
                self.canvas.coords(self.crosstalk_block_image_id, x1, y1)

        if self.crosshair_enabled:
            self.draw_crosshair_overlay(width, height)
        else:
            self.clear_crosshair_overlay()
        self.last_pil = None

    def draw_subdot_pattern(self, width: int, height: int) -> None:
        level = self.gray_level
        magenta = f"#{level:02x}00{level:02x}"
        green = f"#00{level:02x}00"
        for y in range(height):
            start_green = y % 2 == 0
            for x in range(width):
                use_green = (x % 2 == 0) if start_green else (x % 2 == 1)
                color = green if use_green else magenta
                self.pattern_put(color, (x, y, x + 1, y + 1))
        self.draw_level_hud(width, height, level)

    def draw_hud_pil(self, img, label: str, align: str = "left") -> None:
        scale = 2
        pad_x = 6
        pad_y = 4
        width, height = img.size
        text_w, text_h = self.measure_text(label, scale)
        hud_w = min(text_w + pad_x * 2, width)
        hud_h = min(text_h + pad_y * 2, height)
        hud_x = 2 if align != "right" else max(width - hud_w - 2, 0)
        hud_y = 2
        pixels = img.load()
        if img.mode == "P":
            bg = 3
            fg = 2
            for y in range(hud_y, min(hud_y + hud_h, height)):
                for x in range(hud_x, min(hud_x + hud_w, width)):
                    pixels[x, y] = bg
        else:
            for y in range(hud_y, min(hud_y + hud_h, height)):
                for x in range(hud_x, min(hud_x + hud_w, width)):
                    pixels[x, y] = (0, 0, 0)

        x0 = hud_x + pad_x
        y0 = hud_y + pad_y
        font = self.get_font_5x7()
        for ch in label:
            if ch == " ":
                x0 += 3 * scale
                continue
            bitmap = font.get(ch)
            if not bitmap:
                continue
            for row, line in enumerate(bitmap):
                for col, bit in enumerate(line):
                    if bit == "1":
                        for sy in range(scale):
                            for sx in range(scale):
                                px = x0 + col * scale + sx
                                py = y0 + row * scale + sy
                                if 0 <= px < width and 0 <= py < height:
                                    pixels[px, py] = 2 if img.mode == "P" else (255, 255, 255)
            x0 += (5 + 1) * scale

    def get_pattern_base_pil(self, width: int, height: int):
        try:
            from PIL import Image, ImageDraw  # type: ignore[import-not-found]
        except Exception:
            return None

        key = self.get_pattern_base_key(width, height)
        if key == self.pattern_base_key and self.pattern_base_pil is not None:
            if self.pattern in ("vline", "hline", "1dot", "2dot", "subdot"):
                self.pattern_base_pil = self.build_bicolor_image(width, height, Image)
            return self.pattern_base_pil

        img = self.build_pattern_base_pil(width, height, Image, ImageDraw)
        self.pattern_base_pil = img
        self.pattern_base_key = key
        return img

    def get_pattern_base_key(self, width: int, height: int) -> tuple:
        if self.pattern in ("vline", "hline", "1dot", "2dot", "subdot"):
            return (
                self.pattern,
                width,
                height,
                self.vline_mode,
                self.hline_mode,
                self.flip_mode,
            )
        return (
            self.pattern,
            width,
            height,
            self.gray_level,
            self.gray_mode,
            self.vline_mode,
            self.hline_mode,
            self.checker_level,
            self.checker_mode,
            self.checker_size_index,
            self.gradient_steps,
            self.flip_mode,
        )

    def build_pattern_base_pil(self, width: int, height: int, Image, ImageDraw):
        pattern = self.pattern
        if pattern == "grayscale":
            r, g, b = self.level_to_rgb(self.gray_level)
            img = Image.new("RGB", (width, height), (r, g, b))
            return self.apply_flip_pil(img)
        if pattern == "checkerboard":
            r, g, b = self.mode_to_rgb(self.checker_mode, self.checker_level)
            white_color = (r, g, b)
            black_color = (0, 0, 0)
            size = self.checker_sizes[self.checker_size_index]
            cell_w = max(width // size, 1)
            cell_h = max(height // size, 1)
            img = Image.new("RGB", (width, height), black_color)
            draw = ImageDraw.Draw(img)
            for row in range(size):
                y1 = row * cell_h
                y2 = height if row == size - 1 else min((row + 1) * cell_h, height)
                for col in range(size):
                    x1 = col * cell_w
                    x2 = width if col == size - 1 else min((col + 1) * cell_w, width)
                    if (row + col) % 2 == 0:
                        draw.rectangle((x1, y1, x2 - 1, y2 - 1), fill=white_color)
            return self.apply_flip_pil(img)
        if pattern in ("gray_h", "gray_v"):
            img = Image.new("RGB", (width, height))
            data = []
            if pattern == "gray_h":
                denom = max(width - 1, 1)
                row = []
                for x in range(width):
                    level = self.quantize_level((x / denom) * 255.0, self.gradient_steps)
                    row.append(self.level_to_rgb(level))
                data = row * height
            else:
                denom = max(height - 1, 1)
                for y in range(height):
                    level = self.quantize_level((y / denom) * 255.0, self.gradient_steps)
                    color = self.level_to_rgb(level)
                    data.extend([color] * width)
            img.putdata(data)
            return self.apply_flip_pil(img)
        if pattern == "gray_center":
            img = Image.new("RGB", (width, height), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            steps = self.gradient_steps
            if steps <= 1:
                return self.apply_flip_pil(img)
            bands = 256 if steps >= 256 else steps
            half_w = width // 2
            half_h = height // 2
            def build_insets(half: int, count: int) -> list[int]:
                base = half // count
                rem = half % count
                insets = [0]
                acc = 0
                for i in range(count):
                    acc += base + (1 if i < rem else 0)
                    insets.append(acc)
                return insets
            inset_x = build_insets(half_w, bands)
            inset_y = build_insets(half_h, bands)
            for band in range(bands):
                level = self.quantize_level((band / (bands - 1)) * 255.0 if bands > 1 else 255.0, steps)
                r, g, b = self.level_to_rgb(level)
                x1 = inset_x[band]
                y1 = inset_y[band]
                x2 = width - inset_x[band]
                y2 = height - inset_y[band]
                nx1 = inset_x[band + 1]
                ny1 = inset_y[band + 1]
                nx2 = width - inset_x[band + 1]
                ny2 = height - inset_y[band + 1]
                if ny1 > y1:
                    draw.rectangle((x1, y1, x2 - 1, ny1 - 1), fill=(r, g, b))
                if y2 > ny2:
                    draw.rectangle((x1, ny2, x2 - 1, y2 - 1), fill=(r, g, b))
                if nx1 > x1 and ny2 > ny1:
                    draw.rectangle((x1, ny1, nx1 - 1, ny2 - 1), fill=(r, g, b))
                if x2 > nx2 and ny2 > ny1:
                    draw.rectangle((nx2, ny1, x2 - 1, ny2 - 1), fill=(r, g, b))
            return self.apply_flip_pil(img)
        if pattern in ("vline", "hline", "1dot", "2dot", "subdot"):
            img = self.build_bicolor_image(width, height, Image)
            return img
        if pattern == "one_third":
            img = Image.new("RGB", (width, height), (255, 255, 255))
            split_y = height // 3
            draw = ImageDraw.Draw(img)
            draw.rectangle((0, 0, width - 1, max(split_y - 1, 0)), fill=(0, 0, 0))
            return self.apply_flip_pil(img)
        if pattern == "align":
            img = Image.new("RGB", (width, height), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            line_color = (191, 191, 191)
            cx = width // 2
            cy = height // 2
            draw.line((0, cy, width - 1, cy), fill=line_color, width=1)
            draw.line((cx, 0, cx, height - 1), fill=line_color, width=1)
            draw.line((0, 0, width - 1, height - 1), fill=line_color, width=1)
            draw.line((0, height - 1, width - 1, 0), fill=line_color, width=1)
            draw.rectangle((0, 0, width - 1, height - 1), outline=line_color, width=1)
            for ratio in (0.95, 0.75, 0.55, 0.35):
                rect_w = max(2, int(width * ratio))
                rect_h = max(2, int(height * ratio))
                x1 = (width - rect_w) // 2
                y1 = (height - rect_h) // 2
                x2 = x1 + rect_w - 1
                y2 = y1 + rect_h - 1
                draw.rectangle((x1, y1, x2, y2), outline=line_color, width=1)
            radius_base = min(cx, cy)
            for ratio in (1.0, 2 / 3, 1 / 3):
                radius = max(2, int(radius_base * ratio))
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=line_color, width=1)
            return self.apply_flip_pil(img)
        return Image.new("RGB", (width, height), (0, 0, 0))

    def apply_flip_pil(self, img):
        try:
            from PIL import Image  # type: ignore[import-not-found]
        except Exception:
            return img
        if self.flip_mode == "h":
            return img.transpose(Image.FLIP_LEFT_RIGHT)
        if self.flip_mode == "v":
            return img.transpose(Image.FLIP_TOP_BOTTOM)
        return img

    
    def get_bicolor_mask(self, width: int, height: int) -> bytes:
        key = (self.pattern, width, height, self.vline_mode, self.hline_mode, self.flip_mode)
        cached = self.bicolor_mask_cache.get(key)
        if cached is not None:
            return cached
        pattern = self.pattern
        mask = bytearray(width * height)

        def write_row(dest_y: int, row: bytearray) -> None:
            start = dest_y * width
            mask[start:start + width] = row

        if pattern == "vline":
            row = bytearray(width)
            if self.vline_mode == "subline":
                for x in range(width):
                    row[x] = 0 if x % 2 == 0 else 1
            elif self.vline_mode == "1line":
                for x in range(width):
                    row[x] = 1 if x % 2 == 0 else 0
            else:
                for x in range(width):
                    row[x] = 1 if x % 3 == 0 else 0
            if self.flip_mode == "h":
                row = bytearray(reversed(row))
            for y in range(height):
                dest_y = height - 1 - y if self.flip_mode == "v" else y
                write_row(dest_y, row)
        elif pattern == "hline":
            row_on = bytearray([1] * width)
            row_off = bytearray([0] * width)
            if self.flip_mode == "h":
                row_on = bytearray(reversed(row_on))
                row_off = bytearray(reversed(row_off))
            for y in range(height):
                use_on = y % 2 == 0 if self.hline_mode == "1line" else (y % 4 < 2)
                row = row_on if use_on else row_off
                dest_y = height - 1 - y if self.flip_mode == "v" else y
                write_row(dest_y, row)
        else:
            size = 1 if pattern in ("1dot", "subdot") else 2
            row_on = bytearray()
            row_off = bytearray()
            on = True
            x = 0
            while x < width:
                run = min(size, width - x)
                row_on.extend([1 if on else 0] * run)
                row_off.extend([0 if on else 1] * run)
                on = not on
                x += run
            if self.flip_mode == "h":
                row_on = bytearray(reversed(row_on))
                row_off = bytearray(reversed(row_off))
            for y in range(height):
                row = row_on if y % 2 == 0 else row_off
                dest_y = height - 1 - y if self.flip_mode == "v" else y
                write_row(dest_y, row)

        data = bytes(mask)
        self.bicolor_mask_cache[key] = data
        return data

    def update_bicolor_palette(self, img, color0: tuple[int, int, int], color1: tuple[int, int, int]) -> None:
        palette = [
            color0[0], color0[1], color0[2],
            color1[0], color1[1], color1[2],
            255, 255, 255,
            0, 0, 0,
        ]
        palette.extend([0, 0, 0] * (256 - 4))
        img.putpalette(palette)

    def build_bicolor_image(self, width: int, height: int, Image):
        mask = self.get_bicolor_mask(width, height)
        img = Image.frombytes("P", (width, height), mask)
        if self.pattern == "vline" and self.vline_mode == "subline":
            color0 = (self.gray_level, 0, self.gray_level)
            color1 = (0, self.gray_level, 0)
        elif self.pattern == "subdot":
            color0 = (self.gray_level, 0, self.gray_level)
            color1 = (0, self.gray_level, 0)
        else:
            r, g, b = self.level_to_rgb(self.gray_level)
            color1 = (r, g, b)
            color0 = (0, 0, 0)
        self.update_bicolor_palette(img, color0, color1)
        return img

    def draw_pattern_hud_pil(self, img) -> None:
        if self.pattern in ("grayscale", "vline", "hline", "1dot", "2dot", "subdot"):
            self.draw_hud_pil(img, f"L{self.gray_level}")
        elif self.pattern == "checkerboard":
            self.draw_hud_pil(img, f"L{self.checker_level}")
            elapsed = max(0.0, time.monotonic() - self.checker_start)
            days = int(elapsed // 86400)
            hours = int((elapsed % 86400) // 3600)
            minutes = int((elapsed % 3600) // 60)
            label = f"{days}:{hours}:{minutes}"
            self.draw_hud_pil(img, label, align="right")

    def draw_crosshair_pil(self, img) -> None:
        try:
            from PIL import ImageDraw  # type: ignore[import-not-found]
        except Exception:
            return
        width, height = img.size
        self.crosshair_x = max(0, min(width - 1, self.crosshair_x))
        self.crosshair_y = max(0, min(height - 1, self.crosshair_y))
        r, g, b = self.mode_to_rgb(self.crosshair_color_mode, 255)
        color = (r, g, b)
        draw = ImageDraw.Draw(img)
        if self.crosshair_mode in ("cross", "vline"):
            draw.line((self.crosshair_x, 0, self.crosshair_x, height - 1), fill=color, width=1)
        if self.crosshair_mode in ("cross", "hline"):
            draw.line((0, self.crosshair_y, width - 1, self.crosshair_y), fill=color, width=1)
        if self.crosshair_mode == "point":
            draw.rectangle((self.crosshair_x, self.crosshair_y, self.crosshair_x, self.crosshair_y), fill=color)

    def draw_coord_hud_pil(self, img) -> None:
        label = f"X{self.crosshair_x} Y{self.crosshair_y}"
        self.draw_hud_pil(img, label)

    def update_canvas_from_pil(self, img) -> None:
        try:
            from PIL import ImageTk  # type: ignore[import-not-found]
        except Exception:
            return
        self.pattern_photo = ImageTk.PhotoImage(img)
        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.pattern_photo)
        else:
            self.canvas.itemconfig(self.image_id, image=self.pattern_photo)
    def draw_align(self, width: int, height: int) -> None:
        try:
            from PIL import Image, ImageDraw, ImageTk  # type: ignore[import-not-found]
        except Exception:
            self.pattern_put("black", (0, 0, width, height))
            line_color = "#bfbfbf"
            cx = width // 2
            cy = height // 2
            self.draw_line(0, cy, width - 1, cy, line_color)
            self.draw_line(cx, 0, cx, height - 1, line_color)
            self.draw_line(0, 0, width - 1, height - 1, line_color)
            self.draw_line(0, height - 1, width - 1, 0, line_color)
            self.draw_rect_outline(0, 0, width - 1, height - 1, line_color)
            for ratio in (0.95, 0.75, 0.55, 0.35):
                rect_w = max(2, int(width * ratio))
                rect_h = max(2, int(height * ratio))
                x1 = (width - rect_w) // 2
                y1 = (height - rect_h) // 2
                x2 = x1 + rect_w - 1
                y2 = y1 + rect_h - 1
                self.draw_rect_outline(x1, y1, x2, y2, line_color)
            radius_base = min(cx, cy)
            for ratio in (1.0, 2 / 3, 1 / 3):
                radius = max(2, int(radius_base * ratio))
                self.draw_circle(cx, cy, radius, line_color)
            return

        cache_key = (width, height, self.flip_mode)
        if cache_key == self.align_cache_key and self.align_pil is not None:
            self.align_photo = ImageTk.PhotoImage(self.align_pil)
        else:
            img = Image.new("RGB", (width, height), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            line_color = (191, 191, 191)
            cx = width // 2
            cy = height // 2
            draw.line((0, cy, width - 1, cy), fill=line_color, width=1)
            draw.line((cx, 0, cx, height - 1), fill=line_color, width=1)
            draw.line((0, 0, width - 1, height - 1), fill=line_color, width=1)
            draw.line((0, height - 1, width - 1, 0), fill=line_color, width=1)
            draw.rectangle((0, 0, width - 1, height - 1), outline=line_color, width=1)
            for ratio in (0.95, 0.75, 0.55, 0.35):
                rect_w = max(2, int(width * ratio))
                rect_h = max(2, int(height * ratio))
                x1 = (width - rect_w) // 2
                y1 = (height - rect_h) // 2
                x2 = x1 + rect_w - 1
                y2 = y1 + rect_h - 1
                draw.rectangle((x1, y1, x2, y2), outline=line_color, width=1)
            radius_base = min(cx, cy)
            for ratio in (1.0, 2 / 3, 1 / 3):
                radius = max(2, int(radius_base * ratio))
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=line_color, width=1)
            if self.flip_mode == "h":
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif self.flip_mode == "v":
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
            self.align_pil = img
            self.align_cache_key = cache_key
            self.align_photo = ImageTk.PhotoImage(img)

        if self.image_id is None:
            self.image_id = self.canvas.create_image(0, 0, anchor="nw", image=self.align_photo)
        else:
            self.canvas.itemconfig(self.image_id, image=self.align_photo)
    def draw_rect_outline(self, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
        self.pattern_put(color, (x1, y1, x2 + 1, y1 + 1))
        self.pattern_put(color, (x1, y2, x2 + 1, y2 + 1))
        self.pattern_put(color, (x1, y1, x1 + 1, y2 + 1))
        self.pattern_put(color, (x2, y1, x2 + 1, y2 + 1))

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy), 1)
        for i in range(steps + 1):
            x = int(round(x1 + dx * i / steps))
            y = int(round(y1 + dy * i / steps))
            self.pattern_put(color, (x, y, x + 1, y + 1))

    def draw_circle(self, cx: int, cy: int, radius: int, color: str) -> None:
        x = radius
        y = 0
        err = 1 - radius
        while x >= y:
            self.pattern_put(color, (cx + x, cy + y, cx + x + 1, cy + y + 1))
            self.pattern_put(color, (cx + y, cy + x, cx + y + 1, cy + x + 1))
            self.pattern_put(color, (cx - y, cy + x, cx - y + 1, cy + x + 1))
            self.pattern_put(color, (cx - x, cy + y, cx - x + 1, cy + y + 1))
            self.pattern_put(color, (cx - x, cy - y, cx - x + 1, cy - y + 1))
            self.pattern_put(color, (cx - y, cy - x, cx - y + 1, cy - x + 1))
            self.pattern_put(color, (cx + y, cy - x, cx + y + 1, cy - x + 1))
            self.pattern_put(color, (cx + x, cy - y, cx + x + 1, cy - y + 1))
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1
                err += 2 * (y - x) + 1

    def draw_crosshair(self, width: int, height: int) -> None:
        self.crosshair_x = max(0, min(width - 1, self.crosshair_x))
        self.crosshair_y = max(0, min(height - 1, self.crosshair_y))
        r, g, b = self.mode_to_rgb(self.crosshair_color_mode, 255)
        color = f"#{r:02x}{g:02x}{b:02x}"

        if self.crosshair_mode in ("cross", "vline"):
            self.image.put(color, to=(self.crosshair_x, 0, self.crosshair_x + 1, height))
        if self.crosshair_mode in ("cross", "hline"):
            self.image.put(color, to=(0, self.crosshair_y, width, self.crosshair_y + 1))
        if self.crosshair_mode == "point":
            self.image.put(
                color,
                to=(
                    self.crosshair_x,
                    self.crosshair_y,
                    self.crosshair_x + 1,
                    self.crosshair_y + 1,
                ),
            )

    def on_key(self, event: tk.Event) -> None:
        is_ctrl = bool(event.state & 0x0004)
        is_alt = bool(event.state & 0x0008)
        if is_ctrl and event.keysym.lower() == "r":
            if self.pattern != "none":
                if self.pattern == "image":
                    if self.flip_mode == "none":
                        self.flip_mode = "h"
                    elif self.flip_mode == "h":
                        self.flip_mode = "v"
                    else:
                        self.flip_mode = "none"
                elif self.pattern in ("gray_h", "vline"):
                    self.flip_mode = "h" if self.flip_mode != "h" else "none"
                else:
                    self.flip_mode = "v" if self.flip_mode != "v" else "none"
                self.draw()
            return
        if is_ctrl and event.keysym.lower() == "f":
            if self.pattern != "none":
                self.crosshair_enabled = not self.crosshair_enabled
                if self.crosshair_enabled:
                    width = max(self.canvas.winfo_width(), 1)
                    height = max(self.canvas.winfo_height(), 1)
                    self.crosshair_x = width // 2
                    self.crosshair_y = height // 2
                    self.crosshair_mode = "cross"
                    self.crosshair_color_mode = "white"
                self.draw()
            return

        if self.pattern == "crosstalk":
            width = max(self.canvas.winfo_width(), 1)
            height = max(self.canvas.winfo_height(), 1)
            self.ensure_crosstalk_rect(width, height)
            if is_ctrl and event.keysym == "1":
                self.open_crosstalk_image("background")
                return
            if is_ctrl and event.keysym == "2":
                self.open_crosstalk_image("block")
                return
            if is_ctrl and event.keysym in ("Left", "Right", "Up", "Down"):
                step = 10 if (event.state & 0x0001) else 1
                x1, y1, x2, y2 = self.crosstalk_rect or [0, 0, 1, 1]
                if event.keysym == "Left":
                    x1 -= step
                elif event.keysym == "Right":
                    x2 += step
                elif event.keysym == "Up":
                    y1 -= step
                elif event.keysym == "Down":
                    y2 += step
                self.crosstalk_rect = [x1, y1, x2, y2]
                self.clamp_crosstalk_rect(width, height)
                self.draw()
                return
            if event.keysym in ("Left", "Right", "Up", "Down") and not is_ctrl:
                step = 10 if (event.state & 0x0001) else 1
                dx = 0
                dy = 0
                if event.keysym == "Left":
                    dx = -step
                elif event.keysym == "Right":
                    dx = step
                elif event.keysym == "Up":
                    dy = -step
                elif event.keysym == "Down":
                    dy = step
                x1, y1, x2, y2 = self.crosstalk_rect or [0, 0, 1, 1]
                x1 += dx
                x2 += dx
                y1 += dy
                y2 += dy
                if x1 < 0:
                    x2 -= x1
                    x1 = 0
                if y1 < 0:
                    y2 -= y1
                    y1 = 0
                if x2 > width:
                    x1 -= (x2 - width)
                    x2 = width
                if y2 > height:
                    y1 -= (y2 - height)
                    y2 = height
                self.crosstalk_rect = [x1, y1, x2, y2]
                self.clamp_crosstalk_rect(width, height)
                self.draw()
                return
            return

        if self.crosshair_enabled:
            if is_ctrl and event.keysym in ("1", "2", "3", "4"):
                mode_map = {
                    "1": "hline",
                    "2": "vline",
                    "3": "point",
                    "4": "cross",
                }
                self.crosshair_mode = mode_map[event.keysym]
                self.draw()
                return

            if event.keysym in ("Up", "Down"):
                if self.crosshair_mode in ("cross", "hline", "point"):
                    step = 10 if (event.state & 0x0001) else 1
                    delta = -step if event.keysym == "Up" else step
                    self.crosshair_y += delta
                    self.draw()
                return
            if event.keysym in ("Left", "Right"):
                if self.crosshair_mode in ("cross", "vline", "point"):
                    step = 10 if (event.state & 0x0001) else 1
                    delta = -step if event.keysym == "Left" else step
                    self.crosshair_x += delta
                    self.draw()
                return

            if event.char and event.char in "12345678":
                self.crosshair_color_mode = self.map_color_mode(event.char)
                self.draw()
            return

        if self.pattern == "checkerboard":
            if event.keysym in ("Up", "Down"):
                step = 16 if (event.state & 0x0001) else 1
                if event.keysym == "Down":
                    step = -step
                self.checker_level = max(0, min(255, self.checker_level + step))
                self.draw()
                return
            if event.keysym in ("Left", "Right"):
                delta = -1 if event.keysym == "Left" else 1
                new_index = self.checker_size_index + delta
                self.checker_size_index = max(0, min(len(self.checker_sizes) - 1, new_index))
                self.draw()
                return
            if event.keysym == "Home":
                self.checker_level = 255
                self.draw()
                return
            if event.keysym == "End":
                self.checker_level = 0
                self.draw()
                return
            if event.char and event.char in "12345678":
                self.checker_mode = self.map_color_mode(event.char)
                self.draw()
            return

        if self.pattern in ("gray_h", "gray_v", "gray_center"):
            if event.char and event.char in "12345678":
                self.gray_mode = self.map_color_mode(event.char)
                self.draw()
            return

        if self.pattern not in ("grayscale", "vline", "hline", "1dot", "2dot", "subdot"):
            return

        if event.keysym in ("Up", "Down"):
            step = 16 if (event.state & 0x0001) else 1
            if event.keysym == "Down":
                step = -step
            self.gray_level = max(0, min(255, self.gray_level + step))
            self.draw()
            return
        if event.keysym == "Home":
            self.gray_level = 255
            self.draw()
            return
        if event.keysym == "End":
            self.gray_level = 0
            self.draw()
            return

        if event.char and event.char in "12345678":
            self.gray_mode = self.map_color_mode(event.char)
            self.draw()

    def get_monitors(self) -> list[tuple[int, int, int, int]]:
        monitors: list[tuple[int, int, int, int]] = []

        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", ctypes.c_ulong),
            ]

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(RECT),
            ctypes.c_double,
        )

        def callback(hmonitor, hdc, rect_ptr, data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                rect = info.rcMonitor
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                is_primary = bool(info.dwFlags & 1)
                entry = (rect.left, rect.top, width, height)
                if is_primary:
                    monitors.insert(0, entry)
                else:
                    monitors.append(entry)
            return 1

        user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(callback), 0)
        if not monitors:
            width = self.root.winfo_screenwidth()
            height = self.root.winfo_screenheight()
            monitors.append((0, 0, width, height))
        return monitors

    def map_color_mode(self, key: str) -> str:
        mode_map = {
            "1": "red",
            "2": "green",
            "3": "blue",
            "4": "white",
            "5": "yellow",
            "6": "magenta",
            "7": "cyan",
            "8": "white",
        }
        return mode_map.get(key, "white")

    def level_to_rgb(self, level: int) -> tuple[int, int, int]:
        return self.mode_to_rgb(self.gray_mode, level)

    def mode_to_rgb(self, mode: str, level: int) -> tuple[int, int, int]:
        if mode == "red":
            return level, 0, 0
        if mode == "green":
            return 0, level, 0
        if mode == "blue":
            return 0, 0, level
        if mode == "yellow":
            return level, level, 0
        if mode == "magenta":
            return level, 0, level
        if mode == "cyan":
            return 0, level, level
        return level, level, level

    def pattern_put(self, color: str, to: tuple[int, int, int, int]) -> None:
        x1, y1, x2, y2 = to
        if self.flip_mode == "h":
            x1, x2 = self.pattern_width - x2, self.pattern_width - x1
        elif self.flip_mode == "v":
            y1, y2 = self.pattern_height - y2, self.pattern_height - y1
        if x2 <= x1 or y2 <= y1:
            return
        self.image.put(color, to=(x1, y1, x2, y2))


def report_fatal_error(exc: Exception) -> None:
    log_path = Path(sys.argv[0]).with_suffix(".log")
    message = f"{exc}\n\n{traceback.format_exc()}"
    try:
        log_path.write_text(message, encoding="utf-8")
    except OSError:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Fatal error, details saved to:\n{log_path}\n\n{exc}",
            "Pattern Test",
            0x00000010,
        )
    except Exception:
        pass

if __name__ == "__main__":
    try:
        multiprocessing.freeze_support()
        root = tk.Tk()
        app = PatternApp(root)
        root.mainloop()
    except Exception as exc:  # noqa: BLE001
        report_fatal_error(exc)
