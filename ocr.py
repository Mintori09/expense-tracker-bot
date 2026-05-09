"""
OCR module for image and PDF text extraction.
Supports Vietnamese and English languages.
Uses AI vision for image processing.
"""

import asyncio
import base64
import logging
import re
from pathlib import Path

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from config import ensure_data_dir, settings
from utils import OCRFailedError

logger = logging.getLogger(__name__)


def setup_tesseract():
    """Configure Tesseract for Vietnamese and English OCR."""
    return "eng+vie"


def image_to_base64(image_path: str) -> str:
    """Convert image to base64 for AI API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


async def image_to_text_ai(image_path: str) -> str:
    """Extract text from image using AI vision model."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    base64_image = image_to_base64(image_path)

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """Extract all text from this receipt/invoice image. 
                        Focus on: date, merchant name, items, amounts, total.
                        Return as plain text that can be parsed for financial data.
                        Vietnamese text should be preserved."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        max_tokens=1000,
    )

    text = response.choices[0].message.content or ""
    logger.info(f"AI vision extracted {len(text)} chars from {image_path}")
    return text.strip()


async def image_to_text_async(image_path: str) -> str:
    """Extract text from image using AI vision - async version."""
    try:
        return await image_to_text_ai(image_path)
    except Exception as e:
        logger.warning(f"AI vision failed: {e}, falling back to OCR")
        # Fallback to Tesseract OCR
        try:
            lang = setup_tesseract()
            image = Image.open(image_path)
            image = image.convert("L")
            image = image.point(lambda x: 0 if x < 128 else 255, "1")
            text = pytesseract.image_to_string(image, lang=lang)
            logger.info(f"OCR extracted {len(text)} chars from {image_path}")
            return text.strip()
        except Exception as e2:
            logger.error(f"OCR failed: {e2}")
            raise OCRFailedError(str(e2))


def image_to_text(image_path: str) -> str:
    """Extract text from image - try AI first, fallback to OCR."""
    try:
        return asyncio.run(image_to_text_async(image_path))
    except Exception as e:
        logger.error(f"Image processing failed: {e}")
        raise OCRFailedError(str(e))


async def pdf_to_text_async(pdf_path: str) -> str:
    """Extract text from PDF - try text extraction first, fallback to AI/OCR."""
    # Try pdfplumber for text-based PDFs first
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text += page_text + "\n"

        if text.strip() and len(text.strip()) > 50:
            logger.info(f"PDF text extraction got {len(text)} chars from {pdf_path}")
            return text.strip()
    except Exception as e:
        logger.warning(f"PDF text extraction failed: {e}")

    # Fallback to AI vision - convert each page to image first
    try:
        images = convert_from_path(pdf_path)
        texts = []
        for i, image in enumerate(images):
            ensure_data_dir()
            temp_path = f"data/temp_pdf_page_{i}.jpg"
            image.save(temp_path, "JPEG")
            try:
                page_text = await image_to_text_ai(temp_path)
                texts.append(page_text)
            finally:
                Path(temp_path).unlink(missing_ok=True)
        result = "\n\n".join(texts)
        logger.info(f"PDF AI vision extracted {len(result)} chars")
        return result.strip()
    except Exception as e:
        logger.warning(f"PDF AI vision failed: {e}, trying OCR")

    # Last resort: OCR
    try:
        lang = setup_tesseract()
        images = convert_from_path(pdf_path)
        texts = []
        for i, image in enumerate(images):
            image = image.convert("L")
            image = image.point(lambda x: 0 if x < 128 else 255, "1")
            text = pytesseract.image_to_string(image, lang=lang)
            texts.append(text)
        result = "\n\n".join(texts)
        logger.info(f"PDF OCR extracted {len(result)} chars from {pdf_path}")
        return result.strip()
    except Exception as e:
        logger.error(f"PDF OCR failed: {e}")
        raise OCRFailedError(str(e))


def pdf_to_text(pdf_path: str) -> str:
    """Extract text from PDF - try text extraction first, fallback to AI/OCR."""
    try:
        return asyncio.run(pdf_to_text_async(pdf_path))
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        raise OCRFailedError(str(e))


def preprocess_ocr_text(text: str) -> str:
    """Clean up OCR text for better LLM processing."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Fix common OCR errors for Vietnamese - use raw strings
    lines = []
    for line in text.split("\n"):
        # Fix O -> 0 in numbers: "5O000" -> "50000"
        line = re.sub(r"(\d)O(\d)", r"\g<1>0\g<2>", line)
        # Fix l -> 1 in numbers: "1l000" -> "11000"
        line = re.sub(r"(\d)l(\d)", r"\g<1>1\g<2>", line)
        lines.append(line.strip())

    return "\n".join(lines)