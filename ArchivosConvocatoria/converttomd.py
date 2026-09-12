import pymupdf4llm

# Convierte todo el PDF a un string en Markdown
md_text = pymupdf4llm.to_markdown("TO-02AyudantedeAlbañileria62102.pdf")

# Guardar el resultado en un archivo .md
with open("TO-02AyudantedeAlbañileria62102.md", "w", encoding="utf-8") as f:
    f.write(md_text)