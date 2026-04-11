import PyPDF2

for pdf_path in [r'd:\work\travel\doc\Travel_Route_File_Based_SRS_TOR_API.pdf']:
    reader = PyPDF2.PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            print(f"\n--- PAGE {i+1} ---")
            print(text)
