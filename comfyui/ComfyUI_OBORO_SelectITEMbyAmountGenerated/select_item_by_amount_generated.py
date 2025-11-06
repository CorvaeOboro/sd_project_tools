import re
from pathlib import Path

class OBOROSelectITEMbyAmountGenerated:
    """
    SELECT ITEM BY AMOUNT GENERATED
    Within a project structure, prioritize items missing ranked images or with low generation coverage.
    
    Example PROJECT structure (CATEGORY > GROUP > ITEM ( with upscale ) ): 

      CATEGORY/                       # e.g., ART, UI, ENV
        GROUP/                        # e.g., ART_Food
          ITEM.psd                    # Base PSD for the item (original source)
          ITEM.bmp                    # (Optional) Base BMP preview or export
          ITEM_B.psd
          ITEM_B.bmp
          Upscale/
            ITEM.psd                  # Upscaled PSD for the same ITEM name
            ITEM.png                  # Upscaled PNG (preferred preview)
            ITEM/                     # Folder named after the ITEM
              prompt/
                prompt_sdxl.md        # prompt text for the sdxl model type 
              gen/
                01/                   # Best-ranked generated images for this upscaled ITEM
                  <ranked_images>.png
            ITEM_B.psd                # Upscaled PSD for the same ITEM name
            ITEM_B.png                # Upscaled PNG (preferred preview)
            ITEM_B/                   # Folder named after the ITEM
              gen/
                <unranked_images>.png
                01/                   # Best-ranked generated images for this upscaled ITEM
                  <ranked_good_images>.png
                02/                   # Second-best ranked generated images for this upscaled ITEM
                  <ranked_bad_images>.png

    Definitions and discovery:
    - ITEM is determined primarily from the Upscale folder contents:
      - If Upscale/ITEM.psd or Upscale/ITEM.png exists, ITEM is considered present in Upscale.
      - The corresponding base files are located in GROUP (e.g., GROUP/ITEM.psd, GROUP/ITEM.bmp).
    - Target image for editing is typically Upscale/ITEM.psd (the upscaled PSD).
    - Ranked generated outputs are stored under Upscale/ITEM/gen/01/*.png.
    - If gen/01 contains no files, the ITEM is considered unreviewed for rankings.

    Selection goals:
    - Items with fewer gen/01 images to surface assets needing attention.
    - Items matching a checkpoint-specific prompt (.md) for SDXL/sd1.5/flux/video
    - Items with low total generations in gen/ and ITEM Upscale
    - Items without any gen/01 ranked images
    - Down-rank items with large ranked histories in gen/02 over time

    PROJECT STRUCTURE EXAMPLE B
        base_dir/                       # example = POTION
            ITEM/                        # example = PotionA
                ITEM.png                    # target image
                prompt/
                    prompt_sdxl.md        # prompt text for the sdxl model type 
                gen/
                    01/                   # Best-ranked generated images for this upscaled ITEM
                        <ranked_images>.png


    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'base_dir': ('STRING', {'default': str(Path(__file__).parent.parent)}),
                'use_complex_structure': ('BOOLEAN', {'default': False}),
                'require_prompt_sdxl': ('BOOLEAN', {'default': False}),
                'require_prompt_flux': ('BOOLEAN', {'default': False}),
                'require_prompt_sd15': ('BOOLEAN', {'default': False}),
                'require_prompt_video': ('BOOLEAN', {'default': False}),
                'max_images_target': ('INT', {'default': 5, 'min': 1, 'max': 1000, 'step': 1}),
                'seed': ('INT', {'default': 0, 'min': 0, 'max': 0xffffffffffffffff}),
            },
            'optional': {
                'debug': ('BOOLEAN', {'default': False}),
            }
        }

    RETURN_TYPES = ('STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('item_png_filepath', 'item_folder', 'item_name')
    FUNCTION = 'select'
    CATEGORY = 'OBORO'

    def select(self, base_dir, use_complex_structure=False, require_prompt_sdxl=False, require_prompt_flux=False, 
               require_prompt_sd15=False, require_prompt_video=False, max_images_target=5, seed=0, debug=False):
        root = Path(base_dir).expanduser()

        # Build prompt requirements dict
        prompt_requirements = {
            'sdxl': require_prompt_sdxl,
            'flux': require_prompt_flux,
            'sd15': require_prompt_sd15,
            'video': require_prompt_video,
        }

        # Discover and sort items based on structure type
        if use_complex_structure:
            items = self._discover_items_complex(
                root,
                include_categories=None,
                include_groups=None,
                prompt_requirements=prompt_requirements,
                debug=debug,
            )
        else:
            items = self._discover_items_simple(
                root,
                prompt_requirements=prompt_requirements,
                debug=debug,
            )
        schedule = self._select_by_amount(items, max_images_target=max_images_target, debug=debug)

        # Use seed as index into schedule (ComfyUI increments seed with control_after_generate)
        top = None
        item_name = ''
        item_png_filepath = ''
        item_folder = ''
        
        if schedule:
            # Use seed modulo schedule length to select item
            idx = seed % len(schedule)
            top = schedule[idx]
            item_name = top.get('name', '')
            item_png_filepath = top.get('item_png', '')  # Get the PNG path from item data
            
            # Compute folder from available paths
            try:
                if use_complex_structure:
                    # Complex structure: CATEGORY/GROUP/Upscale/ITEM
                    base_psd = top.get('base_psd') or ''
                    item_psd = top.get('item_psd') or ''
                    existing_png = top.get('item_png') or ''
                    group_dir = None
                    if base_psd:
                        group_dir = Path(base_psd).parent
                    elif item_psd:
                        group_dir = Path(item_psd).parent.parent
                    elif existing_png:
                        group_dir = Path(existing_png).parent.parent
                    if group_dir:
                        item_folder = str(group_dir / 'Upscale')
                    # Fill missing png path using folder + name
                    if not item_png_filepath and item_folder and item_name:
                        item_png_filepath = str(Path(item_folder) / f"{item_name}.png")
                else:
                    # Simple structure: base_dir/ITEM
                    item_folder = str(root)
                    if not item_png_filepath and item_name:
                        item_png_filepath = str(root / item_name / f"{item_name}.png")
            except Exception as e:
                print(f"[SelectITEMbyAmountGenerated][ERROR] Building outputs: {e}")
            
            # Debug output
            if debug:
                total_images = top.get('gen_count', 0) + top.get('gen01_count', 0) + top.get('gen02_count', 0)
                print(f"\n[SelectITEMbyAmountGenerated] Schedule: {len(schedule)} entries (target={max_images_target})")
                print(f"[SelectITEMbyAmountGenerated] Seed: {seed} -> Index: {idx}")
                print(f"[SelectITEMbyAmountGenerated] Selected: {item_name} (total_images={total_images})")
                print(f"[SelectITEMbyAmountGenerated] Path: {item_png_filepath}")
                # Show next 3 items
                next_items = []
                for i in range(1, 4):
                    if idx + i < len(schedule):
                        next_items.append(schedule[idx + i].get('name', ''))
                if next_items:
                    print(f"[SelectITEMbyAmountGenerated] Next: {', '.join(next_items)}")
        
        return (item_png_filepath, item_folder, item_name)


    @staticmethod
    def _safe_str(p: Path | None) -> str:
        return str(p) if p else ""

    @staticmethod
    def _count_files(folder: Path) -> int:
        try:
            if not folder.exists() or not folder.is_dir():
                return 0
            return sum(1 for f in folder.iterdir() if f.is_file())
        except Exception as e:
            print(f"[SelectITEMbyAmountGenerated][ERROR] Counting files in '{folder}': {e}")
            return 0
    
    @staticmethod
    def _build_gen_stats(gen_root: Path, gen01: Path, gen02: Path, prompt_folder: Path) -> dict:
        """Build common generation statistics dictionary for an item."""
        return {
            'gen_folder': OBOROSelectITEMbyAmountGenerated._safe_str(gen_root if gen_root.exists() else None),
            'gen_count': int(OBOROSelectITEMbyAmountGenerated._count_files(gen_root)) if gen_root.exists() else 0,
            'gen01_folder': OBOROSelectITEMbyAmountGenerated._safe_str(gen01 if gen01.exists() else None),
            'gen01_count': int(OBOROSelectITEMbyAmountGenerated._count_files(gen01)),
            'gen02_folder': OBOROSelectITEMbyAmountGenerated._safe_str(gen02 if gen02.exists() else None),
            'gen02_count': int(OBOROSelectITEMbyAmountGenerated._count_files(gen02)),
            'prompt_folder': OBOROSelectITEMbyAmountGenerated._safe_str(prompt_folder if prompt_folder.exists() else None),
        }
    
    @staticmethod
    def _check_prompt_requirements(prompt_folder: Path, prompt_requirements: dict, name: str, debug: bool) -> bool:
        """Check if item meets prompt requirements. Returns True if item should be included."""
        # If no requirements are enabled, include all items
        if not any(prompt_requirements.values()):
            return True
        
        # Check which prompt files exist
        prompt_files = {
            'sdxl': prompt_folder / 'prompt_sdxl.md',
            'flux': prompt_folder / 'prompt_flux.md',
            'sd15': prompt_folder / 'prompt_sd15.md',
            'video': prompt_folder / 'prompt_video.md',
        }
        
        # Check if all required prompts exist
        missing_prompts = []
        for model_type, required in prompt_requirements.items():
            if required:
                prompt_file = prompt_files[model_type]
                if not (prompt_file.exists() and prompt_file.is_file()):
                    missing_prompts.append(model_type)
        
        # If any required prompts are missing, skip this item
        if missing_prompts:
            if debug:
                print(f"  [Skip] {name}: missing required prompts: {', '.join(missing_prompts)}")
            return False
        
        return True

    @staticmethod
    def _discover_items_simple(project_root: Path,
                               prompt_requirements: dict = None,
                               debug: bool = False):
        """
        Discover items in simple structure: base_dir/ITEM/ITEM.png
        PROJECT STRUCTURE B:
            base_dir/
                ITEM/
                    ITEM.png
                    prompt/
                        prompt_sdxl.md
                    gen/
                        01/
                            <ranked_images>.png
        """
        items = []
        root = Path(project_root)
        if not root.exists():
            return items

        project_name = root.name

        if debug:
            print(f"[SelectITEMbyAmountGenerated] Discovering items (SIMPLE structure) in: '{project_name}' at {root}")

        # Iterate through immediate subdirectories as ITEMs
        for item_dir in sorted([p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.')], key=lambda x: x.name.lower()):
            name = item_dir.name
            item_png = item_dir / f"{name}.png"
            gen_root = item_dir / 'gen'
            gen01 = gen_root / '01'
            gen02 = gen_root / '02'
            prompt_folder = item_dir / 'prompt'
            
            # Filter: require existing prompt files if requested
            if prompt_requirements is None:
                prompt_requirements = {}
            if not OBOROSelectITEMbyAmountGenerated._check_prompt_requirements(prompt_folder, prompt_requirements, name, debug):
                continue

            items.append({
                'project': project_name,
                'category': '',  # No category in simple structure
                'group': '',     # No group in simple structure
                'name': name,
                'base_psd': '',  # No base PSD in simple structure
                'item_psd': '',  # No item PSD in simple structure
                'item_png': OBOROSelectITEMbyAmountGenerated._safe_str(item_png if item_png.exists() else None),
                **OBOROSelectITEMbyAmountGenerated._build_gen_stats(gen_root, gen01, gen02, prompt_folder),
            })
            if debug:
                print(f"  [Item] {name}: gen={items[-1]['gen_count']}, gen01={items[-1]['gen01_count']}, gen02={items[-1]['gen02_count']}, prompt={'yes' if items[-1]['prompt_folder'] else 'no'}")
        return items

    @staticmethod
    def _discover_items_complex(project_root: Path,
                                include_categories=None,
                                include_groups=None,
                                prompt_requirements: dict = None,
                                debug: bool = False):
        """
        Discover items in complex structure: CATEGORY/GROUP/Upscale/ITEM
        PROJECT STRUCTURE A (Complex):
            CATEGORY/
                GROUP/
                    ITEM.psd
                    Upscale/
                        ITEM.psd
                        ITEM.png
                        ITEM/
                            prompt/
                                prompt_sdxl.md
                            gen/
                                01/
                                    <ranked_images>.png
        """
        items = []
        root = Path(project_root)
        if not root.exists():
            return items

        HEX_PREFIX_LOCAL = "0x"
        HEX_SUFFIX_RE_LOCAL = re.compile(r"0x[0-9A-Fa-f]+$")
        HEX_FILTER_ENABLED_LOCAL = False

        project_name = root.name

        if debug:
            print(f"[SelectITEMbyAmountGenerated] Discovering items (COMPLEX structure) in project: '{project_name}' at {root}")

        for category in sorted([p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.')], key=lambda x: x.name.lower()):
            if include_categories and category.name not in include_categories:
                continue
            if debug:
                print(f"  [Category] {category.name}")
            for group in sorted([p for p in category.iterdir() if p.is_dir() and not p.name.startswith('.')], key=lambda x: x.name.lower()):
                if include_groups and group.name not in include_groups:
                    continue
                upscale = group / 'Upscale'
                names = set()
                if upscale.exists():
                    for p in list(upscale.glob('*.png')) + list(upscale.glob('*.psd')):
                        if HEX_FILTER_ENABLED_LOCAL and HEX_PREFIX_LOCAL not in p.name:
                            continue
                        names.add(p.stem)
                    for p in group.glob('*.psd'):
                        try:
                            if HEX_SUFFIX_RE_LOCAL.search(p.stem):
                                if HEX_FILTER_ENABLED_LOCAL and HEX_PREFIX_LOCAL not in p.name:
                                    continue
                                names.add(p.stem)
                        except Exception:
                            pass
                else:
                    for p in list(group.glob('*.psd')) + list(group.glob('*.bmp')):
                        if HEX_FILTER_ENABLED_LOCAL and HEX_PREFIX_LOCAL not in p.name:
                            continue
                        names.add(p.stem)
                if debug:
                    print(f"    [Group] {group.name} -> candidates: {len(names)}")
                for name in sorted(names):
                    base_psd = group / f"{name}.psd"
                    item_psd = upscale / f"{name}.psd"
                    item_png = upscale / f"{name}.png"
                    gen_root = upscale / name / 'gen'
                    gen01 = gen_root / '01'
                    gen02 = gen_root / '02'
                    prompt_folder = upscale / name / 'prompt'
                    # Filter: require existing prompt files if requested
                    if prompt_requirements is None:
                        prompt_requirements = {}
                    if not OBOROSelectITEMbyAmountGenerated._check_prompt_requirements(prompt_folder, prompt_requirements, name, debug):
                        continue

                    items.append({
                        'project': project_name,
                        'category': category.name,
                        'group': group.name,
                        'name': name,
                        'base_psd': OBOROSelectITEMbyAmountGenerated._safe_str(base_psd if base_psd.exists() else None),
                        'item_psd': OBOROSelectITEMbyAmountGenerated._safe_str(item_psd if item_psd.exists() else None),
                        'item_png': OBOROSelectITEMbyAmountGenerated._safe_str(item_png if item_png.exists() else None),
                        **OBOROSelectITEMbyAmountGenerated._build_gen_stats(gen_root, gen01, gen02, prompt_folder),
                    })
                    if debug:
                        print(f"      [Item] {name}: gen01={items[-1]['gen01_count']}, gen02={items[-1]['gen02_count']}, prompt={'yes' if items[-1]['prompt_folder'] else 'no'}")
        return items

    @staticmethod
    def _select_by_amount(all_items, max_images_target=5, debug: bool = False):
        def sort_key(it):
            missing_item = 0 if (it.get('item_psd') or it.get('item_png')) else 1
            # Priority: gen_count (total unranked), gen01_count, missing_item, gen02_count
            return (
                it.get('gen_count', 0),  # Primary: total unranked generations (low gen/)
                it.get('gen01_count', 0),  # Secondary: ranked gen01 (low)
                -missing_item,  # Tertiary: missing item files (prioritize existing)
                it.get('gen02_count', 0),  # Quaternary: ranked gen02 (low)
                it.get('group', ''),
                it.get('name', ''),
            )
        sorted_items = sorted(all_items, key=sort_key)
        
        # Create balanced schedule: items with fewer images appear more frequently
        schedule = OBOROSelectITEMbyAmountGenerated._create_balanced_schedule(sorted_items, max_images_target=max_images_target, debug=debug)
        
        if debug:
            print(f"[SelectITEMbyAmountGenerated] Discovered {len(all_items)} items, created schedule with {len(schedule)} entries")
        return schedule
    
    @staticmethod
    def _create_balanced_schedule(items, max_images_target=5, debug: bool = False):
        """Create a balanced schedule where items with fewer images appear more frequently."""
        if not items:
            return []
        
        # Calculate total image count for each item (gen + gen01 + gen02)
        item_counts = []
        for item in items:
            total = item.get('gen_count', 0) + item.get('gen01_count', 0) + item.get('gen02_count', 0)
            item_counts.append((item, total))
        
        # Use max_images_target as the balancing target (or actual max if higher)
        actual_max = max(count for _, count in item_counts) if item_counts else 0
        max_count = max(max_images_target, actual_max)
        
        # Calculate repetitions for each item (items with fewer images get more repetitions)
        schedule_entries = []
        for item, count in item_counts:
            repetitions = max_count - count + 1  # +1 ensures even max_count items appear once
            schedule_entries.append((item, repetitions))
        
        if debug:
            print(f"[SelectITEMbyAmountGenerated] Balanced Schedule Calculation:")
            print(f"  Target image count: {max_images_target}")
            print(f"  Actual max image count: {actual_max}")
            print(f"  Using max count: {max_count}")
            for item, reps in schedule_entries[:5]:  # Show first 5
                total = item.get('gen_count', 0) + item.get('gen01_count', 0) + item.get('gen02_count', 0)
                print(f"    {item.get('name')}: total_images={total}, repetitions={reps}")
        
        # Create interleaved schedule using round-robin with repetition counts
        schedule = []
        remaining = [(item, reps) for item, reps in schedule_entries]
        
        while remaining:
            # Add one entry from each item that still has repetitions left
            next_remaining = []
            for item, reps in remaining:
                schedule.append(item)
                if reps > 1:
                    next_remaining.append((item, reps - 1))
            remaining = next_remaining
        
        if debug:
            print(f"[SelectITEMbyAmountGenerated] Created schedule with {len(schedule)} entries")
            # Show first 10 entries
            print(f"[SelectITEMbyAmountGenerated] First 10 schedule entries:")
            for i, item in enumerate(schedule[:10]):
                total = item.get('gen_count', 0) + item.get('gen01_count', 0) + item.get('gen02_count', 0)
                print(f"    {i}: {item.get('name')} (total_images={total})")
        
        return schedule

NODE_CLASS_MAPPINGS = {
    'OBOROSelectByAmount': OBOROSelectITEMbyAmountGenerated,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'OBOROSelectByAmount': 'Select ITEM By Amount Generated',
}

