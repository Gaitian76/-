import argparse
import os
from app.config import ROOT, load_env
from app.retrieval import build_index, index_status

if __name__ == '__main__':
    load_env()
    parser = argparse.ArgumentParser(description='建立本地知识库索引')
    parser.add_argument('--books-zip', help='可选：超星导出的专业课程 PDF 压缩包')
    parser.add_argument('--source-dir', help='可选：本机原始知识系统目录，直接读取其中的 PDF')
    args = parser.parse_args()
    if args.books_zip and args.source_dir:
        parser.error('请选择 --books-zip 或 --source-dir，避免重复索引。')
    if not args.books_zip and not args.source_dir:
        args.source_dir = os.getenv('KNOWLEDGE_SOURCE_DIR', '').strip() or None
    report = build_index(ROOT / 'knowledge', ROOT / 'data' / 'knowledge.sqlite3',
                         pdf_archive=args.books_zip, source_dir=args.source_dir)
    status = index_status(ROOT / 'data' / 'knowledge.sqlite3')
    print(f"扫描完成：{report['files']} 个文件，其中 {status['searchable_files']} 个有可检索文字，"
          f"共 {report['chunks']} 个文本片段；"
          f"{report['empty_pages']} 个页面/文件未提取到文字。")
    if report['empty_pages']:
        print('图片或扫描版页面需要 OCR；当前索引不会自动识别图片文字。')
