import hashlib
from typing import Any, Dict, List


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def make_code_chunks(path: str, code: str, max_chars: int = 1200, overlap: int = 120) -> List[Dict[str, Any]]:
    """
    Cắt code thành các chunk nhỏ để embed. Theo ký tự để đơn giản.
    max_chars ~ 800-1500 hợp lý. overlap để tránh mất ngữ cảnh giữa ranh giới.
    """
    chunks = []
    n = len(code)
    i = 0
    idx = 0
    while i < n:
        j = min(i + max_chars, n)
        chunk = code[i:j]
        chunks.append({
            "path": path,
            "chunk_index": idx,
            "text": chunk
        })
        idx += 1
        if j == n:
            break
        i = j - overlap 
        if i < 0:
            i = 0
    return chunks

def index_codebase_in_chroma(collection, batch_inputs: List[Dict[str, Any]]):
    """
    Upsert tất cả file trong batch_inputs vào Chroma.
    metadata gồm: path, lang, chunk_index.
    id = sha1(path + chunk_index + hash(code))
    """
    docs, ids, metadatas = [], [], []
    for item in batch_inputs:
        path = item["name"]
        lang = item["lang"] or "text"
        code = item["code"]
        chunks = make_code_chunks(path, code)
        for ch in chunks:
            doc_id = _hash(f"{path}:{ch['chunk_index']}:{_hash(ch['text'])}")
            ids.append(doc_id)
            docs.append(ch["text"])
            metadatas.append({
                "path": path,
                "lang": lang,
                "chunk_index": ch["chunk_index"]
            })
    if docs:
        # Upsert theo lô (Chroma sẽ replace nếu id trùng)
        collection.upsert(documents=docs, ids=ids, metadatas=metadatas)

def retrieve_related_code(collection, query_text: str, exclude_path: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Tìm các chunk giống nội dung file hiện tại, loại bỏ chính file đó.
    Trả về danh sách {path, chunk_index, text, distance}
    """
    if not query_text.strip():
        return []
    res = collection.query(
        query_texts=[query_text],
        n_results=k * 2,  
        include=["documents", "metadatas", "distances"]
    )
    out = []
    if not res or not res.get("documents"):
        return out
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res.get("distances", [[None]*len(docs)])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        if not meta:
            continue
        if str(meta.get("path")) == exclude_path:
            continue
        out.append({
            "path": meta.get("path"),
            "chunk_index": meta.get("chunk_index"),
            "text": doc,
            "distance": dist
        })
        if len(out) >= k:
            break
    return out

def build_context_md(related_chunks: List[Dict[str, Any]]) -> str:
    if not related_chunks:
        return ""
    lines = ["### Related code (retrieved via embeddings)\n"]
    for i, ch in enumerate(related_chunks, 1):
        lines.append(f"**{i}. {ch['path']} @ chunk {ch['chunk_index']}**\n")
        snippet = ch["text"]
        if len(snippet) > 800:
            snippet = snippet[:800] + "\n… (truncated)"
        lines.append(f"```text\n{snippet}\n```\n")
    return "\n".join(lines)
