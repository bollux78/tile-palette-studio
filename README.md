# Tile Palette Studio — Mega Drive / Genesis

### 🎨 [▶️ Abrir Tile Palette Studio Web](https://bollux78.github.io/tile-palette-studio/)

**[Acessar o aplicativo online](https://bollux78.github.io/tile-palette-studio/)** · Funciona diretamente no navegador, sem instalação.

Converta imagens para as limitações gráficas do **Sega Mega Drive / Genesis**, com quantização por tiles de 8 × 8 pixels, até quatro paletas de 16 cores, dithering e exportação de dados para SGDK.

## Como usar

1. **[Abra o aplicativo](https://bollux78.github.io/tile-palette-studio/)** e use a imagem de exemplo ou carregue a sua.
2. Escolha uma resolução **H40 (320 × 224/240)** ou **H32 (256 × 224/240)** — ou informe dimensões personalizadas.
3. Ajuste o redimensionamento (**Lanczos, bicúbico, bilinear ou vizinho mais próximo**), o dithering e as paletas.
4. Clique em **Quantizar imagem** para comparar original e resultado.
5. Se precisar reduzir o uso de VRAM, configure o orçamento de tiles e ative opcionalmente a **substituição por similares**.
6. Baixe o **PNG paletizado** ou exporte o **pacote SGDK (.zip)**.

## Recursos

- **Dithering:** padrões Diagonal 2/4, Horizontal 2/4 e Vertical 2/4 baseados no projeto de Rilden, **Floyd–Steinberg com difusão de erro** e opção desligado.
- **Otimização de tiles:** reutilização de padrões idênticos e espelhamentos horizontais/verticais sem perda, seguida opcionalmente de redução por similaridade visual.
- **Exportação SGDK:** tiles 4bpp, tilemap com atributos e flips, paletas CRAM e arquivos auxiliares.
- **Formatos de entrada:** PNG, BMP, GIF (primeiro quadro), WebP, JPEG e AVIF quando suportado pelo navegador/Pillow.
- **Privacidade:** a imagem é processada localmente no navegador; não é enviada para um servidor.
- **Segurança:** o original não é sobrescrito automaticamente.

## Tecnologias e limitações

O processamento usa Python pelo **Pyodide**, com **NumPy** e **Pillow**. A primeira visita exige conexão para carregar essas bibliotecas. Imagens grandes podem consumir muita memória ou deixar a interface lenta.

O total de VRAM realmente disponível depende do jogo e dos recursos que já estejam carregados. A redução por similaridade pode introduzir alterações visuais; confira a prévia e valide os dados em uma ROM antes do uso definitivo.

## Referências

- [Rilden — tiledpalettequant](https://github.com/rilden/tiledpalettequant), referência para os padrões e o método de dithering.
- [OrionSoft — Super PNG2MD](https://orionsoft.itch.io/super-png2md), referência para a estratégia de otimização e reutilização de tiles.

O código de quantização e otimização deste repositório é uma implementação própria, não uma reprodução integral do Super PNG2MD.

---

**Site do aplicativo:** https://bollux78.github.io/tile-palette-studio/

## ROM de teste Mega Drive (.bin) — experimental

O botão **Gerar ROM de teste Mega Drive (.bin)** cria no próprio navegador uma ROM de 128 KiB com programa 68000 mínimo: inicialização do VDP, carregamento dos tiles 4bpp, plano A e quatro paletas CRAM. A imagem é estática; não há controles, som, menus ou animações.

A ROM de teste grava **cada tile 8×8 na posição original, sem deduplicação, espelhamentos ou substituições por similaridade**, para reproduzir a prévia quantizada sem artefatos de mapeamento. A otimização de tiles continua disponível separadamente na exportação SGDK.

**Primeira versão:** aceita H32 256×224 e H40 320×224. O gerador reserva a VRAM a partir de 0xC000 para o tilemap, permitindo até 1536 tiles únicos. Não usa o tile inicial configurado para exportação SGDK, pois a ROM independente carrega os tiles a partir do índice zero. Se exceder o limite, é necessário habilitar a redução por similaridade ou ajustar a imagem.

**Atenção:** o gerador é experimental e precisa ser validado em emulador e hardware real. Recomenda-se testar no emulador antes de usar no Mega EverDrive.
