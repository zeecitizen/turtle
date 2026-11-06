import sys
sys.stdout.reconfigure(encoding='utf-8')
from pypdf import PdfReader

reader = PdfReader(r'C:\Users\zeesh\Downloads\Optimizing S4b Strategy Win Rate.pdf')
# Write clean text to a file to avoid encoding issues
with open(r'C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\pdf_content.txt', 'w', encoding='utf-8') as f:
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            # Clean up the excessive whitespace from PDF extraction
            lines = text.split('\n')
            clean_lines = []
            for line in lines:
                # Join words that are split by excessive spaces
                clean = ' '.join(line.split())
                if clean:
                    clean_lines.append(clean)
            f.write(f'=== PAGE {i+1} ===\n')
            f.write('\n'.join(clean_lines))
            f.write('\n\n')
print(f'Written {len(reader.pages)} pages to pdf_content.txt')
