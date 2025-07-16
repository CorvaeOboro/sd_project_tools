
class OBOROTextTokenCount:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"text": ("STRING", {"default": ""})},
            "optional": {"clip": ("CLIP", )}
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "count_tokens"
    CATEGORY = "OBORO"
    DESCRIPTION = "Count the tokens of a string using the provided CLIP model's tokenizer if available, otherwise estimate."

    def count_tokens(self, text, clip=None):
        """
        Count tokens using CLIP's tokenizer if possible, otherwise estimate.
        Args:
            text (str): The string to count tokens for.
            clip (optional): CLIP model object with a tokenizer.
        Returns:
            tuple: (token_count_as_string,)
        """
        if clip is not None:
            try:
                # Try common CLIP tokenizer patterns
                if hasattr(clip, 'tokenizer') and hasattr(clip.tokenizer, 'tokenize'):
                    tokens = clip.tokenizer.tokenize(text)
                    token_count = len(tokens[0]) if hasattr(tokens, '__getitem__') else len(tokens)
                    return (str(token_count),)
                elif hasattr(clip, 'tokenize'):
                    tokens = clip.tokenize(text)
                    token_count = len(tokens[0]) if hasattr(tokens, '__getitem__') else len(tokens)
                    return (str(token_count),)
            except Exception as e:
                # Fallback to estimation if something fails
                pass
        # Fallback: Simple LLM-like token estimation
        word_tokens = len(text.split())
        char_tokens = max(0, int(len(text) / 4))
        total_tokens = word_tokens + char_tokens
        return (str(total_tokens),)


NODE_CLASS_MAPPINGS = {
    'OBOROTextTokenCount': OBOROTextTokenCount,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'OBOROTextTokenCount': 'Text Token Count',
}
