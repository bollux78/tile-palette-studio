# Tile Palette Studio Web 1.0

Versão web do Tile Palette Studio Python para GitHub Pages. Usa **Pyodide**, NumPy e Pillow no navegador, preservando o `quantizer.py` original, inclusive os sete métodos de dithering e a exportação SGDK. Não há upload de imagens para servidores.

## Publicação

Envie `index.html`, `app.js` e `quantizer.py` para a raiz da branch `main` do repositório. Em **Settings → Pages**, selecione **Deploy from a branch → main → /(root)**. A URL será `https://bollux78.github.io/tile-palette-studio/`.

## Formatos

PNG, BMP, GIF (primeiro quadro), WebP, JPEG e AVIF (quando o navegador e a versão do Pillow suportarem). Exportação PNG e ZIP com os arquivos SGDK. A primeira visita precisa de internet para carregar o Pyodide; o processamento ocorre localmente.

## Notas

- Esta é a primeira versão web e deve ser validada com as imagens reais do usuário, comparando com a versão desktop.
- Imagens muito grandes podem consumir bastante memória e congelar a interface durante a quantização (o processamento ainda ocorre na thread principal).
- O navegador pode perguntar se deseja substituir um arquivo baixado com o mesmo nome; o Studio não tem permissão para modificar diretamente o arquivo de entrada.
- A versão web preserva o motor Python, mas não replica ainda todos os controles avançados da interface Tk.
