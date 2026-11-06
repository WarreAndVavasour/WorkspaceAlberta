"""Build a complete, page-addressable source corpus; document text is data only."""
import argparse
import hashlib
import json
from pathlib import Path

import fitz


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with fitz.open(args.pdf) as doc:
        outline = [dict(id=f'section-{i}', level=level, title=title, pdf_page=page)
                   for i, (level, title, page) in enumerate(doc.get_toc()) if page > 0]
        pages = [dict(id=f'page-{i+1}', pdf_page=i+1,
                      printed_page_label=page.get_label(), text=page.get_text(sort=True))
                 for i, page in enumerate(doc)]
        corpus = dict(schema_version='1.0', title=doc.metadata.get('title'),
                      source_filename=args.pdf.name,
                      source_sha256=hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
                      provenance='User-supplied PDF; not compared against an online edition.',
                      coverage='All PDF pages; extracted text, not a verified financial dataset.',
                      page_count=len(pages), outline=outline, pages=pages)
        (args.output / 'source.json').write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding='utf-8')
        (args.output / 'source.txt').write_text('\n\n'.join(f'PDF PAGE {p["pdf_page"]}\n{p["text"]}' for p in pages), encoding='utf-8')
        print(json.dumps(dict(pages=len(pages), outline_entries=len(outline),
                              pages_with_text=sum(bool(p['text'].strip()) for p in pages))))


if __name__ == '__main__':
    main()
