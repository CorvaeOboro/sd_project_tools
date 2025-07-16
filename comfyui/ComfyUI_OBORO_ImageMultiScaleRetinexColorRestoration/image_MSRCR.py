import cv2
import numpy as np
import torch


class OBORO_ImageRetinexEnhancementNode:
    """
    A ComfyUI node that applies Multi-Scale Retinex with Color Restoration (MSRCR)
    to enhance the dynamic range and color constancy of input images.

    This node implements the MSRCR algorithm as described in the Retinex literature
    (see e.g. Jobson, Rahman, and Woodell, "A Multiscale Retinex for Bridging the Gap Between Color Images and the Human Observation of Scenes," IEEE Transactions on Image Processing, 1997).

    The parameters exposed in this node correspond to the original MSRCR algorithm notation:

        - gaussian_sigma_small, gaussian_sigma_medium, gaussian_sigma_large: σ₁, σ₂, σ₃ (Gaussian blur scales)
        - color_restoration_strength: α (alpha, color restoration strength)
        - color_restoration_offset: β (beta, color restoration offset)
        - output_gain: G (gain, output multiplier)
        - output_offset: b (offset, output offset)

    Variable names in this implementation are verbose for clarity, but map directly to the standard
    notation in the literature. See the referenced paper for mathematical details.

    This algorithm is useful in lighting situations, as it enhances details in both shadows and highlights while preserving natural colors.

    The node processes images in a batch (expected shape: [B, H, W, C]) and supports both
    color (multi-channel) and grayscale (single channel) images.

    Note:
      The algorithm scales input images (assumed in [0, 1]) to [0, 255] internally,
      then applies a logarithmic transformation to avoid numerical issues. Final results
      are normalized back to [0, 1].
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_image": ("IMAGE",),
            },
            "optional": {
                "gaussian_sigma_small": (
                    "FLOAT",
                    {"default": 15.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "gaussian_sigma_medium": (
                    "FLOAT",
                    {"default": 80.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "gaussian_sigma_large": (
                    "FLOAT",
                    {"default": 250.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "color_restoration_strength": (
                    "FLOAT",
                    {"default": 125.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "color_restoration_offset": (
                    "FLOAT",
                    {"default": 46.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "output_gain": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.1, "max": 10.0, "step": 0.1},
                ),
                "output_offset": (
                    "FLOAT",
                    {"default": 0.0, "min": -100.0, "max": 100.0, "step": 0.1},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("enhanced_image",)
    FUNCTION = "apply_retinex_enhancement"
    CATEGORY = "OBORO"
    DESCRIPTION = (
        "Applies Multi-Scale Retinex with Color Restoration (MSRCR) to enhance dynamic range "
        "and color constancy. Ideal for improving details in both shadows and highlights under "
        "challenging lighting conditions. Exposes parameters for Gaussian blur scales, color restoration strength/offset, and output gain/offset for fine-tuning."
    )

    def apply_retinex_enhancement(
        self, input_image, gaussian_sigma_small, gaussian_sigma_medium, gaussian_sigma_large,
        color_restoration_strength, color_restoration_offset, output_gain, output_offset
    ):
        """
        Applies the MSRCR algorithm to each image in the batch.

        Parameters:
            input_image (torch.Tensor): Batch of images in [B, H, W, C] format, with pixel values in [0, 1].
            gaussian_sigma_small (float): Sigma value for the smallest scale of Gaussian blurring.
            gaussian_sigma_medium (float): Sigma value for the medium scale of Gaussian blurring.
            gaussian_sigma_large (float): Sigma value for the largest scale of Gaussian blurring.
            color_restoration_strength (float): Controls the strength of the color restoration.
            color_restoration_offset (float): Controls the offset of the color restoration.
            output_gain (float): Gain multiplier applied to the final result.
            output_offset (float): Offset subtracted from the MSRCR result.

        Returns:
            Tuple containing a single torch.Tensor of enhanced images.
        """
        # Move tensor to CPU and convert to numpy array.
        input_image_cpu = input_image.cpu()
        image_batch_np = input_image_cpu.numpy()  # Expected shape: (B, H, W, C)

        # List to accumulate enhanced images.
        enhanced_images_list = []

        # Define sigma scales based on node parameters.
        gaussian_sigma_scales = [gaussian_sigma_small, gaussian_sigma_medium, gaussian_sigma_large]

        epsilon = 1e-6  # Small constant to avoid log(0)

        # Process each image in the batch individually.
        for single_image in image_batch_np:
            # Retrieve image dimensions.
            image_height, image_width, num_channels = single_image.shape

            # Scale image to [0, 255] and add 1.0 to avoid taking log(0).
            # (This converts an image from [0, 1] to [1, 256].)
            image_scaled = single_image.astype(np.float64) * 255.0 + 1.0

            if num_channels > 1:
                # --- Process Color Images ---
                # Initialize the Multi-Scale Retinex (MSR) result.
                msr_result = np.zeros_like(image_scaled, dtype=np.float64)

                # Apply Single-Scale Retinex (SSR) for each sigma value and accumulate the results.
                for current_gaussian_sigma in gaussian_sigma_scales:
                    blurred_image = cv2.GaussianBlur(image_scaled, (0, 0), current_gaussian_sigma)
                    msr_result += np.log(image_scaled + epsilon) - np.log(blurred_image + epsilon)

                # Average the SSR results across scales.
                msr_result = msr_result / float(len(gaussian_sigma_scales))

                # Compute the Color Restoration Factor.
                sum_channels = np.sum(image_scaled, axis=2, keepdims=True) + epsilon
                color_restoration_factor = color_restoration_offset * (
                    np.log(color_restoration_strength * image_scaled + epsilon) - np.log(sum_channels)
                )

                # Combine MSR and Color Restoration to obtain the MSRCR result.
                msrcr_result = output_gain * (msr_result * color_restoration_factor - output_offset)

                # Normalize each channel independently to [0, 1]
                normalized_result = np.zeros_like(msrcr_result)
                for c in range(num_channels):
                    channel = msrcr_result[:, :, c]
                    channel_min = np.min(channel)
                    channel_max = np.max(channel)
                    normalized_result[:, :, c] = (channel - channel_min) / (
                        channel_max - channel_min + epsilon
                    )
                enhanced_image = np.clip(normalized_result, 0.0, 1.0)

            else:
                # --- Process Grayscale Images ---
                # For grayscale images, apply Multi-Scale Retinex without color restoration.
                msr_result = np.zeros_like(image_scaled[:, :, 0], dtype=np.float64)

                for current_gaussian_sigma in gaussian_sigma_scales:
                    blurred_image = cv2.GaussianBlur(image_scaled, (0, 0), current_gaussian_sigma)
                    msr_result += np.log(image_scaled[:, :, 0] + epsilon) - np.log(
                        blurred_image[:, :, 0] + epsilon
                    )

                msr_result = msr_result / float(len(gaussian_sigma_scales))
                channel_min = np.min(msr_result)
                channel_max = np.max(msr_result)
                normalized_result = (msr_result - channel_min) / (
                    channel_max - channel_min + epsilon
                )
                # Expand dimensions to restore channel dimension.
                enhanced_image = np.expand_dims(
                    np.clip(normalized_result, 0.0, 1.0), axis=2
                )

            # Append the enhanced image (converted to float32) to the list.
            enhanced_images_list.append(enhanced_image.astype(np.float32))

        # Stack the enhanced images back into a single numpy array.
        output_images_np = np.stack(enhanced_images_list, axis=0)

        # Convert the numpy array back to a torch tensor and place it on the original device.
        output_images_tensor = torch.from_numpy(output_images_np).to(input_image.device)

        return (output_images_tensor,)


# ComfyUI custom node classes to load 
NODE_CLASS_MAPPINGS = {
    "OBOROImageRetinexEnhancementNode": OBORO_ImageRetinexEnhancementNode,
}

# ComfyUI display name for node
NODE_DISPLAY_NAME_MAPPINGS = {
    "OBOROImageRetinexEnhancementNode": "Image Retinex Enhancement ",
}
