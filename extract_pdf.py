import PyPDF2

for pdf_path in [r'd:\work\travel\doc\Travel_Route_File_Based_SRS_TOR_API.pdf', r'd:\work\travel\doc\Data_Travel_2568.pdf']:
    print(f"\n{'='*80}")
    print(f"FILE: {pdf_path}")
    print(f"{'='*80}")
    reader = PyPDF2.PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            print(f"\n--- PAGE {i+1} ---")
            print(text)
