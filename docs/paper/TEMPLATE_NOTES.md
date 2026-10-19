# Springer Word 2003 template handoff

The generated paper already mirrors the supplied proceedings layout:

- page size: 155 × 235 mm;
- text area: 122 × 193 mm;
- Times New Roman body text, 10 pt with 12 pt leading;
- separate styles for title, authors, affiliation, abstract, keywords,
  headings, captions, equations, tables, normal text, and references;
- numbered section headings, figure/table captions, hanging references, and
  first-line indentation following the supplied instructions.

The supplied `svlnproc1104.dot` is a legacy binary Word 97--2003 template with
macros. `python-docx` cannot execute or embed those macros. If the venue checks
the attached template rather than only the visible formatting, perform this
final step in Microsoft Word:

1. Keep the DOCX and `svlnproc1104.dot` in the same folder.
2. Open the generated DOCX.
3. Select **Tools → Templates and Add-Ins** (or **Developer → Document
   Template** in a newer Word version).
4. Select `svlnproc1104.dot`, enable **Automatically update document styles**,
   and confirm.
5. Save and reopen the paper; accept the template page setup if Word asks.
6. Recheck title, headings, captions, equations, tables, and references. The
   template instructions note that direct formatting may need the relevant
   style to be reapplied.

Do not open the DOT with **File → Open**, because that edits the template
instead of attaching it to a manuscript.
