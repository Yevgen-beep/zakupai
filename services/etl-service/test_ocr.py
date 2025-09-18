#!/usr/bin/env python3
"""
Test script for OCR Loader
Creates simple PDF files from text files for testing using fpdf2 (lighter alternative to reportlab)
"""

import sys
from pathlib import Path


def create_test_pdfs_simple():
    """Create simple PDF files using basic approach (fallback method)"""
    pdf_dir = Path("pdf")

    # Find text files
    text_files = list(pdf_dir.glob("*.txt"))

    if not text_files:
        print("No text files found in pdf/ directory")
        # Create sample files if none exist
        create_sample_text_files()
        text_files = list(pdf_dir.glob("*.txt"))

    print(f"Creating PDF files from {len(text_files)} text files...")

    # Try with fpdf2 first
    try:
        from fpdf import FPDF

        return create_test_pdfs_fpdf(text_files)
    except ImportError:
        print("fpdf2 not available, trying reportlab...")

    # Try with reportlab as fallback
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        return create_test_pdfs_reportlab(text_files)
    except ImportError:
        print("reportlab not available, using simple text file approach...")
        return create_simple_text_files(text_files)


def create_test_pdfs_fpdf(text_files):
    """Create PDFs using fpdf2"""
    from fpdf import FPDF

    for txt_file in text_files:
        pdf_file = txt_file.with_suffix(".pdf")

        try:
            # Read text content
            with open(txt_file, encoding="utf-8") as f:
                content = f.read()

            # Create PDF
            pdf = FPDF()
            pdf.add_page()

            # Try to add Unicode font
            try:
                pdf.add_font(
                    "DejaVu",
                    "",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    uni=True,
                )
                pdf.set_font("DejaVu", size=10)
            except Exception as e:
                print(f"Failed to load DejaVu font: {e}")
                # Fallback to built-in font
                pdf.set_font("Arial", size=10)

            # Add content line by line
            lines = content.split("\n")
            y = 10

            for line in lines:
                if y > 280:  # Start new page if needed
                    pdf.add_page()
                    y = 10

                try:
                    pdf.text(10, y, line)
                except Exception as e:
                    print(f"Failed to add text line '{line[:50]}...': {e}")
                    # Convert to Latin1 if Unicode fails
                    safe_line = line.encode("ascii", errors="ignore").decode("ascii")
                    pdf.text(10, y, safe_line)

                y += 5

            # Save PDF
            pdf.output(str(pdf_file))
            print(f"Created: {pdf_file.name}")

            # Remove text file
            txt_file.unlink()

        except Exception as e:
            print(f"Error creating {pdf_file} with fpdf2: {e}")
            return False

    return True


def create_test_pdfs_reportlab(text_files):
    """Create PDFs using reportlab"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    for txt_file in text_files:
        pdf_file = txt_file.with_suffix(".pdf")

        try:
            # Read text content
            with open(txt_file, encoding="utf-8") as f:
                content = f.read()

            # Create PDF
            c = canvas.Canvas(str(pdf_file), pagesize=letter)
            c.setFont("Times-Roman", 12)

            # Write content line by line
            lines = content.split("\n")
            y = 750  # Start from top

            for line in lines:
                if y < 50:  # Start new page if needed
                    c.showPage()
                    c.setFont("Times-Roman", 12)
                    y = 750

                try:
                    c.drawString(50, y, line)
                except Exception as e:
                    print(f"Failed to draw string '{line[:50]}...': {e}")
                    # Fallback for non-ASCII characters
                    ascii_line = line.encode("ascii", errors="ignore").decode("ascii")
                    c.drawString(50, y, ascii_line)

                y -= 20

            c.save()
            print(f"Created: {pdf_file.name}")

            # Remove text file
            txt_file.unlink()

        except Exception as e:
            print(f"Error creating {pdf_file} with reportlab: {e}")
            return False

    return True


def create_simple_text_files(text_files):
    """Fallback: rename .txt to .pdf for basic testing"""
    print("WARNING: No PDF library available, using text files as mock PDFs")

    for txt_file in text_files:
        pdf_file = txt_file.with_suffix(".pdf")

        try:
            # Just copy text content to PDF file (for basic testing)
            with open(txt_file, encoding="utf-8") as f:
                content = f.read()

            with open(pdf_file, "w", encoding="utf-8") as f:
                f.write("MOCK PDF FILE FOR TESTING\n")
                f.write("=" * 40 + "\n")
                f.write(content)

            print(f"Created mock PDF: {pdf_file.name}")
            txt_file.unlink()

        except Exception as e:
            print(f"Error creating mock PDF {pdf_file}: {e}")
            return False

    return True


def create_sample_text_files():
    """Create sample text files if none exist"""
    pdf_dir = Path("pdf")
    pdf_dir.mkdir(exist_ok=True)

    # Sample data for lot 37971908
    sample_1 = """ТЕХНИЧЕСКОЕ ЗАДАНИЕ НА ЗАКУПКУ

Лот №37971908
Наименование: Поставка канцелярских товаров
Заказчик: АО "КазПочта"
БИН заказчика: 123456789012

ОПИСАНИЕ ЗАКУПКИ:
1. Бумага формата А4 - 1000 пачек
2. Ручки шариковые синие - 500 штук
3. Карандаши простые - 300 штук
4. Папки для документов - 100 штук

ТРЕБОВАНИЯ К КАЧЕСТВУ:
- Бумага должна соответствовать ГОСТ 9094-89
- Ручки должны обеспечивать длину письма не менее 1000 метров
- Карандаши твердости НВ
- Папки из плотного картона

СРОК ПОСТАВКИ: 30 дней с момента подписания договора
МЕСТО ПОСТАВКИ: г. Алматы, ул. Абая 123"""

    # Sample data for lot 37971907
    sample_2 = """ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ

Лот №37971907
Наименование: Поставка компьютерной техники
Заказчик: ТОО "ЦОН Астана"
БИН заказчика: 987654321098

ПЕРЕЧЕНЬ ОБОРУДОВАНИЯ:
1. Персональные компьютеры - 50 штук
   - Процессор: Intel Core i5 или аналогичный
   - ОЗУ: не менее 8 ГБ DDR4
   - Жесткий диск: SSD 256 ГБ + HDD 1 ТБ

2. Мониторы - 50 штук
   - Диагональ: 24 дюйма
   - Разрешение: Full HD (1920x1080)

3. Принтеры лазерные - 10 штук
   - Скорость печати: не менее 30 стр/мин

СРОК ВЫПОЛНЕНИЯ: 45 дней"""

    # Write sample files
    with open(pdf_dir / "37971908.txt", "w", encoding="utf-8") as f:
        f.write(sample_1)

    with open(pdf_dir / "37971907.txt", "w", encoding="utf-8") as f:
        f.write(sample_2)

    print("Created sample text files: 37971908.txt, 37971907.txt")


if __name__ == "__main__":
    try:
        success = create_test_pdfs_simple()
        if success:
            print("✅ Test PDF creation completed successfully!")
        else:
            print("❌ Test PDF creation failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
