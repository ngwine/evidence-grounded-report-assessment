import re

def approx_token_count(text):
    words = len(text.split())
    return max(1, int(words * 1.3))


def _format_table_text(rows):
    lines = []
    for row in rows:
        cells = [c for c in row if c]
        if not cells:
            continue
        if len(row) == 2:
            lines.append(f"{row[0]}: {row[1]}")
        else:
            lines.append(" - ".join(row))
    return "\n".join(lines)


def _breadcrumb(section_path):
    return " > ".join(section_path) if section_path else ""


def chunk_elements(elements, max_tokens=400, min_tokens=40):
    raw_chunks = []

    def flush_buffer(buf_texts, section_path, source_refs):
        if not buf_texts:
            return
        pieces, cur, cur_refs = [], [], []
        for t, ref in zip(buf_texts, source_refs):
            trial = cur + [t]
            trial_tokens = approx_token_count(" ".join(trial))
            if cur and trial_tokens > max_tokens:
                pieces.append((cur, cur_refs))
                cur, cur_refs = [], []
            cur.append(t)
            cur_refs.append(ref)
        if cur:
            pieces.append((cur, cur_refs))
        for texts, refs in pieces:
            joined = " ".join(texts)
            raw_chunks.append({
                "type": "text",
                "section_path": list(section_path),
                "section_paths": [list(section_path)],
                "text": joined,
                "text_with_context": (f"[{_breadcrumb(section_path)}] " if section_path else "") + joined,
                "source_refs": refs,
                "token_count": approx_token_count(joined),
            })

    buf_texts, buf_section, buf_refs = [], None, []

    def ref_of(el):
        return el.get("para_index", el.get("page"))

    for el in elements:
        if el["type"] == "heading":
            continue

        if el["type"] in ("paragraph", "caption", "reference"):
            sp = tuple(el["section_path"])
            if buf_section is not None and sp != buf_section:
                flush_buffer(buf_texts, buf_section, buf_refs)
                buf_texts, buf_refs = [], []
            buf_section = sp
            buf_texts.append(el["text"])
            buf_refs.append(ref_of(el))

        elif el["type"] == "table":
            if buf_texts:
                flush_buffer(buf_texts, buf_section, buf_refs)
                buf_texts, buf_refs = [], []
            table_text = _format_table_text(el["rows"])
            sp = el["section_path"]
            raw_chunks.append({
                "type": "table",
                "section_path": list(sp),
                "section_paths": [list(sp)],
                "text": table_text,
                "text_with_context": (f"[{_breadcrumb(sp)}] " if sp else "") + table_text,
                "source_refs": [ref_of(el)],
                "token_count": approx_token_count(table_text),
            })

    if buf_texts:
        flush_buffer(buf_texts, buf_section, buf_refs)

    merged = []
    for ch in raw_chunks:
        if (merged and ch["type"] == "text" and merged[-1]["type"] == "text"
                and ch["token_count"] < min_tokens
                and merged[-1]["section_path"][:1] == ch["section_path"][:1]):
            prev = merged[-1]
            trial_text = prev["text"] + " " + ch["text"]
            trial_tokens = approx_token_count(trial_text)
            if trial_tokens <= max_tokens:
                prev["text"] = trial_text
                prev["text_with_context"] = prev["text_with_context"] + " " + ch["text"]
                prev["source_refs"] += ch["source_refs"]
                prev["token_count"] = trial_tokens
                if ch["section_path"] not in prev["section_paths"]:
                    prev["section_paths"].append(ch["section_path"])
                if len(ch["section_path"]) > len(prev["section_path"]):
                    prev["section_path"] = ch["section_path"]
                continue
        merged.append(dict(ch))

    for i, ch in enumerate(merged):
        ch["chunk_id"] = i

    return merged