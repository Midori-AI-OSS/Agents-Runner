# PixelArch Environment Context

This prompt is appended to agent prompts when "Append PixelArch context" is enabled in Settings.

**When used:** Non-interactive agent runs with PixelArch context enabled  
**Template variables:** None

## Prompt


Environment context:
- You are running inside PixelArch.
- You have passwordless sudo.
- If you need to install packages, use `yay -Syu`.
- You have full control of the container you are running in.
