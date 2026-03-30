import pdfplumber
import os

pdf1 = r"C:\Users\dhars\Downloads\202004301208150409Dr-Lalit-Kishore-Srivastava-Government-Contract.pdf"
pdf2 = r"C:\Users\dhars\Downloads\DraftChVISCD.pdf"

with open("new_pdfs_output.txt", "w", encoding="utf-8") as f:
    f.write("--- PDF 1 ---\n")
    try:
        if os.path.exists(pdf1):
            with pdfplumber.open(pdf1) as pdf:
                f.write(pdf.pages[0].extract_text()[:2000] + "\n\n")
        else:
            f.write("File not found\n\n")
    except Exception as e:
        f.write(str(e) + "\n\n")

    f.write("--- PDF 2 ---\n")
    try:
        if os.path.exists(pdf2):
            with pdfplumber.open(pdf2) as pdf:
                f.write(pdf.pages[0].extract_text()[:2000] + "\n")
        else:
            f.write("File not found\n")
    except Exception as e:
        f.write(str(e) + "\n")
