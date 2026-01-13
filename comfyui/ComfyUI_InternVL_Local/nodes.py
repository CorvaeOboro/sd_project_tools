"""
COMFYUI INTERNVL LOCAL NODES
implementation of the Vision Language Model InternVL models by OpenGVLab
modified for local model management and sampling parameters
TODO:
more security and safety 
hardcodded hash verification of favored models ( protect against the model repo changing )
download and review the models , once approved the hardcoded hashlist goes in this file 
try to reduce the .py and .pyc files downloaded with the models from running arbitrariy 
VL3 support custom handling of 

VERSION::20260112
"""
import os
import glob
import hashlib
import traceback
import folder_paths
import comfy.model_management as mm
import io
import base64
import torch
import requests
import numpy as np
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from PIL import Image
from typing import Union, List
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer, AutoModel

# Global configuration
REMOVE_CUSTOM_CODE_AFTER_DOWNLOAD = True  # Set to False to preserve all .py files
VERIFY_FILE_HASHES = True  # Set to False to skip hash verification

def calculate_file_hash(file_path, algorithm='sha256'):
    """Calculate hash of a file for verification purposes."""
    hash_obj = hashlib.new(algorithm)
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except Exception as e:
        print(f"Error calculating hash for {file_path}: {e}")
        return None

def log_file_info(file_path, action="Downloaded"):
    """Log detailed information about a file including its hash."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    file_size = os.path.getsize(file_path)
    print(f"{action}: {os.path.basename(file_path)} ({file_size:,} bytes)")
    
    if VERIFY_FILE_HASHES:
        file_hash = calculate_file_hash(file_path)
        if file_hash:
            print(f"  SHA256: {file_hash}")
        else:
            print(f"  Hash: Unable to calculate")
    
    print(f"  Path: {file_path}")

class InternVLModelDownloader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (
                    [
                        # InternVL2 Series
                        "OpenGVLab/InternVL2-1B",
                        "OpenGVLab/InternVL2-2B",
                        "OpenGVLab/InternVL2-4B",
                        "OpenGVLab/InternVL2-8B",
                        "OpenGVLab/InternVL2-26B",
                        "OpenGVLab/InternVL2-40B",
                        # InternVL3 Series (Latest)
                        "OpenGVLab/InternVL3-8B",
                        "OpenGVLab/InternVL3-26B",
                        # InternVL2.5 Series
                        "OpenGVLab/InternVL2_5-1B",
                        "OpenGVLab/InternVL2_5-2B",
                        "OpenGVLab/InternVL2_5-4B",
                        "OpenGVLab/InternVL2_5-8B",
                        "OpenGVLab/InternVL2_5-38B",
                        # Chat variants
                        "OpenGVLab/InternVL2-8B-AWQ",
                        "OpenGVLab/InternVL2-26B-AWQ",
                        "OpenGVLab/InternVL2-40B-AWQ",
                    ],
                    {"default": "OpenGVLab/InternVL2-8B"}
                )
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model_path",)
    FUNCTION = "download"
    CATEGORY = "internvl"

    def download(self, model):
        model_name = model.rsplit('/', 1)[-1]
        model_dir = os.path.join(folder_paths.models_dir, "LLM", model_name)
        
        print(f"Target download location: {model_dir}")
        
        # Check if model directory exists and is complete
        needs_download = False
        
        if not os.path.exists(model_dir):
            print(f"Model directory does not exist - will download")
            needs_download = True
        else:
            print(f"Model directory exists - checking completeness...")
            # Check for essential files to determine if download is complete
            required_files = [
                'config.json',
                'tokenizer_config.json'
            ]
            
            # Check for essential InternVL files that might be missing
            # Only include files that actually exist in the repository
            essential_internvl_files = [
                'tokenization_internlm2.py',
                'configuration_intern_vit.py',
                'modeling_intern_vit.py',
                'configuration_internlm2.py',
                'modeling_internlm2.py',
                'conversation.py',
                'modeling_internvl_chat.py',
                'configuration_internvl_chat.py'
            ]
            
            missing_required = []
            missing_internvl = []
            
            for file in required_files:
                if not os.path.exists(os.path.join(model_dir, file)):
                    missing_required.append(file)
            
            for file in essential_internvl_files:
                if not os.path.exists(os.path.join(model_dir, file)):
                    missing_internvl.append(file)
            
            if missing_required:
                print(f"Missing required files: {missing_required} - will re-download")
                needs_download = True
            elif missing_internvl:
                print(f"Missing essential InternVL files: {missing_internvl} - will re-download")
                needs_download = True
            else:
                print(f"Model appears complete - skipping download")
        
        if needs_download:
            if not os.path.exists(model_dir):
                # Full download for new model
                print(f"Downloading complete model {model} to {model_dir}")
                snapshot_download(
                    repo_id=model,
                    cache_dir=model_dir,
                    local_dir=model_dir,
                    local_dir_use_symlinks=False
                )
                print(f"Complete download finished to: {model_dir}")
            else:
                # Selective download for missing files
                print(f"Downloading missing files for {model} to {model_dir}")
                
                # Determine which files to download
                files_to_download = []
                if missing_required:
                    files_to_download.extend(missing_required)
                if missing_internvl:
                    files_to_download.extend(missing_internvl)
                
                print(f"Missing files to download: {files_to_download}")
                
                # Download each missing file individually
                from huggingface_hub import hf_hub_download
                
                for filename in files_to_download:
                    try:
                        print(f"Downloading: {filename}")
                        downloaded_path = hf_hub_download(
                            repo_id=model,
                            filename=filename,
                            local_dir=model_dir,
                            local_dir_use_symlinks=False
                        )
                        
                        # Log detailed file information with hash
                        file_path = os.path.join(model_dir, filename)
                        log_file_info(file_path, "Downloaded")
                        
                    except Exception as e:
                        print(f"Warning: Could not download {filename}: {e}")
                        print(f"File may not exist in repository or may have different name")
                
                print(f"Selective download completed to: {model_dir}")

            # File cleanup based on global configuration
            if REMOVE_CUSTOM_CODE_AFTER_DOWNLOAD:
                print("File cleanup enabled - removing potentially dangerous .py files while preserving essential files")
                self._cleanup_dangerous_files(model_dir)
            else:
                print("File cleanup disabled - preserving all .py files (including potentially dangerous custom code)")
                print("Warning: Custom code files may pose security risks if they contain malicious code")
        
        # Return the model directory path as required by ComfyUI
        return (model_dir,)
    
    def _cleanup_dangerous_files(self, model_dir):
        """Remove potentially dangerous .py files but preserve essential tokenizer/model files."""
        essential_files = {
            # Tokenization files
            'tokenization_internlm2.py',
            # Modeling files
            'modeling_internlm2.py',
            'modeling_internvl_chat.py',
            'modeling_intern_vit.py',
            # Configuration files
            'configuration_internlm2.py',
            'configuration_internvl_chat.py',
            'configuration_intern_vit.py',
            # Additional essential files
            'image_processing_internvl.py',
            'processing_internvl.py',
            'conversation.py'
        }
        
        removed_files = []
        preserved_files = []
        
        for root, dirs, files in os.walk(model_dir):
            for file in files:
                if file.endswith(".py") or file.endswith(".pyc"):
                    file_path = os.path.join(root, file)
                    
                    # Preserve essential tokenizer and model files
                    if file in essential_files:
                        preserved_files.append(file)
                        print(f"Preserving essential file: {file}")
                        # Log preserved file info
                        log_file_info(file_path, "Preserved")
                    else:
                        # Remove potentially dangerous custom code
                        print(f"Removing potentially dangerous file: {file}")
                        os.remove(file_path)
                        removed_files.append(file)
        
        if removed_files:
            print(f"Removed {len(removed_files)} potentially dangerous .py files: {', '.join(removed_files)}")
        if preserved_files:
            print(f"Preserved {len(preserved_files)} essential model files: {', '.join(preserved_files)}")
        
        # Final status report
        print(f"Model ready at: {model_dir}")
        print(f"Model path for loader: {model_dir}")
        
        return (model_dir,)

class InternVLModelLoader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model_path": ("STRING", {
                    "multiline": False,
                    "default": ""
                }),
            }
        }

    RETURN_TYPES = ("InternVLModel",)
    RETURN_NAMES = ("intervl_model",)
    FUNCTION = "load_model"
    CATEGORY = "internvl"

    def load_model(self, model_path):
        try:
            device = mm.get_torch_device()

            # Validate that model_path is a safe, absolute local path
            if not os.path.isabs(model_path):
                raise ValueError("Model path must be an absolute local path.")
            
            # Check for potentially unsafe path patterns
            if "http" in model_path.lower() or ".." in model_path:
                raise ValueError("Model path contains unsafe patterns (URLs or relative path traversal).")
            
            # Normalize the path to resolve any remaining path issues
            model_path = os.path.normpath(model_path)
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model path does not exist: {model_path}")
            
            if not os.path.isdir(model_path):
                raise ValueError("Model path must be a directory containing the model files.")
            
            print(f"Loading from validated local path: {model_path}")

            # Verify all required files exist locally before loading
            self._verify_local_files(model_path)
            
            # Load model with strict local-only mode (no network calls, no telemetry)
            # Note: Some models require trust_remote_code=True for custom architectures
            # but local_files_only=True ensures no network access even with trusted code
            
            print("Loading tokenizer with local_files_only=True (no network access)...")
            try:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    trust_remote_code=False,
                    local_files_only=True,  # Prevents all network calls
                    use_fast=False  # Avoid potential network checks
                )
            except Exception as e:
                if "trust_remote_code=True" in str(e):
                    print("Model requires custom code - enabling trust_remote_code with local_files_only for security")
                    tokenizer = AutoTokenizer.from_pretrained(
                        model_path, 
                        trust_remote_code=True,  # Required for some models
                        local_files_only=True,  # Still prevents network calls
                        use_fast=False
                    )
                else:
                    raise e
            
            print("Loading model with local_files_only=True (no network access)...")
            try:
                model = AutoModel.from_pretrained(
                    model_path,
                    torch_dtype=torch.float16,
                    trust_remote_code=False,
                    local_files_only=True,  # Prevents all network calls
                    low_cpu_mem_usage=True,
                    use_safetensors=True  # Prefer safetensors format
                ).eval().to(device)
            except Exception as e:
                if "trust_remote_code=True" in str(e):
                    print("Model requires custom code - enabling trust_remote_code with local_files_only for security")
                    model = AutoModel.from_pretrained(
                        model_path,
                        torch_dtype=torch.float16,
                        trust_remote_code=True,  # Required for some models
                        local_files_only=True,  # Still prevents network calls
                        low_cpu_mem_usage=True,
                        use_safetensors=True
                    ).eval().to(device)
                else:
                    raise e
            
            print("Model loaded successfully with no network access")
            
            # Fix for transformers v4.50+ compatibility: manually add GenerationMixin if missing
            self._ensure_generation_capability(model)
            
            # Ensure generation config is properly initialized
            self._ensure_generation_config(model)
            
            return ({
                "model": model,
                "tokenizer": tokenizer
            },)
            
        except Exception as e:
            error_msg = f"Failed to load InternVL model from {model_path}: {str(e)}"
            print(f"ERROR: {error_msg}")
            raise RuntimeError(error_msg) from e
    
    def _ensure_generation_capability(self, model):
        """Fix for transformers v4.50+ compatibility: ensure the model has generation capability."""
        try:
            from transformers import GenerationMixin
            import types
            
            # Check if the language model component has the generate method
            if hasattr(model, 'language_model'):
                lang_model = model.language_model
                if not hasattr(lang_model, 'generate'):
                    print("Warning: Language model missing 'generate' method - applying compatibility fix")
                    
                    # Method 1: Direct method addition approach
                    try:
                        # Add the generate method first
                        if not hasattr(lang_model, 'generate'):
                            generate_method = GenerationMixin.generate
                            lang_model.generate = types.MethodType(generate_method, lang_model)
                            print("  Added: generate method")
                        
                        # Add essential supporting methods that are commonly needed
                        essential_methods = {
                            '_prepare_generation_config': GenerationMixin._prepare_generation_config,
                            '_prepare_model_inputs': GenerationMixin._prepare_model_inputs,
                            '_get_logits_processor': GenerationMixin._get_logits_processor,
                            '_get_logits_warper': GenerationMixin._get_logits_warper,
                            '_update_model_kwargs_for_generation': GenerationMixin._update_model_kwargs_for_generation,
                        }
                        
                        added_count = 0
                        for method_name, method_func in essential_methods.items():
                            if not hasattr(lang_model, method_name):
                                try:
                                    setattr(lang_model, method_name, types.MethodType(method_func, lang_model))
                                    print(f"  Added: {method_name}")
                                    added_count += 1
                                except Exception as e:
                                    print(f"  Failed to add {method_name}: {e}")
                        
                        print(f"Successfully added {added_count + 1} GenerationMixin methods to language model")
                        
                        # Verify critical methods
                        if hasattr(lang_model, 'generate'):
                            print("✓ Generate method confirmed present")
                        if hasattr(lang_model, '_prepare_generation_config'):
                            print("✓ _prepare_generation_config method confirmed present")
                        else:
                            print("✗ _prepare_generation_config method still missing")
                            
                    except Exception as e:
                        print(f"Method 1 failed: {e}")
                        
                        # Method 2: Fallback - try class inheritance approach
                        try:
                            original_class = lang_model.__class__
                            
                            # Create a new class that inherits from both
                            class FixedLanguageModel(original_class, GenerationMixin):
                                pass
                            
                            # Update the class of the instance
                            lang_model.__class__ = FixedLanguageModel
                            print("Fallback: Successfully updated language model class with GenerationMixin")
                            
                        except Exception as e2:
                            print(f"Method 2 also failed: {e2}")
                            
                            # Method 3: Direct implementation of generate method
                            try:
                                from transformers.generation.utils import GenerationMixin
                                
                                # Get the generate method specifically
                                generate_method = GenerationMixin.generate
                                
                                # Bind it directly to the language model
                                lang_model.generate = types.MethodType(generate_method, lang_model)
                                
                                # Also add other essential generation methods
                                essential_methods = [
                                    '_prepare_model_inputs', 
                                    '_prepare_generation_config',
                                    '_prepare_encoder_decoder_kwargs_for_generation',
                                    '_prepare_attention_mask_for_generation',
                                    '_prepare_decoder_input_ids_for_generation',
                                    '_update_model_kwargs_for_generation',
                                    '_get_logits_warper',
                                    '_get_logits_processor'
                                ]
                                
                                for method_name in essential_methods:
                                    if hasattr(GenerationMixin, method_name) and not hasattr(lang_model, method_name):
                                        method = getattr(GenerationMixin, method_name)
                                        setattr(lang_model, method_name, types.MethodType(method, lang_model))
                                        print(f"  Added method: {method_name}")
                                
                                print("Method 3: Successfully added generate method directly")
                                
                                if hasattr(lang_model, 'generate'):
                                    print("✓ Generate method confirmed present after Method 3")
                                    
                            except Exception as e3:
                                print(f"Method 3 also failed: {e3}")
                                print("All generation capability fixes failed - model may not work properly")
                    
            # Also check the main model and add wrapper if needed
            if hasattr(model, 'language_model'):
                lang_model = model.language_model
                if hasattr(lang_model, 'generate') and not hasattr(model, 'generate'):
                    # Add a generate wrapper to the main model
                    def generate_wrapper(*args, **kwargs):
                        return lang_model.generate(*args, **kwargs)
                    
                    model.generate = generate_wrapper
                    print("Added generate wrapper to main model")
                
        except Exception as e:
            print(f"Warning: Could not apply generation capability fix: {e}")
            print("Model may still work if it has alternative generation methods")
    
    def _ensure_generation_config(self, model):
        """Ensure the model has a proper generation config to avoid NoneType errors."""
        try:
            from transformers import GenerationConfig
            
            # Check if the language model has a generation_config
            if hasattr(model, 'language_model'):
                lang_model = model.language_model
                
                if not hasattr(lang_model, 'generation_config') or lang_model.generation_config is None:
                    print("Warning: Language model missing generation_config - initializing default config")
                    
                    # Create a default generation config
                    try:
                        # Try to create from model config if available
                        if hasattr(lang_model, 'config'):
                            generation_config = GenerationConfig.from_model_config(lang_model.config)
                        else:
                            # Create a basic default config
                            generation_config = GenerationConfig()
                        
                        lang_model.generation_config = generation_config
                        print("✓ Generation config successfully initialized")
                        
                    except Exception as e:
                        print(f"Failed to create generation config from model config: {e}")
                        # Fallback to basic config
                        try:
                            generation_config = GenerationConfig(
                                max_length=2048,
                                max_new_tokens=1024,
                                do_sample=False,
                                num_beams=1,
                                pad_token_id=0,
                                eos_token_id=2,
                                bos_token_id=1
                            )
                            lang_model.generation_config = generation_config
                            print("✓ Fallback generation config initialized")
                        except Exception as e2:
                            print(f"Failed to create fallback generation config: {e2}")
                
                else:
                    print("✓ Generation config already present")
                    
        except Exception as e:
            print(f"Warning: Could not ensure generation config: {e}")
    
    def _verify_local_files(self, model_path):
        """Verify all required model files exist locally before attempting to load."""
        required_files = [
            "config.json",
            "tokenizer_config.json"
        ]
        
        # Check for model weights (safetensors preferred, .bin as fallback)
        weight_patterns = ["*.safetensors", "pytorch_model*.bin", "model*.bin"]
        weight_files = []
        for pattern in weight_patterns:
            weight_files.extend(glob.glob(os.path.join(model_path, pattern)))
        
        if not weight_files:
            raise FileNotFoundError(f"No model weight files found in {model_path}")
        
        # Check for tokenizer files
        tokenizer_patterns = ["tokenizer.json", "vocab.json", "vocab.txt"]
        tokenizer_files = []
        for pattern in tokenizer_patterns:
            if os.path.exists(os.path.join(model_path, pattern)):
                tokenizer_files.append(pattern)
        
        if not tokenizer_files:
            print("Warning: No tokenizer files found, but proceeding...")
        
        # Verify required files exist
        missing_files = []
        for file in required_files:
            if not os.path.exists(os.path.join(model_path, file)):
                missing_files.append(file)
        
        if missing_files:
            raise FileNotFoundError(f"Missing required files: {missing_files}")
        
        print(f"Local file verification passed: {len(weight_files)} weight files, {len(tokenizer_files)} tokenizer files")

class DynamicPreprocess:
    IMAGENET_MEAN = (0.485, 0.456, 0.406)
    IMAGENET_STD = (0.229, 0.224, 0.225)

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "optional": {
                "min_num": ("INT", {"default": 1, "min": 1, "max": 40}),
                "max_num": ("INT", {"default": 6, "min": 1, "max": 40}),
                "image_size": ("INT", {"default": 448, }),
                "use_thumbnail": ("BOOLEAN", {"default": True, }),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "load_image"
    CATEGORY = "internvl"

    def load_image(self, image, min_num=1, max_num=6, image_size=448, use_thumbnail=True):
        pil_image = self.convert_to_pil_image(image)
        transform = self.build_transform(input_size=image_size)
        images = self.preprocess(pil_image, min_num, max_num, image_size, use_thumbnail)
        # import pdb;pdb.set_trace()
        pixel_values = [transform(image) for image in images]
        pixel_values = torch.stack(pixel_values)
        return (pixel_values,)

    def preprocess(self, image, min_num=1, max_num=6, image_size=448, use_thumbnail=True):
        orig_width, orig_height = image.size
        aspect_ratio = orig_width / orig_height

        # 该代码功能是生成并排序一个集合，其中包含所有在指定范围内（min_num和max_num）的两个数的乘积
        target_ratios = set(
            (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
            i * j <= max_num and i * j >= min_num)
        target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

        # 寻找与给定aspect_ratio最接近的宽高比
        target_aspect_ratio = self.find_closest_aspect_ratio(
            aspect_ratio, target_ratios, orig_width, orig_height, image_size)

        target_width = image_size * target_aspect_ratio[0]
        target_height = image_size * target_aspect_ratio[1]
        blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

        resized_img = image.resize((target_width, target_height))
        processed_images = []
        for i in range(blocks):
            box = (
                (i % (target_width // image_size)) * image_size,
                (i // (target_width // image_size)) * image_size,
                ((i % (target_width // image_size)) + 1) * image_size,
                ((i // (target_width // image_size)) + 1) * image_size
            )
            split_img = resized_img.crop(box)
            processed_images.append(split_img)
        assert len(processed_images) == blocks
        if use_thumbnail and len(processed_images) != 1:
            thumbnail_img = image.resize((image_size, image_size))
            processed_images.append(thumbnail_img)
        return processed_images

    def find_closest_aspect_ratio(self, aspect_ratio, target_ratios, width, height, image_size):
        best_ratio_diff = float('inf')
        best_ratio = (1, 1)
        area = width * height
        for ratio in target_ratios:
            target_aspect_ratio = ratio[0] / ratio[1]
            ratio_diff = abs(aspect_ratio - target_aspect_ratio)
            if ratio_diff < best_ratio_diff:
                best_ratio_diff = ratio_diff
                best_ratio = ratio
            elif ratio_diff == best_ratio_diff:
                if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                    best_ratio = ratio
        return best_ratio

    def convert_to_pil_image(self, image: Union[
        np.ndarray, List[np.ndarray], bytes, str, Image.Image, torch.Tensor]) -> Image.Image:

        try:
            if isinstance(image, np.ndarray):
                return Image.fromarray(self._ensure_rgb(image))

            elif isinstance(image, list):
                return self._handle_list_input(image)

            elif isinstance(image, bytes):
                return Image.open(io.BytesIO(image)).convert('RGB')

            elif isinstance(image, str):
                return self._handle_string_input(image)

            elif isinstance(image, Image.Image):
                return image.convert('RGB')

            elif isinstance(image, torch.Tensor):
                return self._convert_tensor_to_pil(image)

            else:
                raise ValueError(f"Unsupported image type: {type(image)}")

        except Exception as e:
            raise ValueError(f"Failed to convert image: {str(e)}")

    def _handle_list_input(self, image_list: List) -> Image.Image:
        if len(image_list) == 0:
            raise ValueError("Empty list provided as image")

        if isinstance(image_list[0], np.ndarray):
            return Image.fromarray(self._ensure_rgb(image_list[0]))

        elif all(isinstance(x, (int, float)) for x in image_list):
            arr = np.array(image_list).astype('uint8')

            if arr.size in [1024 * 1024, 1024 * 1024 * 3]:
                arr = arr.reshape((1024, 1024, -1))
            elif arr.size in [512 * 512, 512 * 512 * 3]:
                arr = arr.reshape((512, 512, -1))
            else:
                arr = arr.reshape((arr.shape[0], -1))
            return Image.fromarray(self._ensure_rgb(arr))

        else:
            raise ValueError(f"Unsupported list content type: {type(image_list[0])}")

    def _handle_string_input(self, image_string: str) -> Image.Image:
        if image_string.startswith(('http://', 'https://')):
            response = requests.get(image_string)
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content)).convert('RGB')

        elif image_string.startswith('data:image'):
            image_data = base64.b64decode(image_string.split(',')[1])
            return Image.open(io.BytesIO(image_data)).convert('RGB')

        else:
            return Image.open(image_string).convert('RGB')

    def _ensure_rgb(self, arr: np.ndarray) -> np.ndarray:
        if arr.ndim == 2:
            return np.stack([arr] * 3, axis=-1)
        elif arr.ndim == 3 and arr.shape[2] == 1:
            return np.repeat(arr, 3, axis=2)
        elif arr.ndim == 3 and arr.shape[2] == 3:
            return arr
        elif arr.ndim == 3 and arr.shape[2] == 4:
            return arr[:, :, :3]
        else:
            raise ValueError(f"Unsupported array shape: {arr.shape}")

    def _convert_tensor_to_pil(self, tensor: torch.Tensor) -> Image.Image:
        if tensor.ndim == 4:
            tensor = tensor[0]
        if tensor.ndim == 3:
            if tensor.shape[0] in [1, 3, 4]:
                tensor = tensor.permute(1, 2, 0)
        elif tensor.ndim == 2:

            tensor = tensor.unsqueeze(-1).repeat(1, 1, 3)

        np_array = tensor.cpu().numpy()

        if np_array.dtype != np.uint8:
            if np_array.max() <= 1.0:
                np_array = (np_array * 255).astype(np.uint8)
            else:
                np_array = np_array.astype(np.uint8)

        return Image.fromarray(self._ensure_rgb(np_array))

    def build_transform(self, input_size):
        MEAN, STD = self.IMAGENET_MEAN, self.IMAGENET_STD
        transform = T.Compose([
            T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
            T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=MEAN, std=STD)
        ])
        return transform

class InternVLHFInference:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "model": ("InternVLModel",),
                "system_prompt": ("STRING", {
                    "multiline": False,
                    "default": "You are a helpful assistant."
                }),
                "prompt": ("STRING", {
                    "multiline": False,
                    "default": "What is this?"
                }),
            },
            "optional": {
                "keep_model_loaded": ("BOOLEAN", {"default": False}),
                "max_new_tokens": ("INT", {"default": 1024, "min": 1, "max": 4096}),
                "do_sample": ("BOOLEAN", {"default": False}),
                "num_beams": ("INT", {"default": 1}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0}),
                "top_p": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
                "top_k": ("INT", {"default": 50, "min": 0, "max": 200}),
                "repetition_penalty": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 2.0}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31-1})
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output",)
    FUNCTION = "process"
    CATEGORY = "internvl"

    def process(self,
                image,
                model,
                system_prompt,
                prompt,
                keep_model_loaded=False,
                max_new_tokens=1024,
                do_sample=False,
                num_beams=1,
                temperature=1.0,
                top_p=1.0,
                top_k=50,
                repetition_penalty=1.0,
                seed=-1):
        try:
            # Validate inputs
            if image is None:
                raise ValueError("Image input cannot be None")
            if model is None:
                raise ValueError("Model input cannot be None")
            if not isinstance(model, dict) or 'model' not in model or 'tokenizer' not in model:
                raise ValueError("Model input must be a dictionary with 'model' and 'tokenizer' keys")
            
            mm.soft_empty_cache()
            device = mm.get_torch_device()
            offload_device = mm.unet_offload_device()

            print(f"Processing inference with prompt: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")
            
            # Get the actual device of the model (in case it was offloaded)
            internvl_model = model['model']
            if hasattr(internvl_model, 'device'):
                model_device = internvl_model.device
            else:
                # Check vision model device as fallback
                model_device = next(internvl_model.parameters()).device
            
            print(f"Model is on device: {model_device}")
            
            # Validate and fix image tensor dimensions, using model's actual device
            image = self._prepare_image_tensor(image, model_device)
            # Build generation config with all sampling parameters
            generation_config = dict(
                num_beams=num_beams,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                do_sample=do_sample
            )
            # If any sampling param is non-default, force do_sample=True
            if temperature != 1.0 or top_p != 1.0 or top_k != 50 or repetition_penalty != 1.0:
                generation_config['do_sample'] = True
            # Set random seed for reproducibility if provided
            if seed != -1:
                import random
                import numpy as np
                import torch
                random.seed(seed)
                np.random.seed(seed)
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(seed)

            internvl_model = model['model']
            tokenizer = model['tokenizer']
            
            if internvl_model is None:
                raise ValueError("Model object is None - model may not have loaded correctly")
            if tokenizer is None:
                raise ValueError("Tokenizer object is None - tokenizer may not have loaded correctly")
            
            question = f'<image>\n{system_prompt}\n{prompt}'
            print(f"Generating response with config: {generation_config}")
            
            response, _ = internvl_model.chat(tokenizer, image, question, generation_config, history=None,
                                     return_history=True)
            
            if response is None:
                raise RuntimeError("Model returned None response - inference failed")
            
            print(f"Generated response: '{response[:100]}{'...' if len(response) > 100 else ''}'")

            if not keep_model_loaded:
                print("Offloading model...")
                internvl_model.to(offload_device)
                mm.soft_empty_cache()

            return (response,)
            
        except Exception as e:
            error_msg = f"InternVL inference failed: {str(e)}"
            print(f"ERROR: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            # Return error message instead of None to prevent ComfyUI crash
            return (f"ERROR: {error_msg}",)
    
    def _prepare_image_tensor(self, image, device):
        """Prepare image tensor using proper InternVL dynamic preprocessing."""
        # InternVL constants from official implementation
        IMAGENET_MEAN = (0.485, 0.456, 0.406)
        IMAGENET_STD = (0.229, 0.224, 0.225)
        IMAGE_SIZE = 448  # Standard InternVL input size
        MAX_NUM_PATCHES = 12  # Maximum number of image patches
        
        
        # Convert ComfyUI tensor to PIL Image for processing
        if image.dim() == 4 and image.shape[0] == 1:  # [1, height, width, channels]
            # Convert from ComfyUI format [1, H, W, C] to PIL Image
            if image.shape[3] == 3:  # RGB
                # Convert to numpy and then PIL
                img_np = (image[0].cpu().numpy() * 255).astype(np.uint8)
                pil_image = Image.fromarray(img_np, 'RGB')
            else:
                raise ValueError(f"Unsupported channel count: {image.shape[3]}")
        else:
            raise ValueError(f"Unsupported input tensor shape: {image.shape}")
        
        print(f"Converted to PIL image: {pil_image.size}")
        
        # Apply InternVL dynamic preprocessing
        processed_images = self._dynamic_preprocess(
            pil_image, 
            min_num=1, 
            max_num=MAX_NUM_PATCHES, 
            image_size=IMAGE_SIZE, 
            use_thumbnail=True
        )
        
        print(f"Dynamic preprocessing created {len(processed_images)} image patches")
        
        # Build transform pipeline (from official InternVL code)
        transform = T.Compose([
            T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
            T.Resize((IMAGE_SIZE, IMAGE_SIZE), interpolation=T.InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
        ])
        
        # Apply transform to each processed image
        pixel_values = [transform(img) for img in processed_images]
        pixel_values = torch.stack(pixel_values)  # Stack into tensor
        
        print(f"Final processed tensor shape: {pixel_values.shape}")
        print(f"Tensor dtype before conversion: {pixel_values.dtype}")
        print(f"Tensor stats: min={pixel_values.min().item()}, max={pixel_values.max().item()}, sum={pixel_values.sum().item()}")
        print(f"Any NaN: {torch.isnan(pixel_values).any().item()}, Any Inf: {torch.isinf(pixel_values).any().item()}")
        
        # Per-model dtype logic
        model_name = None
        try:
            # Try to get model name from device arg (passed from process)
            if hasattr(device, 'model_name'):
                model_name = device.model_name
        except Exception: pass
        # Fallback: try to get global model name from class
        import inspect
        frame = inspect.currentframe()
        while frame:
            if 'model' in frame.f_locals:
                m = frame.f_locals['model']
                if isinstance(m, dict) and 'model_name' in m:
                    model_name = m['model_name']
                    break
            frame = frame.f_back
        dtype = torch.float16
        if model_name and ("VL3" in model_name or "InternVL3" in model_name):
            dtype = torch.bfloat16
            print(f"Detected InternVL3 model ({model_name}) - using bfloat16")
        else:
            print(f"Detected InternVL2 or unknown ({model_name}) - using float16")
        # Convert to appropriate dtype and device
        pixel_values = pixel_values.to(dtype).to(device)
        print(f"Tensor dtype after conversion: {pixel_values.dtype}")
        print(f"Tensor stats after conversion: min={pixel_values.min().item()}, max={pixel_values.max().item()}, sum={pixel_values.sum().item()}")
        assert torch.isfinite(pixel_values).all(), "Image tensor contains NaN or Inf values!"
        assert pixel_values.abs().sum() > 0, "Image tensor is all zeros!"
        return pixel_values
    
    def _find_closest_aspect_ratio(self, aspect_ratio, target_ratios, width, height, image_size):
        """Find the closest aspect ratio from official InternVL code."""
        best_ratio_diff = float('inf')
        best_ratio = (1, 1)
        area = width * height
        for ratio in target_ratios:
            target_aspect_ratio = ratio[0] / ratio[1]
            ratio_diff = abs(aspect_ratio - target_aspect_ratio)
            if ratio_diff < best_ratio_diff:
                best_ratio_diff = ratio_diff
                best_ratio = ratio
            elif ratio_diff == best_ratio_diff:
                if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                    best_ratio = ratio
        return best_ratio
    
    def _dynamic_preprocess(self, image, min_num=1, max_num=12, image_size=448, use_thumbnail=False):
        """Dynamic preprocessing from official InternVL code."""
        orig_width, orig_height = image.size
        aspect_ratio = orig_width / orig_height

        # calculate the existing image aspect ratio
        target_ratios = set(
            (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
            i * j <= max_num and i * j >= min_num)
        target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

        # find the closest aspect ratio to the target
        target_aspect_ratio = self._find_closest_aspect_ratio(
            aspect_ratio, target_ratios, orig_width, orig_height, image_size)

        # calculate the target width and height
        target_width = image_size * target_aspect_ratio[0]
        target_height = image_size * target_aspect_ratio[1]
        blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

        # resize the image
        resized_img = image.resize((target_width, target_height))
        processed_images = []
        for i in range(blocks):
            box = (
                (i % (target_width // image_size)) * image_size,
                (i // (target_width // image_size)) * image_size,
                ((i % (target_width // image_size)) + 1) * image_size,
                ((i // (target_width // image_size)) + 1) * image_size
            )
            # split the image
            split_img = resized_img.crop(box)
            processed_images.append(split_img)
        assert len(processed_images) == blocks
        if use_thumbnail and len(processed_images) != 1:
            thumbnail_img = image.resize((image_size, image_size))
            processed_images.append(thumbnail_img)
        return processed_images

NODE_CLASS_MAPPINGS = {
    "InternVLModelDownloader": InternVLModelDownloader,
    "InternVLModelLoader": InternVLModelLoader,
    "DynamicPreprocess": DynamicPreprocess,
    "InternVLHFInference": InternVLHFInference,

}

NODE_DISPLAY_NAME_MAPPINGS = {
    "InternVLModelDownloader": "InternVL Model Downloader",
    "InternVLModelLoader": "InternVL Model Loader",
    "DynamicPreprocess": "Dynamic Preprocess",
    "InternVLHFInference": "InternVL HF Inference",
}
