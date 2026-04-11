import PyPDF2

reader = PyPDF2.PdfReader(r'd:\work\travel\doc\Travel_Route_File_Based_SRS_TOR_API.pdf')
for i in range(min(5, len(reader.pages))):
    text = reader.pages[i].extract_text()
    if text:
        print(f"\n--- PAGE {i+1} ---")
        print(text)
