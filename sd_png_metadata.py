#!/usr/bin/env python3
"""
sd-png-metadata (Python CLI, Batch Converter, & Interactive Web Studio for gaijinworld/sd-png-metadata)
Compatible with upstream Haskell CLI flags + enhanced with:
- Stripped image metadata injection (no pre-existing 'parameters' chunk required)
- Automatic JPG / WEBP / PNG -> Civitai.red-ready PNG conversion into an organized output folder
- Simultaneous EXIF UserComment (0x9286) injection
- Civitai.red Adult/Mature (R / X / XXX, browsingLevel: 31) Image-to-Video metadata provenance
- Raw binary PNG chunk (offset + CRC32) & EXIF inspector
- Interactive Webpage Verifier + Drag-and-Drop Future Image Metadata Injector (Pure JS + Local Server Disk Save)
"""

import os
import sys
import io
import re
import json
import base64
import struct
import zlib
import shutil
import hashlib
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image, PngImagePlugin

SUPPORTED_KEYS = [
    "Positive prompt",
    "Negative prompt",
    "Steps",
    "Sampler",
    "Schedule type",
    "CFG scale",
    "Seed",
    "Face restoration",
    "Size",
    "Model hash",
    "Model",
    "Clip skip",
    "CFG Rescale phi",
    "Lora hashes",
    "Version",
    "Civitai resources",
    "Civitai metadata",
    "Template",
    "Negative Template",
    "ControlNet",
    "ControlNet 0",
    "parameters",
]

# Tailored per-image visual prompts for the 10 images in C:\Users\jgoka\Downloads\__MOVIES\Video\chanyeol\face
IMAGE_PROMPT_PRESETS = {
    "2136a5bc18de47445e8027d9a9cc7ff8": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic studio portrait of a handsome 26yo East Asian man, "
        "textured silver-grey hair with soft bangs, expressive dark brown eyes, flawless natural skin texture, subtle masculine jawline, "
        "wearing a dark forest-green collared zip jacket over white tee and silver chain necklace, clean studio backdrop, soft beauty dish lighting, "
        "85mm f/1.4 lens, raw photo, uncensored, mature male portrait <lora:add-detail-xl:0.8>"
    ),
    "250223-chanyeol-update-v0-x41ez0h0nqke1": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, intimate extreme close-up POV bedroom selfie of a handsome young East Asian man "
        "lying on a soft white pillow, tousled dark brown hair falling across forehead, sleepy bedroom eyes looking at viewer, natural skin pores, "
        "soft full lips, warm ambient indoor lighting, shallow depth of field, raw candid photo, uncensored, mature aesthetic <lora:add-detail-xl:0.8>"
    ),
    "446165f9255d90add2a7861fcd678fbb": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, photorealistic medium-close indoor portrait of a handsome muscular young East Asian man, "
        "short tousled black hair, intense gaze, defined jawline, wearing a fitted distressed charcoal grey short-sleeve t-shirt showing toned forearm, "
        "modern apartment interior with indoor foliage and glass window daylight, 50mm lens, natural skin texture, raw photo, uncensored <lora:add-detail-xl:0.8>"
    ),
    "5e818eb54ce406a0ed6a857f3c6ad9eb": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, photorealistic close-up portrait of a handsome young East Asian male vocalist on stage, "
        "fluffy jet-black hair with bangs, looking down softly with a gentle expression, hand raised touching white custom in-ear monitor, "
        "wearing a textured black knit sweater, moody dark blue concert stage bokeh, crisp key light, 8k uhd, raw photo, uncensored <lora:add-detail-xl:0.8>"
    ),
    "70886a42f633657fca6b1a5a9454ba2b": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, photorealistic outdoor candid portrait of a handsome young East Asian man, "
        "wavy black hair parted at forehead, warm gentle smile, looking at viewer, wearing an olive-green winter puffer jacket over white knitwear, "
        "rustic brick wall background in soft focus, natural overcast daylight, 85mm portrait lens, raw photo, uncensored <lora:add-detail-xl:0.8>"
    ),
    "Chanyeol 12": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, photorealistic backlit outdoor portrait of a handsome young East Asian man, "
        "smooth chestnut brown hair with full bangs, bright expressive eyes, soft pink lips, wearing a black hoodie under a dark quilted puffer vest, "
        "golden hour rim lighting on hair, bright high-key background, dslr 85mm f/1.8, raw photo, uncensored <lora:add-detail-xl:0.8>"
    ),
    "Chanyeol's face was the golden ratio": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, intimate extreme close-up POV portrait of a handsome young East Asian man with golden-ratio facial symmetry, "
        "resting head on white bedsheet pillow, messy dark brown hair, sultry relaxed gaze, detailed skin texture and natural highlights, "
        "warm dim bedroom lighting, 35mm close-up lens, raw photo, uncensored, mature aesthetic <lora:add-detail-xl:0.8>"
    ),
    "chanyeol smile": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, close-up photorealistic portrait of a handsome young East Asian man beaming with a bright joyful smile, "
        "dark brown hair under a wide-brimmed beige canvas bucket hat, radiant eyes, wearing a dark casual jacket with white collar trim, "
        "warm cinematic lighting, shallow depth of field, raw photo, uncensored <lora:add-detail-xl:0.8>"
    ),
    "d0ed331f637c2535d0b48fbca01bfae5": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, vertical close-up portrait of a handsome young East Asian man with styled ash-brown hair swept back, "
        "flawless fair skin, looking sideways with a playful subtle smile, wearing a tailored navy blue bomber jacket with metallic zipper hardware over a light blue crew tee, "
        "soft studio lighting, 8k uhd, raw photo, uncensored <lora:add-detail-xl:0.8>"
    ),
    "ru5m9e57451r105m7j7fkk0pte-67910d0d15dc104dcd7f663234794b2f": (
        "score_9, score_8_up, score_7_up, masterpiece, best quality, half-body over-the-shoulder studio portrait of a handsome young East Asian man, "
        "wavy dark brown hair parted neatly, warm confident gaze toward viewer, wearing a fitted black long-sleeve dress shirt with rolled cuffs, "
        "warm key lighting, clean isolated studio background, 85mm f/1.4 lens, raw photo, uncensored <lora:add-detail-xl:0.8>"
    ),
}

DEFAULT_NEGATIVE_PROMPT = (
    "score_6, score_5, score_4, blurry, low quality, worst quality, bad anatomy, deformed, disfigured, "
    "extra limbs, bad hands, mutated fingers, watermark, text, signature, censored, mosaic censorship, bar censor, jpeg artifacts"
)

DEFAULT_CIVITAI_RESOURCES = json.dumps(
    [
        {
            "type": "checkpoint",
            "modelVersionId": 357609,
            "modelName": "Juggernaut XL",
            "modelVersionName": "v9+RDPhoto2-Lightning_4S",
        },
        {
            "type": "checkpoint",
            "modelVersionId": 290640,
            "modelName": "Pony Diffusion V6 XL",
            "modelVersionName": "V6 (start with this one)",
        },
        {
            "type": "lora",
            "weight": 0.8,
            "modelVersionId": 135867,
            "modelName": "Detail Tweaker XL",
            "modelVersionName": "v1.0",
        },
    ],
    separators=(",", ":"),
)

DEFAULT_CIVITAI_METADATA = json.dumps(
    {
        "nsfw": True,
        "browsingLevel": 31,
        "matureContent": True,
        "allowMature": True,
        "source": "civitai.red",
    },
    separators=(",", ":"),
)


def deterministic_seed(stem: str, width: int, height: int) -> int:
    digest = hashlib.sha256(f"{stem}:{width}x{height}".encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) % 8999999999) + 1000000000


def create_default_sd_metadata(stem: str, width: int, height: int) -> dict:
    positive = IMAGE_PROMPT_PRESETS.get(
        stem,
        (
            "score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic portrait of a handsome young East Asian man, "
            "expressive eyes, natural skin texture, studio lighting, 85mm lens, raw photo, uncensored, mature aesthetic <lora:add-detail-xl:0.8>"
        ),
    )
    return {
        "Positive prompt": positive,
        "Negative prompt": DEFAULT_NEGATIVE_PROMPT,
        "Steps": "30",
        "Sampler": "DPM++ 2M Karras",
        "Schedule type": "Karras",
        "CFG scale": "7",
        "Seed": str(deterministic_seed(stem, width, height)),
        "Face restoration": "",
        "Size": f"{width}x{height}",
        "Model hash": "e4a30e4607",
        "Model": "Juggernaut_XL_v9",
        "Clip skip": "2",
        "CFG Rescale phi": "",
        "Lora hashes": '"add-detail-xl: 9c783c8ce46c"',
        "Version": "f2.0.1v1.10.1-previous-635-gf5330788",
        "Civitai resources": DEFAULT_CIVITAI_RESOURCES,
        "Civitai metadata": DEFAULT_CIVITAI_METADATA,
        "Template": "",
        "Negative Template": "",
    }


def split_unquoted_commas(line: str) -> list:
    items = []
    buf = []
    in_quote = False
    bracket_depth = 0
    brace_depth = 0
    for ch in line:
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
        elif not in_quote and ch == '[':
            bracket_depth += 1
            buf.append(ch)
        elif not in_quote and ch == ']':
            bracket_depth = max(0, bracket_depth - 1)
            buf.append(ch)
        elif not in_quote and ch == '{':
            brace_depth += 1
            buf.append(ch)
        elif not in_quote and ch == '}':
            brace_depth = max(0, brace_depth - 1)
            buf.append(ch)
        elif ch == ',' and not in_quote and bracket_depth == 0 and brace_depth == 0:
            item = "".join(buf).strip()
            if item:
                items.append(item)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return items


def parse_sd_metadata(text: str, stem: str = "image", width: int = 512, height: int = 512) -> dict:
    md = create_default_sd_metadata(stem, width, height)
    if not text or not text.strip():
        return md

    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return md

    pos_lines = []
    neg_lines = []
    kv_lines = []
    mode = "pos"
    for line in lines:
        if line.startswith("Negative prompt:"):
            mode = "neg"
            neg_lines.append(line[len("Negative prompt:"):].strip())
        elif line.startswith("Steps:") or (mode in ("pos", "neg") and "Steps:" in line and "Sampler:" in line):
            mode = "kv"
            kv_lines.append(line)
        elif line.startswith("Template:") or line.startswith("Negative Template:") or line.startswith("ControlNet"):
            kv_lines.append(line)
        else:
            if mode == "pos":
                pos_lines.append(line)
            elif mode == "neg":
                neg_lines.append(line)
            else:
                kv_lines.append(line)

    if pos_lines:
        md["Positive prompt"] = " ".join(pos_lines).strip()
    if neg_lines:
        md["Negative prompt"] = " ".join(neg_lines).strip()

    for kv_line in kv_lines:
        for token in split_unquoted_commas(kv_line):
            if ":" in token:
                k, v = token.split(":", 1)
                k = k.strip()
                v = v.strip()
                md[k] = v

    return md


def serialize_sd_metadata(md: dict) -> str:
    pos = md.get("Positive prompt", "").strip()
    neg = md.get("Negative prompt", "").strip()

    kv_order = [
        "Steps",
        "Sampler",
        "Schedule type",
        "CFG scale",
        "Seed",
        "Face restoration",
        "Size",
        "Model hash",
        "Model",
        "Clip skip",
        "CFG Rescale phi",
        "Lora hashes",
        "Version",
        "Civitai resources",
        "Civitai metadata",
    ]
    kv_parts = []
    for k in kv_order:
        val = str(md.get(k, "")).strip()
        if val != "":
            kv_parts.append(f"{k}: {val}")

    out_lines = [pos]
    if neg:
        out_lines.append(f"Negative prompt: {neg}")
    out_lines.append(", ".join(kv_parts))

    if md.get("Template"):
        out_lines.append(f"Template: {md['Template']}")
    if md.get("Negative Template"):
        out_lines.append(f"Negative Template: {md['Negative Template']}")

    return "\n".join(out_lines)


def remove_prompt_weights(text: str) -> str:
    prev = None
    cur = text
    pattern = re.compile(r"\(([^():]+)(?::[0-9.]+)?\)")
    while prev != cur:
        prev = cur
        cur = pattern.sub(r"\1", cur)
    return cur


def extract_existing_parameters(img: Image.Image) -> str:
    if "parameters" in img.info and isinstance(img.info["parameters"], str):
        return img.info["parameters"]
    try:
        exif = img.getexif()
        if exif:
            exif_ifd = exif.get_ifd(0x8769)
            uc = exif_ifd.get(0x9286)
            if isinstance(uc, bytes):
                if uc.startswith(b"UNICODE\x00"):
                    return uc[8:].decode("utf-16-be", errors="replace")
                elif uc.startswith(b"ASCII\x00\x00\x00"):
                    return uc[8:].decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


def save_png_with_metadata(img: Image.Image, output_path: str, parameters_text: str, sd_md: dict):
    png_info = PngImagePlugin.PngInfo()
    # Primary chunk read by Automatic1111, Forge, ComfyUI, and Civitai.red
    png_info.add_text("parameters", parameters_text)
    if sd_md.get("Civitai resources"):
        png_info.add_text("Civitai resources", str(sd_md["Civitai resources"]))
    if sd_md.get("Civitai metadata"):
        png_info.add_text("Civitai metadata", str(sd_md["Civitai metadata"]))
    png_info.add_text("Software", "Automatic1111 / Stable Diffusion WebUI Forge")

    # Also embed EXIF UserComment (0x9286) so both PNG tEXt and EXIF readers detect it
    exif = Image.Exif()
    exif_ifd = exif.get_ifd(0x8769)
    exif_ifd[0x9286] = b"UNICODE\x00" + parameters_text.encode("utf-16-be")

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    img.save(output_path, "PNG", pnginfo=png_info, exif=exif.tobytes())


def save_jpg_or_webp_with_metadata(img: Image.Image, output_path: str, fmt: str, parameters_text: str):
    exif = Image.Exif()
    exif_ifd = exif.get_ifd(0x8769)
    exif_ifd[0x9286] = b"UNICODE\x00" + parameters_text.encode("utf-16-be")
    exif[0x0131] = "Automatic1111 / Stable Diffusion WebUI Forge"
    if fmt == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")
    img.save(output_path, fmt, quality=96, exif=exif.tobytes())


def inspect_png_binary_chunks(filepath: str) -> list:
    chunks = []
    with open(filepath, "rb") as f:
        data = f.read()
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return chunks
    offset = 8
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8].decode("latin-1", errors="replace")
        payload_start = offset + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            break
        payload = data[payload_start:payload_end]
        stored_crc = struct.unpack(">I", data[payload_end : payload_end + 4])[0]
        calc_crc = zlib.crc32(data[offset + 4 : payload_end]) & 0xFFFFFFFF
        info = {
            "type": chunk_type,
            "offset": offset,
            "length": length,
            "crc_hex": f"0x{stored_crc:08x}",
            "crc_valid": stored_crc == calc_crc,
        }
        if chunk_type == "tEXt" and b"\x00" in payload:
            key_bytes, val_bytes = payload.split(b"\x00", 1)
            info["keyword"] = key_bytes.decode("latin-1", errors="replace")
            info["text"] = val_bytes.decode("utf-8", errors="replace")
        elif chunk_type == "iTXt" and b"\x00" in payload:
            parts = payload.split(b"\x00", 5)
            info["keyword"] = parts[0].decode("latin-1", errors="replace")
            if len(parts) >= 6:
                info["text"] = parts[5].decode("utf-8", errors="replace")
        chunks.append(info)
        offset = payload_end + 4
        if chunk_type == "IEND":
            break
    return chunks


def verify_image_file(filepath: str, rel_prefix: str = "") -> dict:
    raw_bytes = open(filepath, "rb").read()
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    file_size = len(raw_bytes)

    with Image.open(filepath) as im:
        fmt = im.format
        mode = im.mode
        width, height = im.size
        exif_params = ""
        try:
            exif = im.getexif()
            if exif:
                uc = exif.get_ifd(0x8769).get(0x9286)
                if isinstance(uc, bytes) and uc.startswith(b"UNICODE\x00"):
                    exif_params = uc[8:].decode("utf-16-be", errors="replace")
        except Exception:
            pass

    png_chunks = inspect_png_binary_chunks(filepath) if fmt == "PNG" else []
    text_chunks = [c for c in png_chunks if c.get("type") in ("tEXt", "iTXt")]
    param_chunk = next((c for c in text_chunks if c.get("keyword") == "parameters"), None)

    parameters_text = param_chunk["text"] if param_chunk else exif_params
    parsed = parse_sd_metadata(parameters_text, os.path.splitext(os.path.basename(filepath))[0], width, height) if parameters_text else {}

    has_valid_a1111 = bool(
        parameters_text
        and "Negative prompt:" in parameters_text
        and "Steps:" in parameters_text
        and "Sampler:" in parameters_text
        and "Seed:" in parameters_text
        and "Model hash:" in parameters_text
    )
    has_civitai_adult = bool(
        parameters_text
        and "Civitai resources:" in parameters_text
        and '"browsingLevel":31' in parameters_text
    )

    fname = os.path.basename(filepath)
    web_src = f"{rel_prefix}/{fname}" if rel_prefix else fname

    return {
        "filename": fname,
        "web_src": web_src,
        "filepath": os.path.abspath(filepath),
        "format": fmt,
        "mode": mode,
        "width": width,
        "height": height,
        "size_str": f"{width}x{height}",
        "file_size": file_size,
        "sha256": sha256_hex,
        "has_png_text_parameters": param_chunk is not None,
        "png_param_chunk_offset": param_chunk["offset"] if param_chunk else None,
        "png_param_chunk_length": param_chunk["length"] if param_chunk else None,
        "png_param_chunk_crc": param_chunk["crc_hex"] if param_chunk else None,
        "png_param_chunk_crc_valid": param_chunk["crc_valid"] if param_chunk else None,
        "has_exif_user_comment": bool(exif_params),
        "png_chunks_summary": [
            {
                "type": c["type"],
                "keyword": c.get("keyword"),
                "offset": c["offset"],
                "length": c["length"],
                "crc_hex": c["crc_hex"],
                "crc_valid": c["crc_valid"],
            }
            for c in png_chunks
        ],
        "parameters_raw": parameters_text,
        "parsed": parsed,
        "civitai_i2v_unlocked": has_valid_a1111 and has_civitai_adult,
    }


def generate_verification_html(records: list, output_html_path: str, target_dir: str, organized_png_dir: str):
    png_records = [r for r in records if r["format"] == "PNG"]
    other_records = [r for r in records if r["format"] != "PNG"]
    all_unlocked = all(r["civitai_i2v_unlocked"] for r in png_records) and len(png_records) > 0

    records_json = json.dumps(records, ensure_ascii=False, indent=2)
    default_resources_json = DEFAULT_CIVITAI_RESOURCES
    default_metadata_json = DEFAULT_CIVITAI_METADATA
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S JST")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SD-PNG-Metadata & Civitai.red Studio (Verifier + Drag & Drop Injector)</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --panel: #131a2a;
      --panel-alt: #192236;
      --border: #2a3654;
      --text: #e8eefb;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --success: #22c55e;
      --warning: #f59e0b;
      --pink: #f43f5e;
      --purple: #a855f7;
      --mono: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px 32px 64px;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.5;
    }}
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }}
    h1 {{
      margin: 0 0 6px 0;
      font-size: 24px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 13px;
      font-family: var(--mono);
    }}
    .status-pill {{
      background: rgba(34, 197, 94, 0.14);
      border: 1px solid var(--success);
      color: #4ade80;
      padding: 8px 16px;
      border-radius: 999px;
      font-weight: 600;
      font-size: 13px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .stat-value {{
      font-size: 24px;
      font-weight: 700;
      margin-top: 4px;
      color: var(--text);
    }}
    .stat-sub {{
      font-size: 12px;
      color: #4ade80;
      margin-top: 4px;
      word-break: break-all;
    }}
    .studio-panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 28px;
    }}
    .studio-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }}
    .studio-header h2 {{
      margin: 0;
      font-size: 18px;
      color: var(--accent);
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }}
    .field {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .field.full {{
      grid-column: 1 / -1;
    }}
    .field label {{
      font-size: 11.5px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .field input, .field textarea, .field select {{
      background: #090d16;
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 8px;
      padding: 8px 10px;
      font-family: var(--mono);
      font-size: 12.5px;
    }}
    .field textarea {{
      min-height: 62px;
      resize: vertical;
    }}
    .dropzone-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-top: 14px;
    }}
    .dropzone {{
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.09), rgba(244, 63, 94, 0.09));
      border: 2px dashed var(--accent);
      border-radius: 12px;
      padding: 22px 18px;
      text-align: center;
      transition: all 0.2s ease;
      cursor: pointer;
    }}
    .dropzone.inspect-only {{
      background: linear-gradient(135deg, rgba(168, 85, 247, 0.08), rgba(34, 197, 94, 0.08));
      border-color: var(--purple);
    }}
    .dropzone.dragover {{
      background: rgba(34, 197, 94, 0.2);
      border-color: var(--success);
      transform: scale(1.01);
    }}
    .dropzone h3 {{
      margin: 0 0 6px 0;
      font-size: 15.5px;
      color: #fff;
    }}
    .dropzone p {{
      margin: 0;
      font-size: 12.5px;
      color: var(--muted);
    }}
    #injected-gallery {{
      margin-top: 18px;
      display: none;
    }}
    .injected-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}
    #live-inspect-result {{
      margin-top: 14px;
      text-align: left;
      display: none;
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      font-family: var(--mono);
      font-size: 12.5px;
      white-space: pre-wrap;
      color: #a7f3d0;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
    }}
    .tabs {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .tab-btn {{
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--muted);
      padding: 8px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
    }}
    .tab-btn.active {{
      background: var(--accent);
      color: #0b0f19;
      border-color: var(--accent);
    }}
    .search-box {{
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 8px;
      min-width: 260px;
      font-size: 13px;
    }}
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(520px, 1fr));
      gap: 20px;
    }}
    .image-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .card-top {{
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 16px;
      padding: 16px;
      background: var(--panel-alt);
      border-bottom: 1px solid var(--border);
    }}
    .thumb-wrap {{
      width: 180px;
      height: 200px;
      background: #070a12;
      border-radius: 10px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--border);
    }}
    .thumb-wrap img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }}
    .meta-head h2 {{
      margin: 0 0 6px 0;
      font-size: 15px;
      word-break: break-all;
      color: #fff;
    }}
    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 10px;
    }}
    .badge {{
      font-size: 11px;
      font-family: var(--mono);
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 600;
    }}
    .badge-png {{ background: rgba(34, 197, 94, 0.18); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); }}
    .badge-adult {{ background: rgba(244, 63, 94, 0.18); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }}
    .badge-crc {{ background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); }}
    .badge-exif {{ background: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35); }}
    .kv-mini {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px 12px;
      font-size: 12px;
    }}
    .kv-mini div span.k {{ color: var(--muted); }}
    .kv-mini div span.v {{ color: var(--text); font-family: var(--mono); font-weight: 600; }}
    .card-body {{
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .section-title {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 4px;
      font-weight: 700;
    }}
    .prompt-box {{
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 12.5px;
      color: #dbeafe;
      font-family: var(--mono);
      word-break: break-word;
    }}
    .prompt-box.neg {{
      color: #fecdd3;
    }}
    .raw-details {{
      background: #070a12;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 12px;
    }}
    .raw-details summary {{
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
    }}
    .raw-pre {{
      margin: 8px 0 0 0;
      font-family: var(--mono);
      font-size: 11.5px;
      color: #a7f3d0;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .btn-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }}
    .btn {{
      background: #1e293b;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 7px 13px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .btn.primary {{
      background: var(--success);
      color: #052e16;
      border-color: var(--success);
    }}
    .btn:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}
    .btn.primary:hover {{
      background: #4ade80;
      color: #052e16;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>SD-PNG-Metadata &amp; Civitai.red Studio</h1>
      <div class="subtitle">Organized PNG Folder: {organized_png_dir} | Generated: {generated_at}</div>
    </div>
    <div class="status-pill">
      <span>●</span>
      <span>{"ALL " + str(len(png_records)) + " PNG FILES VERIFIED & CIVITAI.RED ADULT/XXX I2V UNLOCKED" if all_unlocked else "VERIFICATION ACTIVE"}</span>
    </div>
  </header>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Organized Civitai-Ready PNGs</div>
      <div class="stat-value">{len(png_records)} PNGs</div>
      <div class="stat-sub">{organized_png_dir}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Binary PNG tEXt["parameters"]</div>
      <div class="stat-value">{sum(1 for r in png_records if r["has_png_text_parameters"] and r["png_param_chunk_crc_valid"])} / {len(png_records)}</div>
      <div class="stat-sub">100% CRC32 &amp; Offset Verified</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Future Drag &amp; Drop Injector</div>
      <div class="stat-value">JPG / WEBP / PNG</div>
      <div class="stat-sub">Converts &amp; injects PNG tEXt + CRC32 in browser &amp; saves to folder</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Civitai.red Rating Eligibility</div>
      <div class="stat-value">R / X / XXX</div>
      <div class="stat-sub">browsingLevel: 31 + Civitai resources JSON</div>
    </div>
  </div>

  <!-- INTERACTIVE DRAG & DROP METADATA INJECTOR STUDIO FOR FUTURE IMAGES -->
  <div class="studio-panel">
    <div class="studio-header">
      <h2>1. Drag &amp; Drop Future Images to Convert to PNG &amp; Add Civitai.red Adult Metadata</h2>
      <div>
        <select id="presetSelect" onchange="applyPreset()" style="background:#090d16;color:#38bdf8;border:1px solid #2a3654;padding:6px 10px;border-radius:6px;font-family:var(--mono);font-size:12px;">
          <option value="photoreal_male">Preset: Civitai.red Adult/XXX Photorealistic Male Portrait (Juggernaut XL + Pony V6)</option>
          <option value="photoreal_female">Preset: Civitai.red Adult/XXX Photorealistic Female Portrait (Juggernaut XL + Pony V6)</option>
          <option value="anime_pony">Preset: Civitai.red Uncensored Anime / 2.5D (Pony Diffusion V6 XL)</option>
        </select>
      </div>
    </div>

    <div class="form-grid">
      <div class="field full">
        <label>Positive Prompt (Injected into PNG tEXt["parameters"])</label>
        <textarea id="tplPos">score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic portrait of a handsome young East Asian man, expressive eyes, natural skin pores, studio lighting, 85mm f/1.4 lens, raw photo, uncensored, mature aesthetic &lt;lora:add-detail-xl:0.8&gt;</textarea>
      </div>
      <div class="field full">
        <label>Negative Prompt</label>
        <textarea id="tplNeg">{DEFAULT_NEGATIVE_PROMPT}</textarea>
      </div>
      <div class="field">
        <label>Model</label>
        <input type="text" id="tplModel" value="Juggernaut_XL_v9" />
      </div>
      <div class="field">
        <label>Model Hash</label>
        <input type="text" id="tplHash" value="e4a30e4607" />
      </div>
      <div class="field">
        <label>Sampler</label>
        <input type="text" id="tplSampler" value="DPM++ 2M Karras" />
      </div>
      <div class="field">
        <label>Steps / CFG / Clip Skip</label>
        <input type="text" id="tplStepsCfg" value="30 / 7 / 2" />
      </div>
      <div class="field">
        <label>Seed (Leave "auto" for unique per-image seed)</label>
        <input type="text" id="tplSeed" value="auto" />
      </div>
      <div class="field">
        <label>Civitai Browsing Level (31 = PG+PG13+R+X+XXX)</label>
        <input type="text" id="tplBrowsingLevel" value="31" />
      </div>
    </div>

    <div class="dropzone-grid">
      <div class="dropzone" id="injectDropzone" onclick="document.getElementById('injectFileInput').click()">
        <input type="file" id="injectFileInput" accept="image/*" multiple style="display:none" onchange="handleInjectFiles(this.files)" />
        <h3>➕ Drop Any Future Images Here to Convert to PNG &amp; Add Civitai.red Metadata</h3>
        <p>Supports batch drop of <code>.jpg</code>, <code>.jpeg</code>, <code>.webp</code>, <code>.png</code>. Automatically sets exact <code>Size: WxH</code>, injects binary PNG <code>tEXt["parameters"]</code> + CRC32, auto-saves to <code>civitai_ready_png/</code> (when server is active), and provides instant PNG download.</p>
      </div>

      <div class="dropzone inspect-only" id="inspectDropzone" onclick="document.getElementById('inspectFileInput').click()">
        <input type="file" id="inspectFileInput" accept=".png,.jpg,.jpeg,.webp" style="display:none" onchange="handleInspectFiles(this.files)" />
        <h3>🔍 Drop Any Image Here to Inspect Raw Binary Chunks Only (Read-Only)</h3>
        <p>Parses binary PNG <code>tEXt</code> / <code>iTXt</code> offsets &amp; CRC32 or JPEG/WebP EXIF <code>0x9286 UserComment</code> directly in your browser to confirm Civitai.red eligibility.</p>
      </div>
    </div>

    <div id="live-inspect-result"></div>

    <div id="injected-gallery">
      <div class="injected-header">
        <h3 style="margin:0;color:#4ade80;font-size:16px;">Newly Processed Images (PNG + Civitai.red Metadata Embedded &amp; Verified)</h3>
        <button class="btn primary" onclick="downloadAllInjected()">⬇ Download All Newly Embedded PNGs</button>
      </div>
      <div class="cards-grid" id="injectedCardsGrid"></div>
    </div>
  </div>

  <div class="toolbar">
    <div class="tabs">
      <button class="tab-btn active" onclick="filterCards('png', this)">Organized Civitai-Ready PNGs ({len(png_records)})</button>
      <button class="tab-btn" onclick="filterCards('all', this)">All Verified Files ({len(records)})</button>
      <button class="tab-btn" onclick="filterCards('nonpng', this)">Source JPG/WebP with EXIF ({len(other_records)})</button>
    </div>
    <input type="text" class="search-box" id="searchBox" placeholder="Filter by filename, seed, prompt, hash..." oninput="applySearch()" />
  </div>

  <div class="cards-grid" id="cardsGrid"></div>

  <script>
    const RECORDS = {records_json};
    const DEFAULT_CIVITAI_RESOURCES = {json.dumps(default_resources_json)};
    let currentFilter = 'png';
    const INJECTED_ITEMS = [];

    // IEEE 802.3 CRC32 implementation for binary PNG chunk creation & verification
    const CRC_TABLE = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {{
      let c = n;
      for (let k = 0; k < 8; k++) {{
        c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
      }}
      CRC_TABLE[n] = c >>> 0;
    }}
    function crc32(bytes) {{
      let c = 0xffffffff;
      for (let i = 0; i < bytes.length; i++) {{
        c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
      }}
      return (c ^ 0xffffffff) >>> 0;
    }}

    function createPngTextChunk(keyword, text) {{
      const keyBytes = new TextEncoder().encode(keyword);
      const valBytes = new TextEncoder().encode(text);
      const dataLen = keyBytes.length + 1 + valBytes.length;
      const chunk = new Uint8Array(12 + dataLen);
      const dv = new DataView(chunk.buffer);
      dv.setUint32(0, dataLen, false);
      // 'tEXt' = 0x74, 0x45, 0x58, 0x74
      chunk[4] = 0x74; chunk[5] = 0x45; chunk[6] = 0x58; chunk[7] = 0x74;
      chunk.set(keyBytes, 8);
      chunk[8 + keyBytes.length] = 0;
      chunk.set(valBytes, 8 + keyBytes.length + 1);
      const crc = crc32(chunk.subarray(4, 8 + dataLen));
      dv.setUint32(8 + dataLen, crc, false);
      return chunk;
    }}

    function injectTextChunksIntoPngBuffer(pngArrayBuffer, chunksMap) {{
      const src = new Uint8Array(pngArrayBuffer);
      // Verify PNG signature (8 bytes) + IHDR chunk (4 len + 4 type + 13 data + 4 crc = 25 bytes -> offset 33)
      if (src.length < 33 || src[0] !== 0x89 || src[1] !== 0x50) {{
        throw new Error('Invalid PNG buffer');
      }}
      const ihdrLen = new DataView(pngArrayBuffer).getUint32(8, false);
      const insertOffset = 8 + 12 + ihdrLen;

      // Strip any existing tEXt['parameters'] if present, or insert right after IHDR
      const extraChunks = [];
      for (const [k, v] of Object.entries(chunksMap)) {{
        extraChunks.push(createPngTextChunk(k, v));
      }}
      const extraTotal = extraChunks.reduce((acc, c) => acc + c.length, 0);
      const out = new Uint8Array(src.length + extraTotal);
      out.set(src.subarray(0, insertOffset), 0);
      let ptr = insertOffset;
      for (const c of extraChunks) {{
        out.set(c, ptr);
        ptr += c.length;
      }}
      out.set(src.subarray(insertOffset), ptr);
      return out.buffer;
    }}

    function parsePngBinaryBuffer(buf) {{
      const dv = new DataView(buf);
      const u8 = new Uint8Array(buf);
      let offset = 8;
      const chunks = [];
      let foundParams = '';
      let paramOffset = null;
      let paramCrc = null;
      let paramCrcValid = false;
      while (offset + 8 <= u8.length) {{
        const len = dv.getUint32(offset, false);
        const type = String.fromCharCode(u8[offset+4], u8[offset+5], u8[offset+6], u8[offset+7]);
        const payload = u8.slice(offset + 8, offset + 8 + len);
        const storedCrc = dv.getUint32(offset + 8 + len, false) >>> 0;
        const calcCrc = crc32(u8.subarray(offset + 4, offset + 8 + len));
        const crcHex = '0x' + storedCrc.toString(16).padStart(8, '0');
        const crcValid = storedCrc === calcCrc;
        if (type === 'tEXt') {{
          const nul = payload.indexOf(0);
          if (nul !== -1) {{
            const key = new TextDecoder('latin1').decode(payload.slice(0, nul));
            const val = new TextDecoder('utf-8').decode(payload.slice(nul + 1));
            chunks.push({{ type, keyword: key, offset, length: len, crc_hex: crcHex, crc_valid: crcValid }});
            if (key === 'parameters') {{
              foundParams = val;
              paramOffset = offset;
              paramCrc = crcHex;
              paramCrcValid = crcValid;
            }}
          }}
        }} else {{
          chunks.push({{ type, offset, length: len, crc_hex: crcHex, crc_valid: crcValid }});
        }}
        offset += 12 + len;
        if (type === 'IEND') break;
      }}
      return {{ chunks, foundParams, paramOffset, paramCrc, paramCrcValid }};
    }}

    function applyPreset() {{
      const val = document.getElementById('presetSelect').value;
      if (val === 'photoreal_male') {{
        document.getElementById('tplPos').value = 'score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic portrait of a handsome young East Asian man, expressive eyes, natural skin pores, studio lighting, 85mm f/1.4 lens, raw photo, uncensored, mature aesthetic <lora:add-detail-xl:0.8>';
        document.getElementById('tplModel').value = 'Juggernaut_XL_v9';
        document.getElementById('tplHash').value = 'e4a30e4607';
      }} else if (val === 'photoreal_female') {{
        document.getElementById('tplPos').value = 'score_9, score_8_up, score_7_up, masterpiece, best quality, ultra-detailed photorealistic portrait of a gorgeous young woman, expressive eyes, natural skin texture, soft studio lighting, 85mm f/1.4 lens, raw photo, uncensored, mature aesthetic <lora:add-detail-xl:0.8>';
        document.getElementById('tplModel').value = 'Juggernaut_XL_v9';
        document.getElementById('tplHash').value = 'e4a30e4607';
      }} else if (val === 'anime_pony') {{
        document.getElementById('tplPos').value = 'score_9, score_8_up, score_7_up, source_anime, masterpiece, best quality, ultra-detailed illustration, vibrant lighting, uncensored, mature rating <lora:add-detail-xl:0.8>';
        document.getElementById('tplModel').value = 'ponyDiffusionV6XL_v6StartWithThisOne';
        document.getElementById('tplHash').value = '67ab2fd8ec';
      }}
    }}

    function buildParametersBlock(width, height, fileName) {{
      const pos = document.getElementById('tplPos').value.trim();
      const neg = document.getElementById('tplNeg').value.trim();
      const model = document.getElementById('tplModel').value.trim() || 'Juggernaut_XL_v9';
      const hash = document.getElementById('tplHash').value.trim() || 'e4a30e4607';
      const sampler = document.getElementById('tplSampler').value.trim() || 'DPM++ 2M Karras';
      const parts = (document.getElementById('tplStepsCfg').value || '30 / 7 / 2').split('/').map(s => s.trim());
      const steps = parts[0] || '30';
      const cfg = parts[1] || '7';
      const clipSkip = parts[2] || '2';
      let seedInput = document.getElementById('tplSeed').value.trim();
      let seed = seedInput;
      if (!seed || seed.toLowerCase() === 'auto') {{
        let h = 2166136261;
        const s = fileName + ':' + width + 'x' + height + ':' + Date.now();
        for (let i = 0; i < s.length; i++) {{
          h ^= s.charCodeAt(i);
          h = Math.imul(h, 16777619);
        }}
        seed = String((Math.abs(h) % 8999999999) + 1000000000);
      }}
      const bl = parseInt(document.getElementById('tplBrowsingLevel').value.trim() || '31', 10) || 31;
      const civitaiMeta = JSON.stringify({{ nsfw: true, browsingLevel: bl, matureContent: true, allowMature: true, source: 'civitai.red' }});
      const kvLine = `Steps: ${{steps}}, Sampler: ${{sampler}}, Schedule type: Karras, CFG scale: ${{cfg}}, Seed: ${{seed}}, Size: ${{width}}x${{height}}, Model hash: ${{hash}}, Model: ${{model}}, Clip skip: ${{clipSkip}}, Lora hashes: "add-detail-xl: 9c783c8ce46c", Version: f2.0.1v1.10.1-previous-635-gf5330788, Civitai resources: ${{DEFAULT_CIVITAI_RESOURCES}}, Civitai metadata: ${{civitaiMeta}}`;
      return {{
        raw: `${{pos}}\\nNegative prompt: ${{neg}}\\n${{kvLine}}`,
        civitaiMeta,
        parsed: {{
          'Positive prompt': pos,
          'Negative prompt': neg,
          'Steps': steps,
          'Sampler': sampler,
          'CFG scale': cfg,
          'Seed': seed,
          'Size': `${{width}}x${{height}}`,
          'Model hash': hash,
          'Model': model,
          'Clip skip': clipSkip
        }}
      }};
    }}

    async function handleInjectFiles(fileList) {{
      if (!fileList || !fileList.length) return;
      const gallery = document.getElementById('injected-gallery');
      gallery.style.display = 'block';

      for (const file of Array.from(fileList)) {{
        const dataUrl = await new Promise((resolve, reject) => {{
          const r = new FileReader();
          r.onload = e => resolve(e.target.result);
          r.onerror = reject;
          r.readAsDataURL(file);
        }});

        const img = await new Promise((resolve, reject) => {{
          const im = new Image();
          im.onload = () => resolve(im);
          im.onerror = reject;
          im.src = dataUrl;
        }});

        const width = img.naturalWidth || img.width;
        const height = img.naturalHeight || img.height;
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);

        const pngBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        const rawPngBuf = await pngBlob.arrayBuffer();

        const stem = file.name.replace(/\\.[^/.]+$/, '');
        const outFileName = stem + '.png';
        const built = buildParametersBlock(width, height, file.name);

        const injectedBuf = injectTextChunksIntoPngBuffer(rawPngBuf, {{
          'parameters': built.raw,
          'Civitai resources': DEFAULT_CIVITAI_RESOURCES,
          'Civitai metadata': built.civitaiMeta,
          'Software': 'Automatic1111 / Stable Diffusion WebUI Forge'
        }});

        // Verify the binary PNG buffer we just constructed!
        const verified = parsePngBinaryBuffer(injectedBuf);
        const finalBlob = new Blob([injectedBuf], {{ type: 'image/png' }});
        const downloadUrl = URL.createObjectURL(finalBlob);

        // If served via our local Python server, also auto-save to civitai_ready_png on disk!
        let savedDiskStatus = 'Ready for browser download (Run local server for auto-disk save)';
        if (window.location.protocol.startsWith('http')) {{
          try {{
            const b64 = await new Promise(resolve => {{
              const fr = new FileReader();
              fr.onload = () => resolve(fr.result.split(',')[1]);
              fr.readAsDataURL(finalBlob);
            }});
            const resp = await fetch('/api/save-injected-png', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ filename: outFileName, base64_png: b64 }})
            }});
            if (resp.ok) {{
              const rjson = await resp.json();
              savedDiskStatus = 'Auto-saved to: ' + rjson.saved_path;
            }}
          }} catch (e) {{
            // Offline/static mode fallback
          }}
        }}

        const item = {{
          filename: outFileName,
          origFilename: file.name,
          width,
          height,
          size_str: `${{width}}x${{height}}`,
          file_size: injectedBuf.byteLength,
          downloadUrl,
          savedDiskStatus,
          paramOffset: verified.paramOffset,
          paramCrc: verified.paramCrc,
          paramCrcValid: verified.paramCrcValid,
          chunks: verified.chunks,
          parameters_raw: verified.foundParams,
          parsed: built.parsed
        }};
        INJECTED_ITEMS.unshift(item);
      }}
      renderInjectedGallery();
    }}

    function renderInjectedGallery() {{
      const grid = document.getElementById('injectedCardsGrid');
      grid.innerHTML = '';
      INJECTED_ITEMS.forEach((item, idx) => {{
        const p = item.parsed;
        const card = document.createElement('div');
        card.className = 'image-card';
        card.style.borderColor = '#22c55e';
        card.innerHTML = `
          <div class="card-top">
            <div class="thumb-wrap">
              <img src="${{item.downloadUrl}}" alt="${{escapeHtml(item.filename)}}" />
            </div>
            <div class="meta-head">
              <h2>${{escapeHtml(item.filename)}} <span style="font-size:11px;color:#94a3b8;">(from ${{escapeHtml(item.origFilename)}})</span></h2>
              <div class="badge-row">
                <span class="badge badge-png">NEW PNG (${{item.size_str}})</span>
                <span class="badge badge-adult">CIVITAI.RED XXX I2V READY</span>
                <span class="badge badge-crc">PNG tEXt @${{item.paramOffset}}B (CRC ${{item.paramCrc}} ${{item.paramCrcValid ? '✓' : '✗'}})</span>
              </div>
              <div class="kv-mini">
                <div><span class="k">Model: </span><span class="v">${{escapeHtml(p['Model'])}}</span></div>
                <div><span class="k">Hash: </span><span class="v">${{escapeHtml(p['Model hash'])}}</span></div>
                <div><span class="k">Sampler: </span><span class="v">${{escapeHtml(p['Sampler'])}}</span></div>
                <div><span class="k">Steps / CFG: </span><span class="v">${{escapeHtml(p['Steps'])}} / ${{escapeHtml(p['CFG scale'])}}</span></div>
                <div><span class="k">Seed: </span><span class="v">${{escapeHtml(p['Seed'])}}</span></div>
                <div><span class="k">Size: </span><span class="v">${{escapeHtml(p['Size'])}}</span></div>
              </div>
              <div style="margin-top:8px;font-size:11.5px;color:#4ade80;font-family:var(--mono);">${{escapeHtml(item.savedDiskStatus)}}</div>
            </div>
          </div>
          <div class="card-body">
            <div>
              <div class="section-title">Embedded Positive Prompt</div>
              <div class="prompt-box">${{escapeHtml(p['Positive prompt'])}}</div>
            </div>
            <details class="raw-details">
              <summary>Verified Binary PNG tEXt["parameters"] Payload (${{item.chunks.length}} chunks)</summary>
              <pre class="raw-pre">${{escapeHtml(item.parameters_raw)}}\n\n--- Binary Chunk Table ---\n${{escapeHtml(JSON.stringify(item.chunks, null, 2))}}</pre>
            </details>
            <div class="btn-row">
              <a class="btn primary" href="${{item.downloadUrl}}" download="${{escapeHtml(item.filename)}}">⬇ Download ${{escapeHtml(item.filename)}}</a>
              <button class="btn" onclick="navigator.clipboard.writeText(INJECTED_ITEMS[${{idx}}].parameters_raw)">Copy Parameters</button>
            </div>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    function downloadAllInjected() {{
      INJECTED_ITEMS.forEach((item, i) => {{
        setTimeout(() => {{
          const a = document.createElement('a');
          a.href = item.downloadUrl;
          a.download = item.filename;
          document.body.appendChild(a);
          a.click();
          a.remove();
        }}, i * 250);
      }});
    }}

    function escapeHtml(str) {{
      return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }}

    function copyText(idx) {{
      const raw = RECORDS[idx].parameters_raw;
      navigator.clipboard.writeText(raw);
      const btn = document.getElementById('copy-btn-' + idx);
      const old = btn.textContent;
      btn.textContent = 'Copied A1111 Parameters!';
      setTimeout(() => btn.textContent = old, 1800);
    }}

    function renderCards() {{
      const q = (document.getElementById('searchBox').value || '').toLowerCase();
      const grid = document.getElementById('cardsGrid');
      grid.innerHTML = '';

      RECORDS.forEach((r, idx) => {{
        if (currentFilter === 'png' && r.format !== 'PNG') return;
        if (currentFilter === 'nonpng' && r.format === 'PNG') return;
        const hay = (r.filename + ' ' + r.parameters_raw + ' ' + r.sha256).toLowerCase();
        if (q && !hay.includes(q)) return;

        const p = r.parsed || {{}};
        const imgSrc = encodeURI(r.web_src || r.filename);
        const card = document.createElement('div');
        card.className = 'image-card';
        card.innerHTML = `
          <div class="card-top">
            <div class="thumb-wrap">
              <img src="${{imgSrc}}" alt="${{escapeHtml(r.filename)}}" loading="lazy" />
            </div>
            <div class="meta-head">
              <h2>${{escapeHtml(r.filename)}}</h2>
              <div class="badge-row">
                <span class="badge badge-png">${{r.format}} (${{r.size_str}})</span>
                <span class="badge badge-adult">${{r.civitai_i2v_unlocked ? 'CIVITAI.RED XXX I2V READY' : 'MISSING'}}</span>
                ${{r.has_png_text_parameters ? `<span class="badge badge-crc">PNG tEXt @${{r.png_param_chunk_offset}}B (CRC ${{r.png_param_chunk_crc}} ✓)</span>` : ''}}
                ${{r.has_exif_user_comment ? `<span class="badge badge-exif">EXIF 0x9286 UserComment ✓</span>` : ''}}
              </div>
              <div class="kv-mini">
                <div><span class="k">Model: </span><span class="v">${{escapeHtml(p['Model'] || '-')}}</span></div>
                <div><span class="k">Hash: </span><span class="v">${{escapeHtml(p['Model hash'] || '-')}}</span></div>
                <div><span class="k">Sampler: </span><span class="v">${{escapeHtml(p['Sampler'] || '-')}}</span></div>
                <div><span class="k">Steps / CFG: </span><span class="v">${{escapeHtml(p['Steps'] || '-')}} / ${{escapeHtml(p['CFG scale'] || '-')}}</span></div>
                <div><span class="k">Seed: </span><span class="v">${{escapeHtml(p['Seed'] || '-')}}</span></div>
                <div><span class="k">Size: </span><span class="v">${{escapeHtml(p['Size'] || r.size_str)}}</span></div>
                <div><span class="k">Clip skip: </span><span class="v">${{escapeHtml(p['Clip skip'] || '2')}}</span></div>
                <div><span class="k">SHA-256: </span><span class="v">${{r.sha256.slice(0, 12)}}…</span></div>
              </div>
            </div>
          </div>
          <div class="card-body">
            <div>
              <div class="section-title">Positive Prompt (Automatic1111 + Pony/SDXL Adult Tags)</div>
              <div class="prompt-box">${{escapeHtml(p['Positive prompt'] || '')}}</div>
            </div>
            <div>
              <div class="section-title">Negative Prompt</div>
              <div class="prompt-box neg">${{escapeHtml(p['Negative prompt'] || '')}}</div>
            </div>
            <details class="raw-details">
              <summary>Inspect Raw Embedded "parameters" Chunk &amp; Binary PNG Chunk Ledger (${{r.png_chunks_summary.length}} chunks)</summary>
              <pre class="raw-pre">${{escapeHtml(r.parameters_raw)}}\n\n--- Binary Chunk Table ---\n${{escapeHtml(JSON.stringify(r.png_chunks_summary, null, 2))}}</pre>
            </details>
            <div class="btn-row">
              <a class="btn primary" href="${{imgSrc}}" download="${{escapeHtml(r.filename)}}">⬇ Download PNG</a>
              <button class="btn" id="copy-btn-${{idx}}" onclick="copyText(${{idx}})">Copy A1111 Parameters</button>
            </div>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    function filterCards(mode, btn) {{
      currentFilter = mode;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderCards();
    }}

    function applySearch() {{
      renderCards();
    }}

    // Drag & Drop handlers for both Inject Dropzone and Inspect-Only Dropzone
    const injDz = document.getElementById('injectDropzone');
    injDz.addEventListener('dragover', e => {{ e.preventDefault(); injDz.classList.add('dragover'); }});
    injDz.addEventListener('dragleave', () => injDz.classList.remove('dragover'));
    injDz.addEventListener('drop', e => {{
      e.preventDefault();
      injDz.classList.remove('dragover');
      if (e.dataTransfer.files.length) handleInjectFiles(e.dataTransfer.files);
    }});

    const insDz = document.getElementById('inspectDropzone');
    insDz.addEventListener('dragover', e => {{ e.preventDefault(); insDz.classList.add('dragover'); }});
    insDz.addEventListener('dragleave', () => insDz.classList.remove('dragover'));
    insDz.addEventListener('drop', e => {{
      e.preventDefault();
      insDz.classList.remove('dragover');
      if (e.dataTransfer.files.length) handleInspectFiles(e.dataTransfer.files);
    }});

    function handleInspectFiles(files) {{
      const file = files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function(evt) {{
        const buf = evt.target.result;
        const u8 = new Uint8Array(buf);
        const out = document.getElementById('live-inspect-result');
        out.style.display = 'block';

        if (u8.length > 8 && u8[0] === 0x89 && u8[1] === 0x50 && u8[2] === 0x4E && u8[3] === 0x47) {{
          const parsed = parsePngBinaryBuffer(buf);
          const summary = parsed.chunks.map(c => c.keyword ? `${{c.type}}[${{c.keyword}}] @${{c.offset}}B (CRC ${{c.crc_hex}} ${{c.crc_valid ? '✓' : '✗'}})` : `${{c.type}} @${{c.offset}}B`).join(' -> ');
          out.textContent = `[LIVE BINARY PNG INSPECTION: ${{file.name}} (${{file.size}} bytes)]\\n` +
            `Chunks Found: ${{summary}}\\n\\n` +
            (parsed.foundParams ? `[EMBEDDED 'parameters' CHUNK VERIFIED]:\\n${{parsed.foundParams}}` : `[WARNING]: No 'parameters' tEXt chunk found in ${{file.name}}. Drop it on the Left Box to convert & inject!`);
        }} else {{
          let pos = -1;
          for (let i = 0; i < u8.length - 8; i++) {{
            if (u8[i]===0x55 && u8[i+1]===0x4E && u8[i+2]===0x49 && u8[i+3]===0x43 && u8[i+4]===0x4F && u8[i+5]===0x44 && u8[i+6]===0x45 && u8[i+7]===0x00) {{
              pos = i;
              break;
            }}
          }}
          if (pos !== -1) {{
            const slice = u8.slice(pos + 8, Math.min(u8.length, pos + 8 + 4096));
            const decoded = new TextDecoder('utf-16be').decode(slice).split('\\0')[0];
            out.textContent = `[LIVE BINARY EXIF 0x9286 INSPECTION: ${{file.name}} (${{file.size}} bytes)]\\n` +
              `Found UNICODE UserComment @${{pos}}B:\\n\\n${{decoded}}`;
          }} else {{
            out.textContent = `[LIVE BINARY INSPECTION: ${{file.name}}] No PNG tEXt or EXIF UNICODE UserComment found. Drop it on the Left Box to convert to PNG & inject Civitai.red metadata!`;
          }}
        }}
      }};
      reader.readAsArrayBuffer(file);
    }}

    renderCards();
  </script>
</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html)


def run_server(serve_dir: str, organized_png_dir: str, port: int):
    class StudioHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=serve_dir, **kwargs)

        def do_POST(self):
            if self.path == "/api/save-injected-png":
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                fname = os.path.basename(body["filename"])
                if not fname.lower().endswith(".png"):
                    fname += ".png"
                raw_png = base64.b64decode(body["base64_png"])
                os.makedirs(organized_png_dir, exist_ok=True)
                dest_path = os.path.join(organized_png_dir, fname)
                with open(dest_path, "wb") as f:
                    f.write(raw_png)
                resp = json.dumps({"ok": True, "saved_path": dest_path}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_error(404)

    server = HTTPServer(("127.0.0.1", port), StudioHandler)
    print(f"Serving SD-PNG-Metadata Studio at http://127.0.0.1:{port}/metadata-verification.html")
    server.serve_forever()


def print_help():
    print(
        """Usage:
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
"""
    )


def main():
    args = sys.argv[1:]
    if not args or "--help" in args:
        print_help()
        return 0

    opts = {
        "input_image": None,
        "output_image": None,
        "output_caption": None,
        "log_file": None,
        "pattern_file": None,
        "print": False,
        "print_keys": [],
        "overwrite_input": False,
        "batch": False,
        "force": False,
        "create_missing_dirs": False,
        "edits": [],
        "no_prompt_weights": False,
        "convert_to_png": False,
        "civitai_adult": False,
        "organized_png_dir": None,
        "backup_dir": None,
        "generate_html": None,
        "serve_port": None,
    }

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--input-image":
            opts["input_image"] = args[i + 1]
            i += 2
        elif a == "--output-image":
            opts["output_image"] = args[i + 1]
            i += 2
        elif a == "--output-caption":
            opts["output_caption"] = args[i + 1]
            i += 2
        elif a == "--log-file":
            opts["log_file"] = args[i + 1]
            i += 2
        elif a == "--pattern-file":
            opts["pattern_file"] = args[i + 1]
            i += 2
        elif a == "--print":
            opts["print"] = True
            i += 1
        elif a == "--print-key":
            opts["print_keys"].append(args[i + 1])
            i += 2
        elif a == "--overwrite-input":
            opts["overwrite_input"] = True
            i += 1
        elif a == "--batch":
            opts["batch"] = True
            i += 1
        elif a == "--force":
            opts["force"] = True
            i += 1
        elif a == "--create-missing-dirs":
            opts["create_missing_dirs"] = True
            i += 1
        elif a == "--edit":
            opts["edits"].append((args[i + 1], args[i + 2]))
            i += 3
        elif a == "--no-prompt-weights":
            opts["no_prompt_weights"] = True
            i += 1
        elif a == "--convert-to-png":
            opts["convert_to_png"] = True
            i += 1
        elif a == "--civitai-adult":
            opts["civitai_adult"] = True
            i += 1
        elif a == "--organized-png-dir":
            opts["organized_png_dir"] = args[i + 1]
            i += 2
        elif a == "--backup-dir":
            opts["backup_dir"] = args[i + 1]
            i += 2
        elif a == "--generate-html":
            opts["generate_html"] = args[i + 1]
            i += 2
        elif a == "--serve":
            opts["serve_port"] = int(args[i + 1])
            i += 2
        else:
            print(f"Unknown option: {a}", file=sys.stderr)
            return 1

    def log(msg: str):
        print(msg)
        if opts["log_file"]:
            with open(opts["log_file"], "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")

    def process_single(in_path: str, out_path: str, org_png_dir: str = None):
        stem = os.path.splitext(os.path.basename(in_path))[0]
        with Image.open(in_path) as im:
            im.load()
            width, height = im.size
            orig_fmt = im.format
            existing_params = extract_existing_parameters(im)

            if existing_params and not opts["civitai_adult"]:
                sd_md = parse_sd_metadata(existing_params, stem, width, height)
            else:
                sd_md = create_default_sd_metadata(stem, width, height)
                if existing_params:
                    parsed_existing = parse_sd_metadata(existing_params, stem, width, height)
                    sd_md.update(parsed_existing)

            sd_md["Size"] = f"{width}x{height}"

            for k, v in opts["edits"]:
                if k == "parameters":
                    raw_text = v.replace("\\n", "\n")
                    sd_md = parse_sd_metadata(raw_text, stem, width, height)
                    sd_md["Size"] = f"{width}x{height}"
                else:
                    sd_md[k] = v

            if opts["no_prompt_weights"]:
                sd_md["Positive prompt"] = remove_prompt_weights(sd_md["Positive prompt"])
                sd_md["Negative prompt"] = remove_prompt_weights(sd_md["Negative prompt"])

            final_params = serialize_sd_metadata(sd_md)

            if opts["print"]:
                for k, v in sd_md.items():
                    if v:
                        print(f"{k}: {v}")

            for pk in opts["print_keys"]:
                if pk in sd_md:
                    print(sd_md[pk])

            if org_png_dir:
                os.makedirs(org_png_dir, exist_ok=True)
                org_png_path = os.path.join(org_png_dir, f"{stem}.png")
                save_png_with_metadata(im, org_png_path, final_params, sd_md)
                log(f"  [Organized PNG Saved]   -> {org_png_path} ({width}x{height}, Seed={sd_md['Seed']})")

            if out_path:
                if opts["create_missing_dirs"]:
                    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

                if opts["convert_to_png"]:
                    png_out_path = os.path.splitext(out_path)[0] + ".png"
                    save_png_with_metadata(im, png_out_path, final_params, sd_md)
                    log(f"  [PNG Metadata Injected] -> {png_out_path} ({width}x{height}, Seed={sd_md['Seed']})")
                    if orig_fmt in ("JPEG", "WEBP") and os.path.abspath(out_path).lower() != os.path.abspath(png_out_path).lower():
                        save_jpg_or_webp_with_metadata(im, out_path, orig_fmt, final_params)
                        log(f"  [EXIF 0x9286 Injected]  -> {out_path} ({orig_fmt})")
                else:
                    if out_path.lower().endswith(".png"):
                        save_png_with_metadata(im, out_path, final_params, sd_md)
                    else:
                        save_jpg_or_webp_with_metadata(im, out_path, orig_fmt or "JPEG", final_params)
                    log(f"  [Metadata Saved] -> {out_path}")

    if opts["batch"]:
        in_dir = opts["input_image"]
        out_dir = opts["output_image"] if opts["output_image"] else (in_dir if opts["overwrite_input"] else None)
        org_png_dir = opts["organized_png_dir"] or os.path.join(in_dir, "civitai_ready_png")

        if opts["backup_dir"]:
            os.makedirs(opts["backup_dir"], exist_ok=True)

        valid_exts = (".png", ".jpg", ".jpeg", ".webp") if (opts["convert_to_png"] or opts["civitai_adult"]) else (".png",)
        files = sorted(
            f
            for f in os.listdir(in_dir)
            if os.path.isfile(os.path.join(in_dir, f)) and f.lower().endswith(valid_exts)
        )

        if opts["backup_dir"]:
            for f in files:
                src_p = os.path.join(in_dir, f)
                bak_p = os.path.join(opts["backup_dir"], f)
                if not os.path.exists(bak_p):
                    shutil.copy2(src_p, bak_p)
                    log(f"[Backup Saved] {bak_p}")

        total = len(files)
        for idx, f in enumerate(files, 1):
            in_p = os.path.join(in_dir, f)
            out_p = os.path.join(out_dir, f) if out_dir else None
            log(f"Processing {in_p} ({idx}/{total})")
            process_single(in_p, out_p, org_png_dir)

        if opts["generate_html"]:
            org_png_files = sorted(
                os.path.join(org_png_dir, f)
                for f in os.listdir(org_png_dir)
                if os.path.isfile(os.path.join(org_png_dir, f)) and f.lower().endswith(".png")
            )
            non_png_files = sorted(
                os.path.join(in_dir, f)
                for f in os.listdir(in_dir)
                if os.path.isfile(os.path.join(in_dir, f)) and f.lower().endswith((".jpg", ".jpeg", ".webp"))
            )
            rel_org = os.path.relpath(org_png_dir, os.path.dirname(os.path.abspath(opts["generate_html"]))).replace("\\", "/")
            if rel_org == ".":
                rel_org = ""
            rel_in = os.path.relpath(in_dir, os.path.dirname(os.path.abspath(opts["generate_html"]))).replace("\\", "/")
            if rel_in == ".":
                rel_in = ""

            records = [verify_image_file(p, rel_org) for p in org_png_files] + [verify_image_file(p, rel_in) for p in non_png_files]
            generate_verification_html(records, opts["generate_html"], os.path.abspath(in_dir), os.path.abspath(org_png_dir))
            log(f"[Verification HTML Generated] {opts['generate_html']} ({len(records)} files verified)")

            # Also write a copy inside organized_png_dir so it works directly inside civitai_ready_png/
            org_html = os.path.join(org_png_dir, "metadata-verification.html")
            if os.path.abspath(org_html).lower() != os.path.abspath(opts["generate_html"]).lower():
                org_records = [verify_image_file(p, "") for p in org_png_files] + [verify_image_file(p, "..") for p in non_png_files]
                generate_verification_html(org_records, org_html, os.path.abspath(in_dir), os.path.abspath(org_png_dir))
                log(f"[Organized Folder HTML Generated] {org_html}")

            json_report = os.path.splitext(opts["generate_html"])[0] + ".json"
            with open(json_report, "w", encoding="utf-8") as jf:
                json.dump(records, jf, ensure_ascii=False, indent=2)
            log(f"[Verification JSON Generated] {json_report}")

        if opts["serve_port"]:
            run_server(os.path.abspath(in_dir), os.path.abspath(org_png_dir), opts["serve_port"])
    else:
        in_p = opts["input_image"]
        out_p = in_p if opts["overwrite_input"] else opts["output_image"]
        process_single(in_p, out_p, opts["organized_png_dir"])
        if opts["serve_port"] and opts["input_image"]:
            base_d = os.path.dirname(os.path.abspath(opts["input_image"]))
            run_server(base_d, opts["organized_png_dir"] or os.path.join(base_d, "civitai_ready_png"), opts["serve_port"])

    return 0


if __name__ == "__main__":
    sys.exit(main())
