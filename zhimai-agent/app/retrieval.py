import math
import hashlib
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from collections import Counter
from contextlib import closing
from pathlib import Path

TOKEN_RE = re.compile(r'[\u3400-\u9fff]+|[a-zA-Z][a-zA-Z0-9_+.-]*|\d+(?:\.\d+)?')
QUERY_FILLER = re.compile(r'请问|帮我|给我|介绍一下|什么是|是什么|有哪些|需要哪些|有什么|'
                          r'前置知识|前置基础|后续用途|知识点|之间|关系|联系|复习|课程|如何|怎么|'
                          r'哪些|需要|请|的|与|和|是|吗|呢|一下')


def tokenize(text):
    result = []
    for piece in TOKEN_RE.findall(text.lower()):
        if '\u3400' <= piece[0] <= '\u9fff':
            result.extend(piece[i:i + 2] for i in range(len(piece) - 1))
            if len(piece) == 1:
                result.append(piece)
        else:
            result.append(piece)
    return result


def query_tokens(text):
    return list(dict.fromkeys(tokenize(QUERY_FILLER.sub(' ', text))))[:100]


def chunks(text, size=900, overlap=150):
    text = text.replace('\x00', '').strip()
    if not text:
        return
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        yield text[start:end]
        if end == len(text):
            break
        start = end - overlap


def _pdf_pages(path, name):
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError('索引 PDF 前请运行 pip install -r requirements.txt') from exc
    with pymupdf.open(path) as doc:
        for index, page in enumerate(doc):
            yield name, index + 1, page.get_text()


def _local_pdfs(source_dir):
    root = Path(source_dir).resolve()
    if not root.is_dir():
        raise ValueError('指定的本地知识目录不存在。')
    excluded = {'.git', '.venv', 'venv', 'node_modules', 'site-packages', '__pycache__',
                '.cache', 'cx-profile', '6abe447b9d61d722f219399b'}
    seen = set()
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d.lower() not in excluded and not d.startswith('.')]
        for filename in sorted(names):
            path = Path(current) / filename
            if path.suffix.lower() != '.pdf' or path.is_symlink():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                continue
            digest = hashlib.sha256()
            with resolved.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(block)
            checksum = digest.digest()
            if checksum in seen:
                continue
            seen.add(checksum)
            yield resolved, 'local-books/' + resolved.relative_to(root).as_posix()


def iter_documents(knowledge_root, pdf_archive=None, temp_dir=None, source_dir=None):
    root = Path(knowledge_root)
    local_note_roots = {}
    if source_dir:
        source = Path(source_dir).resolve()
        if not source.is_dir():
            raise ValueError('指定的本地知识目录不存在。')
        for label, relative in [('local-notes', '知识库/大学课程知识库'),
                                ('local-imports', '知识库/比赛方案/超星导入包')]:
            candidate = (source / relative).resolve()
            if candidate.is_dir() and candidate.is_relative_to(source):
                local_note_roots[label] = candidate
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.name == 'README.md':
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in local_note_roots:
            continue
        rel = relative.as_posix()
        suffix = path.suffix.lower()
        if suffix in ('.md', '.txt'):
            yield rel, None, path.read_text(encoding='utf-8-sig', errors='replace')
        elif suffix == '.pdf':
            yield from _pdf_pages(path, rel)
    if source_dir:
        for label, note_root in local_note_roots.items():
            for path in sorted(note_root.rglob('*')):
                if path.is_symlink() or not path.is_file() or path.suffix.lower() not in ('.md', '.txt'):
                    continue
                relative = path.relative_to(note_root)
                if any(part.startswith('.') for part in relative.parts) or not path.resolve().is_relative_to(note_root):
                    continue
                yield f'{label}/{relative.as_posix()}', None, path.read_text(encoding='utf-8-sig', errors='replace')
        for path, name in _local_pdfs(source_dir):
            yield from _pdf_pages(path, name)
    if pdf_archive:
        with zipfile.ZipFile(pdf_archive) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            if sum(entry.file_size for entry in entries) > 2_000_000_000:
                raise ValueError('压缩包解压后的体积超过 2 GB。')
            for entry in entries:
                name = entry.filename.replace('\\', '/')
                parts = name.split('/')
                if name.startswith('/') or any(p in ('', '.', '..') for p in parts) or not name.lower().endswith('.pdf'):
                    raise ValueError(f'压缩包中存在不支持的文件名：{name}')
                if entry.file_size > 300_000_000:
                    raise ValueError(f'单个 PDF 过大：{name}')
                temp = None
                try:
                    with tempfile.NamedTemporaryFile(dir=temp_dir, suffix='.tmp.pdf', delete=False) as target:
                        temp = Path(target.name)
                        with archive.open(entry) as source:
                            shutil.copyfileobj(source, target, 1024 * 1024)
                    yield from _pdf_pages(temp, 'books/' + name)
                finally:
                    if temp is not None:
                        temp.unlink(missing_ok=True)


def build_index(knowledge_root, db_path, pdf_archive=None, source_dir=None):
    """重新构建索引；先写临时数据库，成功后再替换现有索引。"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp = db_path.with_name(db_path.name + '.building')
    if temp.exists():
        temp.unlink()
    count = total_tokens = empty_pages = 0
    files = set()
    conn = sqlite3.connect(temp)
    try:
        conn.executescript('''
            CREATE TABLE documents (id INTEGER PRIMARY KEY, source TEXT NOT NULL,
                                    page INTEGER, content TEXT NOT NULL, length INTEGER NOT NULL);
            CREATE TABLE postings (term TEXT NOT NULL, doc_id INTEGER NOT NULL, tf INTEGER NOT NULL);
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        for source, page, content in iter_documents(knowledge_root, pdf_archive, db_path.parent, source_dir):
            files.add(source)
            if not content.strip():
                empty_pages += 1
                continue
            for chunk in chunks(content):
                terms = Counter(tokenize(chunk))
                if not terms:
                    continue
                length = sum(terms.values())
                cursor = conn.execute(
                    'INSERT INTO documents(source,page,content,length) VALUES(?,?,?,?)',
                    (source, page, chunk, length),
                )
                conn.executemany('INSERT INTO postings(term,doc_id,tf) VALUES(?,?,?)',
                                 ((term, cursor.lastrowid, freq) for term, freq in terms.items()))
                count += 1
                total_tokens += length
                if count % 500 == 0:
                    conn.commit()
        conn.execute('CREATE INDEX postings_term ON postings(term)')
        conn.executemany('INSERT INTO meta(key,value) VALUES(?,?)', [
            ('documents', str(count)), ('files', str(len(files))),
            ('empty_pages', str(empty_pages)),
            ('average_length', str(total_tokens / count if count else 0)),
        ])
        conn.commit()
    except Exception:
        conn.close()
        if temp.exists():
            temp.unlink()
        raise
    conn.close()
    temp.replace(db_path)
    return {'chunks': count, 'files': len(files), 'empty_pages': empty_pages}


def index_status(db_path):
    path = Path(db_path)
    if not path.exists():
        return {'chunks': 0, 'files': 0, 'searchable_files': 0, 'empty_pages': 0}
    with closing(sqlite3.connect(path)) as conn:
        meta = dict(conn.execute('SELECT key,value FROM meta'))
        searchable_files = conn.execute('SELECT COUNT(DISTINCT source) FROM documents').fetchone()[0]
    return {'chunks': int(meta.get('documents', 0)), 'files': int(meta.get('files', 0)),
            'searchable_files': searchable_files, 'empty_pages': int(meta.get('empty_pages', 0))}


def search(db_path, query, limit=10):
    path = Path(db_path)
    if not path.exists():
        return []
    terms = query_tokens(query)
    if not terms:
        return []
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        meta = dict(conn.execute('SELECT key,value FROM meta'))
        total = int(meta.get('documents', 0))
        avg = float(meta.get('average_length', 0)) or 1.0
        if not total:
            return []
        scores, matched = {}, {}
        for term in terms:
            rows = conn.execute('SELECT p.doc_id,p.tf,d.length FROM postings p '
                                'JOIN documents d ON d.id=p.doc_id WHERE p.term=?', (term,)).fetchall()
            if not rows:
                continue
            idf = math.log(1 + (total - len(rows) + 0.5) / (len(rows) + 0.5))
            for row in rows:
                numerator = row['tf'] * 2.2
                denominator = row['tf'] + 1.2 * (0.25 + 0.75 * row['length'] / avg)
                scores[row['doc_id']] = scores.get(row['doc_id'], 0) + idf * numerator / denominator
                matched[row['doc_id']] = matched.get(row['doc_id'], 0) + 1
        result, seen = [], set()
        for doc_id, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True):
            if matched[doc_id] < min(2, len(terms)):
                continue
            row = conn.execute('SELECT source,page,content FROM documents WHERE id=?', (doc_id,)).fetchone()
            fingerprint = re.sub(r'\s+', '', row['content'])
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            result.append({'source': row['source'], 'page': row['page'], 'content': row['content'],
                           'score': round(score, 4)})
            if len(result) >= max(1, min(limit, 20)):
                break
        return result
