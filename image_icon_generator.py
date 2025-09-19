"""
LAUNCH TOOLS
A GUI to display and launch tools from the diffusion project venv.
Arranges and prioritizes common tools.

Diffusion Project Python Tools (synced with launch_tools.py):

// IMAGE REVIEW --------------------------
- image_review_and_rank_multi_project.py
- image_review_and_rank.py

// PROMPT --------------------------
- gen_project_prompt_entry.py
- image_text_prompt_tools.py

// IMAGE TOOLS --------------------------
- image_editor_layered.py
- image_icon_generator.py
- image_inspect_bmp.py
- image_metadata_badword_scanner.py
- image_psd_reconstruct.py
- comfyui_workflow_color_edit.py

// SORT / VOICE --------------------------
- tensor_tools_all.py
- voice_action_organizer.py

// VIDEO --------------------------
- video_combine.py
- video_clip_marker.py
- video_place_in_image_composite.py
- video_webp_pingpong.py
- video_review_and_rank_multi_project.py
- video_psd_to_timelapse_anim.py
- video_add_audio.py
- video_editor_word_rating.py
- VIDEO_cursor_removal.py
- VIDEO_image_sequence_to_webp.py
- video_audio_batch_processor.py
- video_interlacing_fix.py
- video_to_gif_cropper.py
- audio_timing_beat.py

// SD WEBUI PROJECT --------------------------
- sd_batch_image_gen_auto1111_webui.py
- projects_from_civitai_info.py
- projects_from_images.py
- lora_variants.py
- gen_batch_prompts_in_projects.py
- gen_image_variant_grid_explore.py
- lora_previews_to_list.py
- tensor_lora_check_compatible_checkpoint.py
- project_status_dashboard.py

// DEV TOOLS --------------------------
- dev_python_imports_to_top.py
- dev_python_requirements_env.py
- test_safetensors.py
"""

import os
import sys
import math
from pathlib import Path
from typing import Dict, List, Optional
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageTk

#//========================================================================================================
SHOW_TOOL_EMOJIS = True  # Set to False to hide emojis on tool buttons
DEBUG_MODE = False

# --- Tool Emoji Mapping ---
TOOL_EMOJIS = {
    # Image Review
    'image_review_and_rank_multi_project.py': '🖼️🔍📊',
    'image_review_and_rank.py': '🖼️🔍⭐',
    'image_review_and_rank_multi.py': '🖼️🔍📁',
    # Prompt
    'gen_project_prompt_entry.py': '📝✨📂',
    'image_text_prompt_tools.py': '📝🖼️🔤',
    # Image Tools
    'image_editor_layered.py': '🖌️🖼️🎨',
    'image_icon_generator.py': '🖼️⚙️🧩',
    'image_inspect_bmp.py': '🖼️🔎🧩',
    'image_metadata_badword_scanner.py': '🖼️🚫🔤',
    'image_psd_reconstruct.py': '🖼️🧩🔁',
    'comfyui_workflow_color_edit.py': '🎛️🎨🖼️',
    # Model Info and Sort
    'tensor_tools_all.py': '🧠ℹ️🗂️',
    'tensor_info_civitai_get.py': '🧠🔗ℹ️',
    'tensor_sort_civitai_files.py': '🧠🗂️📦',
    'tensor_sort_civitai_by_category.py': '🧠🏷️📂',
    'tensor_remove_duplicate.py': '🧹🧠❌',
    'tensor_lora_check_compatible_checkpoint.py': '🧬✅🧠',
    'lora_previews_to_list.py': '🧬🖼️📜',
    # Video
    'video_combine.py': '🎬➕🎬',
    'video_clip_marker.py': '✂️🎬',
    'video_place_in_image_composite.py': '🖼️🎬',
    'video_webp_pingpong.py': '↔️🎬🖼️',
    'video_review_and_rank_multi_project.py': '🎬🔍📊',
    'video_psd_to_timelapse_anim.py': '🖼️⏳🎬',
    'video_add_audio.py': '🎵➕🎬',
    'video_editor_word_rating.py': '✍️🎬⭐',
    'VIDEO_cursor_removal.py': '🖱️❌🎬',
    'VIDEO_image_sequence_to_webp.py': '🖼️➡️🕸️',
    'video_audio_batch_processor.py': '🎵📦🎬',
    'video_interlacing_fix.py': '📶🛠️🎬',
    'video_to_gif_cropper.py': '🖼️➡️🎞️',
    'audio_timing_beat.py': '🎵⏱️🔢',
    # Voice
    'voice_action_organizer.py': '🎤🗂️🧭',
    # SD webui Project
    'sd_batch_image_gen_auto1111_webui.py': '🤖🖼️🔁',
    'projects_from_civitai_info.py': '🧠📄📂',
    'projects_from_images.py': '🖼️📁📂',
    'lora_variants.py': '🧬🔀📦',
    'gen_batch_prompts_in_projects.py': '📝📦🔁',
    'gen_image_variant_grid_explore.py': '🖼️🗺️🔍',
    'project_status_dashboard.py': '📊📁🖼️',
    # Dev Tools
    'dev_python_imports_to_top.py': '🐍⬆️📦',
    'dev_python_requirements_env.py': '🐍📄⚙️',
    'test_safetensors.py': '🧪🔒🧠',
}

# ========================= Icon Composer Focused Code ========================= #
# Paths & defaults
ICON_OUTPUT_DIR = 'icons'
EMOJI_ASSET_DIR = os.path.join('icons', 'ref', 'emoji')
DEFAULT_SIZE = 128

def emoji_codepoints(emoji: str) -> str:
    return '-'.join(f'{ord(c):x}' for c in emoji)

def find_best_emoji_asset(emoji: str) -> Optional[Path]:
    cp = emoji_codepoints(emoji)
    base = f'emoji_{cp}_'
    if not os.path.isdir(EMOJI_ASSET_DIR):
        return None
    best = None
    best_size = -1
    for name in os.listdir(EMOJI_ASSET_DIR):
        if name.startswith(base) and name.endswith('.png'):
            try:
                size_val = int(name[len(base):-4])
            except Exception:
                size_val = 0
            if size_val > best_size:
                best_size = size_val
                best = name
    return Path(EMOJI_ASSET_DIR) / best if best else None

def render_emoji_fallback(emoji: str, px: int) -> Image.Image:
    font_paths = [
        'seguiemj.ttf', 'Segoe UI Emoji.ttf',
        '/System/Library/Fonts/Apple Color Emoji.ttc',
        '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',
    ]
    font = None
    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, px)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    img = Image.new('RGBA', (px, px), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        bbox = draw.textbbox((0, 0), emoji, font=font, embedded_color=True)
    except TypeError:
        bbox = draw.textbbox((0, 0), emoji, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (px - w) // 2 - bbox[0]
    y = (px - h) // 2 - bbox[1]
    try:
        draw.text((x, y), emoji, font=font, embedded_color=True)
    except TypeError:
        draw.text((x, y), emoji, font=font)
    return img

def load_emoji_image(emoji: str, target_w: int) -> Image.Image:
    """Load emoji image strictly via temporary renders, not prebuilt assets.
    Always ensure a temp image at a reasonably large base size, then resize.
    """
    # Render at max(target_w, 128) into temp cache, then load and scale.
    base_px = max(target_w, 128)
    temp_path = ensure_temp_emoji_image(emoji, base_px)
    try:
        img = Image.open(temp_path).convert('RGBA')
    except Exception:
        img = render_emoji_fallback(emoji, base_px)
    if img.width != target_w:
        scale = target_w / float(img.width)
        new_h = max(1, int(round(img.height * scale)))
        img = img.resize((target_w, new_h), Image.LANCZOS)
    return img

def golden_trio_default(emojis: List[str]) -> List[Dict]:
    layers: List[Dict] = []
    if not emojis:
        return layers
    layers.append({'emoji': emojis[0], 'rel_w': 0.66, 'cx': 0.33, 'cy': 0.50, 'anchor': 'center', 'z': 0})
    if len(emojis) >= 2:
        layers.append({'emoji': emojis[1], 'rel_w': 0.33, 'cx': 0.80, 'cy': 0.32, 'anchor': 'center', 'z': 1})
    if len(emojis) >= 3:
        layers.append({'emoji': emojis[2], 'rel_w': 0.22, 'cx': 0.78, 'cy': 0.78, 'anchor': 'center', 'z': 2})
    return layers

COMPOSITIONS: Dict[str, List[Dict]] = {
    'voice_action_organizer.py': [
        {'emoji': '🎤', 'rel_w': 0.66, 'cx': 0.33, 'cy': 0.50, 'anchor': 'center', 'z': 0},
        {'emoji': '📂', 'rel_w': 0.33, 'cx': 0.80, 'cy': 0.32, 'anchor': 'center', 'z': 1},
        {'emoji': '⏳', 'rel_w': 0.22, 'cx': 0.78, 'cy': 0.78, 'anchor': 'center', 'z': 2},
    ],
    'gen_project_prompt_entry.py': [
        {'emoji': '📝', 'rel_w': 0.76, 'cx': 0.50, 'cy': 0.52, 'anchor': 'center', 'z': 0},
        {'emoji': '✨', 'rel_w': 0.36, 'cx': 0.78, 'cy': 0.28, 'anchor': 'center', 'z': 1},
        {'emoji': '📂', 'rel_w': 0.26, 'cx': 0.80, 'cy': 0.80, 'anchor': 'center', 'z': 2},
    ],
}

def place_layer(base: Image.Image, layer: Dict):
    W, H = base.size
    rel_w = float(layer.get('rel_w', 0.5))
    target_w = max(1, int(round(W * rel_w)))
    sprite = load_emoji_image(str(layer['emoji']), target_w)
    sw, sh = sprite.size
    cx = float(layer.get('cx', 0.5)) * W
    cy = float(layer.get('cy', 0.5)) * H
    anchor = str(layer.get('anchor', 'center')).lower()
    if anchor == 'center':
        x0 = int(round(cx - sw / 2)); y0 = int(round(cy - sh / 2))
    elif anchor == 'tl':
        x0 = int(round(cx)); y0 = int(round(cy))
    elif anchor == 'tr':
        x0 = int(round(cx - sw)); y0 = int(round(cy))
    elif anchor == 'bl':
        x0 = int(round(cx)); y0 = int(round(cy - sh))
    elif anchor == 'br':
        x0 = int(round(cx - sw)); y0 = int(round(cy - sh))
    else:
        x0 = int(round(cx - sw / 2)); y0 = int(round(cy - sh / 2))
    base.alpha_composite(sprite, (x0, y0))

def compose_icon_for_tool(tool_file: str, size: int, layers_override: Optional[List[Dict]] = None) -> Image.Image:
    canvas = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    if layers_override is not None:
        layers = layers_override
    elif tool_file in COMPOSITIONS:
        layers = COMPOSITIONS[tool_file]
    else:
        emoji_str = TOOL_EMOJIS.get(tool_file, '')
        emojis = [ch for ch in emoji_str if ch.strip()]
        layers = golden_trio_default(emojis[:3])
    for layer in sorted(layers, key=lambda L: int(L.get('z', 0))):
        place_layer(canvas, layer)
    return canvas

def save_icon(tool_file: str, out_dir: str, size: int, overwrite: bool = False, layers_override: Optional[List[Dict]] = None) -> Path:
    img = compose_icon_for_tool(tool_file, size, layers_override=layers_override)
    os.makedirs(out_dir, exist_ok=True)
    out_path = Path(out_dir) / f"{Path(tool_file).stem}.png"
    if out_path.exists() and not overwrite:
        print(f"[skip] {out_path} exists (use --overwrite)")
        return out_path
    img.save(out_path)
    print(f"[icon] Wrote {out_path}")
    return out_path

def infer_all_tools() -> List[str]:
    return sorted(list(TOOL_EMOJIS.keys()))

# ---------------- UI: Temp emoji cache + interactive preview ---------------- #
TEMP_EMOJI_DIR = os.path.join('icons', '_tmp_emoji')

def ensure_temp_dir():
    os.makedirs(TEMP_EMOJI_DIR, exist_ok=True)

def ensure_temp_emoji_image(emoji: str, px: int) -> Path:
    """Render the emoji into the temp folder as a PNG and return its path.
    We always (re)create to keep the flow simple and deterministic for this session.
    """
    ensure_temp_dir()
    code = '-'.join(f'{ord(c):x}' for c in emoji)
    out_path = Path(TEMP_EMOJI_DIR) / f"emoji_{code}_{px}.png"
    img = render_emoji_fallback(emoji, px)
    img.save(out_path)
    return out_path

def composition_from_tool(tool_file: str) -> List[Dict]:
    if tool_file in COMPOSITIONS:
        return COMPOSITIONS[tool_file]
    emoji_str = TOOL_EMOJIS.get(tool_file, '')
    emojis = [ch for ch in emoji_str if ch.strip()]
    return golden_trio_default(emojis[:3])

import random

def randomize_composition(emojis: List[str]) -> List[Dict]:
    """Create a randomized but controlled composition from the given emojis.
    - Random order
    - Rel_w sampled around golden trio sizes with small jitter
    - Positions jittered around default anchors
    - Z order equal to list order (later is on top)
    """
    if not emojis:
        return []
    em = emojis[:3]
    random.shuffle(em)
    base_sizes = [0.66, 0.33, 0.22]
    # jitter within +/- 15%
    sizes = [max(0.12, s * random.uniform(0.85, 1.15)) for s in base_sizes[:len(em)]]
    # default centers similar to golden trio
    centers = [(0.33, 0.50), (0.80, 0.32), (0.78, 0.78)]
    layers = []
    for i, e in enumerate(em):
        cx0, cy0 = centers[i]
        # jitter centers within +/- 7%
        cx = min(0.95, max(0.05, cx0 + random.uniform(-0.07, 0.07)))
        cy = min(0.95, max(0.05, cy0 + random.uniform(-0.07, 0.07)))
        layers.append({'emoji': e, 'rel_w': sizes[i], 'cx': cx, 'cy': cy, 'anchor': 'center', 'z': i})
    return layers

class IconComposerUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Icon Composer - Emoji Placeholder Generator')
        self.geometry('900x480')
        self.configure(bg='#20232a')
        self.preview_size = 256
        self.current_tool: Optional[str] = None
        self.current_layers: List[Dict] = []
        self._preview_tk = None
        self._existing_tk = None
        self._build_ui()
        self._populate_tools()

    def _build_ui(self):
        # Left: tools list
        left = tk.Frame(self, bg='#20232a')
        left.pack(side='left', fill='y', padx=8, pady=8)

        tk.Label(left, text='Tools', fg='#e6edf3', bg='#20232a', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        self.tools_list = tk.Listbox(left, height=20, width=36, bg='#0d1117', fg='#e6edf3', selectbackground='#30363d', activestyle='none')
        self.tools_list.pack(fill='y', expand=False)
        self.tools_list.bind('<<ListboxSelect>>', self._on_select_tool)

        # Right: previews (generated vs existing) + controls
        right = tk.Frame(self, bg='#20232a')
        right.pack(side='left', fill='both', expand=True, padx=8, pady=8)

        previews = tk.Frame(right, bg='#20232a')
        previews.pack(fill='both', expand=False)

        # Generated preview column
        gen_col = tk.Frame(previews, bg='#20232a')
        gen_col.pack(side='left', padx=8)
        tk.Label(gen_col, text='Generated Preview', fg='#e6edf3', bg='#20232a', font=('Segoe UI', 9, 'bold')).pack()
        self.preview_label = tk.Label(gen_col, bg='#0d1117')
        self.preview_label.pack(pady=(4,8))

        # Existing icon column
        exist_col = tk.Frame(previews, bg='#20232a')
        exist_col.pack(side='left', padx=8)
        tk.Label(exist_col, text='Existing Icon (icons/)', fg='#e6edf3', bg='#20232a', font=('Segoe UI', 9, 'bold')).pack()
        self.existing_label = tk.Label(exist_col, bg='#0d1117')
        self.existing_label.pack(pady=(4,8))

        btn_row = tk.Frame(right, bg='#20232a')
        btn_row.pack()
        tk.Button(btn_row, text='Regenerate', command=self.regenerate, width=14).pack(side='left', padx=4)
        tk.Button(btn_row, text='Randomize', command=self.randomize, width=14).pack(side='left', padx=4)
        tk.Button(btn_row, text='Save to icons/', command=self.save_to_icons, width=16).pack(side='left', padx=4)
        tk.Button(btn_row, text='Next Missing Icon', command=self.goto_next_missing_icon, width=18).pack(side='left', padx=4)

        self.status = tk.Label(right, text='', fg='#e6edf3', bg='#20232a', anchor='w')
        self.status.pack(fill='x', pady=(8,0))

    def _populate_tools(self):
        tools = infer_all_tools()
        for t in tools:
            self.tools_list.insert('end', t)
        if tools:
            self.tools_list.selection_set(0)
            self._select_tool(tools[0])

    def _on_select_tool(self, event=None):
        sel = self.tools_list.curselection()
        if not sel:
            return
        tool = self.tools_list.get(sel[0])
        self._select_tool(tool)

    def _select_tool(self, tool_file: str):
        self.current_tool = tool_file
        self.current_layers = composition_from_tool(tool_file)
        self._update_preview()
        print(f"[ui] Selected {tool_file}")

    def _update_preview(self):
        if not self.current_tool:
            return
        # Compose using current layers (which may be override randomized)
        unique_emojis = {layer['emoji'] for layer in self.current_layers}
        for em in unique_emojis:
            ensure_temp_emoji_image(em, 128)
        img = compose_icon_for_tool(self.current_tool, self.preview_size, layers_override=self.current_layers)
        # show
        imgtk = ImageTk.PhotoImage(img)
        self._preview_tk = imgtk
        self.preview_label.configure(image=imgtk)
        # Also update the existing icon preview from icons/
        self._update_existing_icon_preview()
        self.status.configure(text=f"Preview: {self.current_tool} ({self.preview_size}x{self.preview_size})")

    def _update_existing_icon_preview(self):
        """Load existing icon from icons/<tool_stem>.png if it exists, else clear."""
        try:
            if not self.current_tool:
                return
            stem = Path(self.current_tool).stem
            icon_path = Path(ICON_OUTPUT_DIR) / f"{stem}.png"
            max_side = max(1, self.preview_size)
            canvas = Image.new('RGBA', (max_side, max_side), (0, 0, 0, 0))
            if icon_path.exists():
                img = Image.open(icon_path).convert('RGBA')
                img.thumbnail((max_side, max_side), Image.LANCZOS)
                x = (max_side - img.width) // 2
                y = (max_side - img.height) // 2
                canvas.alpha_composite(img, (x, y))
            # else: keep transparent placeholder canvas
            imgtk = ImageTk.PhotoImage(canvas)
            self._existing_tk = imgtk
            self.existing_label.configure(image=imgtk)
        except Exception as e:
            print(f"[warn] Failed to load existing icon: {e}")
            # Show a fixed-size red-tinted placeholder on error
            max_side = max(1, self.preview_size)
            err_canvas = Image.new('RGBA', (max_side, max_side), (96, 32, 32, 255))
            imgtk = ImageTk.PhotoImage(err_canvas)
            self._existing_tk = imgtk
            self.existing_label.configure(image=imgtk)

    def regenerate(self):
        # Recompose using the same layers (can add slight noise if desired)
        if not self.current_tool:
            return
        print(f"[ui] Regenerate {self.current_tool}")
        self._update_preview()

    def randomize(self):
        if not self.current_tool:
            return
        emoji_str = TOOL_EMOJIS.get(self.current_tool, '')
        emojis = [ch for ch in emoji_str if ch.strip()]
        self.current_layers = randomize_composition(emojis)
        print(f"[ui] Randomized composition for {self.current_tool}")
        self._update_preview()

    def save_to_icons(self):
        if not self.current_tool:
            return
        print(f"[ui] Saving icon for {self.current_tool} to icons/")
        save_icon(self.current_tool, ICON_OUTPUT_DIR, self.preview_size, overwrite=True, layers_override=self.current_layers)

    # --- New helper actions ---
    def _has_existing_icon(self, tool_file: str) -> bool:
        try:
            stem = Path(tool_file).stem
            icon_path = Path(ICON_OUTPUT_DIR) / f"{stem}.png"
            return icon_path.exists()
        except Exception:
            return False

    def _all_tools(self) -> List[str]:
        items = []
        try:
            count = self.tools_list.size()
            for i in range(count):
                items.append(self.tools_list.get(i))
        except Exception:
            pass
        return items

    def goto_next_missing_icon(self):
        tools = self._all_tools()
        if not tools:
            print('[ui] No tools in list')
            return
        # Determine starting index (after current selection)
        sel = self.tools_list.curselection()
        start = (sel[0] + 1) if sel else 0
        n = len(tools)
        found_index = None
        for offset in range(n):
            idx = (start + offset) % n
            tool = tools[idx]
            if not self._has_existing_icon(tool):
                found_index = idx
                break
        if found_index is None:
            print('[ui] All tools have icons already. Great!')
            self.status.configure(text='All tools have icons already.')
            return
        # Select and focus the found item
        self.tools_list.selection_clear(0, 'end')
        self.tools_list.selection_set(found_index)
        self.tools_list.activate(found_index)
        self.tools_list.see(found_index)
        tool = tools[found_index]
        print(f"[ui] Next missing icon: {tool}")
        self._select_tool(tool)

if __name__ == '__main__':
    # No CLI. Launch UI directly.
    app = IconComposerUI()
    app.mainloop()