import fitz  # PyMuPDF

def extract_text_from_pdf(file_path: str):
    doc = fitz.open(file_path)
    pages_data = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        pages_data.append({
            "page_number": page_num + 1,
            "text": text
        })

    doc.close()
    return pages_data