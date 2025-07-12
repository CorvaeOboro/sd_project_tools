import cv2
import numpy as np
import torch


class OBORO_ImageRetinexEnhancementNode:
    """
    A ComfyUI node that applies Multi-Scale Retinex with Color Restoration (MSRCR)
    to enhance the dynamic range and color constancy of input images.

    This advanced algorithm is particularly useful in challenging lighting situations,
    as it enhances details in both shadows and highlights while preserving natural colors.

    The node processes images in a batch (expected shape: [B, H, W, C]) and supports both
    color (multi-channel) and grayscale (single channel) images.

    Exposed Parameters:
      - Sigma Scales: Three sigma values used for Gaussian blurring, controlling the scales at which
        details are enhanced (default: 15.0, 80.0, 250.0).
      - Alpha: Controls the strength of the color restoration factor (default: 125.0).
      - Beta: Controls the offset of the color restoration factor (default: 46.0).
      - Gain: Multiplier applied to the final result (default: 1.0).
      - Offset: Subtracted from the MSRCR result before applying gain (default: 0.0).

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
                "sigma1": (
                    "FLOAT",
                    {"default": 15.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "sigma2": (
                    "FLOAT",
                    {"default": 80.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "sigma3": (
                    "FLOAT",
                    {"default": 250.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "alpha": (
                    "FLOAT",
                    {"default": 125.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "beta": (
                    "FLOAT",
                    {"default": 46.0, "min": 0.1, "max": 500.0, "step": 0.1},
                ),
                "gain": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.1, "max": 10.0, "step": 0.1},
                ),
                "offset": (
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
        "challenging lighting conditions. Exposes parameters for sigma scales, alpha, beta, gain, "
        "and offset for fine-tuning."
    )

    def apply_retinex_enhancement(
        self, input_image, sigma1, sigma2, sigma3, alpha, beta, gain, offset
    ):
        """
        Applies the MSRCR algorithm to each image in the batch.

        Parameters:
            input_image (torch.Tensor): Batch of images in [B, H, W, C] format, with pixel values in [0, 1].
            sigma1 (float): Sigma value for the first scale of Gaussian blurring.
            sigma2 (float): Sigma value for the second scale of Gaussian blurring.
            sigma3 (float): Sigma value for the third scale of Gaussian blurring.
            alpha (float): Controls the strength of the color restoration.
            beta (float): Controls the offset of the color restoration.
            gain (float): Gain multiplier applied to the final result.
            offset (float): Offset subtracted from the MSRCR result.

        Returns:
            Tuple containing a single torch.Tensor of enhanced images.
        """
        # Move tensor to CPU and convert to numpy array.
        input_image_cpu = input_image.cpu()
        image_batch_np = input_image_cpu.numpy()  # Expected shape: (B, H, W, C)

        # List to accumulate enhanced images.
        enhanced_images_list = []

        # Define sigma scales based on node parameters.
        sigma_scales = [sigma1, sigma2, sigma3]

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
                for current_sigma in sigma_scales:
                    blurred_image = cv2.GaussianBlur(image_scaled, (0, 0), current_sigma)
                    msr_result += np.log(image_scaled + epsilon) - np.log(blurred_image + epsilon)

                # Average the SSR results across scales.
                msr_result = msr_result / float(len(sigma_scales))

                # Compute the Color Restoration Factor.
                sum_channels = np.sum(image_scaled, axis=2, keepdims=True) + epsilon
                color_restoration = beta * (
                    np.log(alpha * image_scaled + epsilon) - np.log(sum_channels)
                )

                # Combine MSR and Color Restoration to obtain the MSRCR result.
                msrcr_result = gain * (msr_result * color_restoration - offset)

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

                for current_sigma in sigma_scales:
                    blurred_image = cv2.GaussianBlur(image_scaled, (0, 0), current_sigma)
                    msr_result += np.log(image_scaled[:, :, 0] + epsilon) - np.log(
                        blurred_image[:, :, 0] + epsilon
                    )

                msr_result = msr_result / float(len(sigma_scales))
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
