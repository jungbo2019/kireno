#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KIRENO & Asset Studio - Gemini Vision Autonomous Pipeline
Integrates Google Gen AI SDK (google-genai 2.33.0), OpenCV, PIL, and rembg.
Provides:
  1. Multimodal AI Vision Inspection (with OpenCV local fallback)
  2. Automatic Background Removal (rembg)
  3. Dynamic Bounding Box & Margin/Clipping Verification
  4. Batch Asset Quality Audit
"""

import os
import sys
import argparse
import json
import time

# Reconfigure stdout for UTF-8 on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import cv2
import numpy as np
from PIL import Image

# Check Google Gen AI SDK
HAS_GENAI = False
try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# Check rembg
HAS_REMBG = False
try:
    from rembg import remove as rembg_remove
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False

def inspect_image_cv(image_path):
    """
    Local Computer Vision inspection:
    - Dimensions
    - Border touch / clipping (Top, Bottom, Left, Right margin)
    - Cleanliness score
    """
    if not os.path.exists(image_path):
        return {"success": False, "error": f"File not found: {image_path}"}

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        # Try PIL
        try:
            pil_img = Image.open(image_path).convert('RGB')
            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            return {"success": False, "error": str(e)}

    h, w, c = img_bgr.shape
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Edge detection & threshold
    edges = cv2.Canny(gray, 50, 150)
    non_zero = cv2.findNonZero(edges)

    clipping_top = False
    clipping_bottom = False
    clipping_left = False
    clipping_right = False
    margin_top = 0
    margin_bottom = 0

    if non_zero is not None:
        x, y, bw, bh = cv2.boundingRect(non_zero)
        margin_top = y
        margin_bottom = h - (y + bh)
        margin_left = x
        margin_right = w - (x + bw)

        # Flag clipping if content touches within 3px of boundary
        clipping_top = (margin_top <= 3)
        clipping_bottom = (margin_bottom <= 3)
        clipping_left = (margin_left <= 3)
        clipping_right = (margin_right <= 3)
    else:
        margin_top = h // 2
        margin_bottom = h // 2
        margin_left = w // 2
        margin_right = w // 2

    is_clipped = clipping_top or clipping_bottom or clipping_left or clipping_right
    status = "RETRY" if is_clipped else "PASS"

    # Sharpness / Blur score (Laplacian variance)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_sharp = blur_score > 80.0

    return {
        "success": True,
        "filename": os.path.basename(image_path),
        "dimensions": f"{w}x{h}",
        "aspect_ratio": round(w / h, 2),
        "margin_top_px": int(margin_top),
        "margin_bottom_px": int(margin_bottom),
        "clipping_detected": bool(is_clipped),
        "blur_score": round(blur_score, 2),
        "sharpness": "SHARP" if is_sharp else "BLURRY",
        "verdict": status
    }

def inspect_with_gemini(image_path):
    """
    Calls Gemini Multimodal API if GEMINI_API_KEY is available.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"gemini_active": False, "note": "GEMINI_API_KEY 미설정 (로컬 정밀 CV 엔진으로 검수 수행됨)"}

    if not HAS_GENAI:
        return {"gemini_active": False, "note": "google-genai 라이브러리 없음"}

    try:
        client = genai.Client(api_key=api_key)
        pil_img = Image.open(image_path)
        prompt = (
            "이 이미지는 쇼룸 및 디지털 에셋에 사용되는 제품/작품 사진입니다.\n"
            "다음 3가지를 한국어로 2줄 요약 평가해 주세요:\n"
            "1. 피사체 잘림(상하좌우 여백 부족) 유무\n"
            "2. 해상도 및 선명도 품질\n"
            "3. 최종 상용 배포 적합성 (합격/보완필요)"
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[pil_img, prompt]
        )
        return {"gemini_active": True, "ai_review": response.text.strip()}
    except Exception as e:
        return {"gemini_active": False, "error": str(e)}

def remove_background(input_path, output_path):
    """
    Removes background using rembg AI.
    """
    if not HAS_REMBG:
        print("[ERROR] rembg 라이브러리가 설치되어 있지 않습니다.")
        return False

    if not os.path.exists(input_path):
        print(f"[ERROR] 파일 없음: {input_path}")
        return False

    print(f"[*] AI 배경 분리(누끼) 작업 시작: {input_path} -> {output_path}")
    input_img = Image.open(input_path)
    output_img = rembg_remove(input_img)
    output_img.save(output_path, "PNG")
    print(f"[+] 배경 제거 완료: {output_path}")
    return True

def run_batch_inspection(target_dir):
    """
    Audits all images in target directory.
    """
    if not os.path.exists(target_dir):
        print(f"[ERROR] 디렉터리 없음: {target_dir}")
        return

    valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
    files = [f for f in os.listdir(target_dir) if f.lower().endswith(valid_exts)]
    
    print("=" * 70)
    print("   KIRENO GEMINI & CV 자율 에셋 무결점 검수 파이프라인 (2026)")
    print("=" * 70)
    print(f"검수 대상 디렉터리: {target_dir} (총 {len(files)}개 파일)")
    print("-" * 70)
    print(f"{'파일명':<32} | {'규격':<10} | {'상단여백':<8} | {'선명도':<8} | {'판정'}")
    print("-" * 70)

    pass_count = 0
    retry_count = 0

    for fname in sorted(files):
        fpath = os.path.join(target_dir, fname)
        res = inspect_image_cv(fpath)
        if res.get("success"):
            v = res["verdict"]
            if v == "PASS":
                pass_count += 1
            else:
                retry_count += 1
            print(f"{fname:<32} | {res['dimensions']:<10} | {res['margin_top_px']}px{'':<4} | {res['sharpness']:<8} | [{v}]")
        else:
            print(f"{fname:<32} | [오류: {res.get('error')}]")

    print("-" * 70)
    print(f"최종 집계: 전수 {len(files)}건 중 합격(PASS): {pass_count}건, 보완필요(RETRY): {retry_count}건")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Gemini API & CV 자율 에셋 파이프라인")
    parser.add_argument("command", choices=["inspect", "batch-inspect", "remove-bg", "status"], help="실행 명령")
    parser.add_argument("--input", "-i", type=str, help="입력 이미지 경로")
    parser.add_argument("--output", "-o", type=str, help="출력 이미지 경로 (remove-bg 전용)")
    parser.add_argument("--dir", "-d", type=str, default="E:/kireno/1_original/static/images", help="배치 검수 대상 디렉터리")

    args = parser.parse_args()

    if args.command == "status":
        print("=== Gemini API & 자율 파이프라인 환경 현황 ===")
        print(f"• Google Gen AI SDK (google-genai): {'사용가능 (v2.33.0)' if HAS_GENAI else '미설치'}")
        print(f"• OpenCV 비전 엔진 (cv2): INSTALLED")
        print(f"• AI 누끼 엔진 (rembg): {'사용가능' if HAS_REMBG else '미설치'}")
        has_key = bool(os.environ.get("GEMINI_API_KEY"))
        print(f"• GEMINI_API_KEY 등록 여부: {'등록됨 (Cloud Vision 가동)' if has_key else '미등록 (로컬 CV 초정밀 엔진 대체 가동)'}")
        print("===============================================")

    elif args.command == "inspect":
        target = args.input or "E:/kireno/1_original/static/images/moon_jar.jpg"
        print(f"[*] 이미지 검수 실행: {target}")
        cv_res = inspect_image_cv(target)
        print(json.dumps(cv_res, ensure_ascii=False, indent=2))
        gem_res = inspect_with_gemini(target)
        print(json.dumps(gem_res, ensure_ascii=False, indent=2))

    elif args.command == "batch-inspect":
        target_dir = args.dir
        run_batch_inspection(target_dir)

    elif args.command == "remove-bg":
        if not args.input or not args.output:
            print("[ERROR] --input 과 --output 인자가 필요합니다.")
            return
        remove_background(args.input, args.output)

if __name__ == "__main__":
    main()
