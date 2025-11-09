import difflib
import html

# ---------- GitHub-like unified diff renderer ----------
def make_github_like_unified_html(a: str, b: str, filename_a="original", filename_b="fixed", n=3) -> str:
    """
    Tạo unified diff và render HTML với màu giống GitHub:
      - dòng thêm: xanh nhạt
      - dòng xoá: đỏ nhạt
      - meta (@@, --- +++) xanh nhạt
      - context: nền trắng
    """
    udiff = list(difflib.unified_diff(
        a.splitlines(keepends=False),
        b.splitlines(keepends=False),
        fromfile=filename_a, tofile=filename_b, n=n
    ))

    if not udiff:
        return """
        <div class="diff-gh">
          <div class="diff-meta">No changes</div>
        </div>
        """

    # Escape HTML và gán class theo ký hiệu đầu dòng
    lines_html = []
    for raw in udiff:
        esc = html.escape(raw)
        if raw.startswith('+++') or raw.startswith('---') or raw.startswith('@@'):
            lines_html.append(f'<div class="diff-line meta">{esc}</div>')
        elif raw.startswith('+'):
            lines_html.append(f'<div class="diff-line add">{esc}</div>')
        elif raw.startswith('-'):
            lines_html.append(f'<div class="diff-line del">{esc}</div>')
        else:
            # space hoặc các dòng khác
            lines_html.append(f'<div class="diff-line ctx">{esc}</div>')

    styles = """
    <style>
      .diff-wrapper {
        border: 1px solid #e1e4e8;
        border-radius: 8px;
        overflow: hidden;
        background: #fff;
      }
      .diff-gh {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 13px;
        line-height: 1.5;
        white-space: pre;
      }
      .diff-line { padding: 2px 10px; }
      .diff-line.add   { background: #e6ffed; color: #24292e; }  /* xanh nhạt */
      .diff-line.del   { background: #ffeef0; color: #24292e; }  /* đỏ nhạt  */
      .diff-line.ctx   { background: #ffffff; color: #24292e; }  /* trắng     */
      .diff-line.meta  { background: #f1f8ff; color: #032f62; font-weight: 600; } /* xanh meta */
      .diff-header {
        background: #f6f8fa;
        border-bottom: 1px solid #e1e4e8;
        padding: 8px 12px;
        font-weight: 600;
      }
      .section-title {
        margin: 10px 0 6px;
        font-weight: 600;
        color: #24292e;
      }
    </style>
    """
    body = f"""
    <div class="diff-gh">
      {''.join(lines_html)}
    </div>
    """
    return styles + body