import pdfplumber

with open("pdf_out.txt", "w", encoding="utf-8") as f:
    f.write("--- SampleContract1 ---\n")
    try:
        with pdfplumber.open(r"C:\Users\dhars\Downloads\SampleContract1.pdf") as pdf:
            f.write(pdf.pages[0].extract_text()[:1500] + "\n\n")
    except Exception as e:
        f.write(str(e) + "\n\n")

    f.write("--- SampleContract2 ---\n")
    try:
        with pdfplumber.open(r"C:\Users\dhars\Downloads\SampleContract2.pdf") as pdf:
            f.write(pdf.pages[0].extract_text()[:1500] + "\n")
    except Exception as e:
        f.write(str(e) + "\n")
