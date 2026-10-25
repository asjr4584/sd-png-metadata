# sd-png-metadata (Enhanced Edition for Automatic1111, Forge & Civitai.red)

PNG, JPG, and WebP metadata tool and interactive Drag-and-Drop Web Studio for Automatic1111 / Forge Stable Diffusion images and **Civitai.red** Image-to-Video (R / X / XXX) provenance.

---

## Quick Start (Windows / Python CLI)

No Haskell compiler is required. Run `sd-png-metadata.cmd` (or `python sd_png_metadata.py`) directly:

```powershell
# Batch convert all JPG/WEBP/PNG files in a directory into Civitai.red-ready PNGs in a dedicated folder:
c:\src\sd-png-metadata\sd-png-metadata.cmd --batch `
  --input-image "C:\Users\jgoka\Downloads\__MOVIES\Video\chanyeol\face" `
  --overwrite-input `
  --civitai-adult `
  --organized-png-dir "C:\Users\jgoka\Downloads\__MOVIES\Video\chanyeol\face\civitai_ready_png" `
  --backup-dir "C:\Users\jgoka\Downloads\__MOVIES\Video\chanyeol\face\backup_originals" `
  --generate-html "C:\Users\jgoka\Downloads\__MOVIES\Video\chanyeol\face\metadata-verification.html"
```

### Print Embedded Metadata from Any Image

```powershell
c:\src\sd-png-metadata\sd-png-metadata.cmd --input-image "path\to\image.png" --print
```

### Launch Interactive Drag-and-Drop Web Studio & Verifier

```powershell
python c:\src\sd-png-metadata\sd_png_metadata.py --batch `
  --input-image "C:\Users\jgoka\Downloads\__MOVIES\Video\chanyeol\face" `
  --organized-png-dir "C:\Users\jgoka\Downloads\__MOVIES\Video\chanyeol\face\civitai_ready_png" `
  --serve 8765
```

---

## CLI Options

```text
Usage:
 sd-png-metadata <options>

Options
  --help                Show this help text.
  --input-image         Input image file or directory path. Required.
  --output-image        Output image file or directory path.
  --output-caption      Output caption file or directory path.
  --log-file            Log file path.
  --pattern-file        Pattern file path for caption output.
  --print               Print the input image metadata to stdout.
  --print-key <key>     Print the input image metadata key to stdout.
  --overwrite-input     Overwrite the input image with the metadata.
  --batch               Batch mode. Specified files must be directories.
  --force               Disable all overwrite checks.
  --create-missing-dirs Create any missing directories.
  --edit <key> <value>  Edit or inject the metadata key.
  --no-prompt-weights   Removes weights from metadata prompts.
  --convert-to-png      Convert JPG/JPEG/WEBP images to PNG with embedded 'parameters' tEXt chunk.
  --civitai-adult       Embed Civitai.red Adult/XXX-compatible A1111 + Civitai resources metadata.
  --organized-png-dir   Separate folder to store all Civitai.red-ready PNG files.
  --backup-dir <dir>    Backup original untouched images before processing.
  --generate-html <p>   Generate self-contained HTML verification & drag-and-drop studio dashboard.
  --serve <port>        Start local HTTP server on specified port.
```
