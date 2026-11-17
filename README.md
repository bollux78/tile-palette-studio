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

## Precisão das cores do VDP

No Mega Drive, o índice de cor **0** em um tile de plano é transparente, independentemente do conteúdo de sua entrada na CRAM. Por isso o quantizador agora reserva automaticamente a entrada 0: cada paleta possui até **15 cores opacas**, mais o índice transparente. A opção de canal alfa controla apenas se pixels transparentes da imagem original devem ser mantidos.

A ROM de teste reserva o **tile gráfico 0 totalmente vazio** e carrega o primeiro tile da imagem no índice 1, impedindo que o plano B mostre fragmentos do primeiro tile através dos pixels transparentes. Essa correção foi testada com a imagem de exemplo em ROM H40, incluindo comparação de dados da ROM com a prévia e execução no BlastEm em runner GitHub Actions.

## ROM de teste Mega Drive (.bin) — experimental

O botão **Gerar ROM de teste Mega Drive (.bin)** cria no próprio navegador uma ROM de 128 KiB com programa 68000 mínimo: inicialização do VDP, carregamento dos tiles 4bpp, plano A e quatro paletas CRAM. A imagem é estática; não há controles, som, menus ou animações.

A ROM de teste grava **cada tile 8×8 na posição original, a partir do índice gráfico 1, sem deduplicação, espelhamentos ou substituições por similaridade**, para reproduzir a prévia quantizada sem artefatos de mapeamento. A otimização de tiles continua disponível separadamente na exportação SGDK.

**Primeira versão:** aceita H32 256×224 e H40 320×224. O gerador reserva a VRAM a partir de 0xC000 para o tilemap, permitindo até 1536 tiles únicos. Não usa o tile inicial configurado para exportação SGDK, pois a ROM independente carrega os tiles a partir do índice zero. Se exceder o limite, é necessário habilitar a redução por similaridade ou ajustar a imagem.

**Atenção:** o gerador é experimental e precisa ser validado em emulador e hardware real. Recomenda-se testar no emulador antes de usar no Mega EverDrive.

## ROM de teste com rolagem por direcional (experimental)

Para imagens maiores do que uma tela, escolha **ROM de teste → Rolagem com direcional** (ou Automático) e selecione **H40 320 × 224** ou **H32 256 × 224** para a janela de visualização. O botão de ROM gera um `.bin` autônomo: o controlador 1 movimenta a imagem em passos de **2 pixels por quadro**, utilizando os registradores de scroll horizontal e vertical do VDP para cima, baixo, esquerda e direita. O programa 68000 usa o scroll de hardware do VDP e um cache circular de tiles; só carrega uma nova faixa de tiles quando a câmera ultrapassa um limite de 8 pixels, preservando o índice 0 transparente. A ROM pode conter uma imagem de até **1024 × 1024 pixels** (e até 2 MiB); o canvas precisa ser pelo menos tão grande quanto a janela escolhida. Como a ROM é um visualizador de teste, o carregador atualiza somente a faixa de tiles que entra na tela, sem desligar o vídeo entre movimentos. O movimento ocorre em passos de 2 pixels sincronizados com o quadro (scroll por hardware), com atualização de faixas de tiles apenas ao cruzar limites de 8 pixels.

O modo de **ROM estática** continua disponível para 256 × 224 e 320 × 224. O gerador de ROM com direcional usa `scroll_rom.py` e o carregador 68000 `scroll_loader.b64`, compilado do fonte `scroll_loader.S`. Não há compilação no navegador nem conexão com servidor para processar as imagens (a aplicação apenas baixa seu próprio código e o carregador).

## Manter proporção com fundo preto

Marque **Manter proporção (encaixar sem cortar, fundo preto)** para preservar o aspecto da imagem original dentro das dimensões escolhidas. O maior eixo é usado como referência e o espaço restante fica preto; a imagem nunca é cortada. Com a opção desmarcada, a imagem é redimensionada exatamente às dimensões do canvas, mesmo que isso implique distorção. O comportamento vale para a quantização, ROM e PNG redimensionado.

### Resoluções PAL de 240 linhas

Os presets 320×240 e 256×240 foram mantidos e identificados como **PAL**. Servem para produzir gráficos com 30 linhas de tiles em vez de 28. As ROMs de teste atuais (estática e com direcional) continuam usando telas de 224 linhas; o preset PAL por si só não altera a inicialização V30 do VDP.

### Rolagem simétrica e Mega EverDrive X7

A ROM de rolagem usa uma reserva circular de **43 × 31 tiles (H40)** ou **35 × 31 (H32)** para pré-carregar faixas à frente e atrás da câmera. Ao inverter a direção (esquerda/cima), os próximos tiles já estão em VRAM e a atualização de faixa ocorre fora da região visível, evitando a espera adicional de VBlank da versão anterior.

As ROMs **estática e de rolagem** habilitam agora a interrupção vertical do VDP (V-Int), permitem interrupções após a inicialização e possuem um tratador mínimo com retorno por `RTE`. Isso corrige a condição documentada pelo fabricante na qual o menu *Start + baixo* do **Mega EverDrive X7** não funciona quando o jogo desativa o VBlank. **A compatibilidade final com o menu do X7 ainda precisa ser confirmada em cartucho real**; o BlastEm permite verificar a execução das ROMs, mas não o menu do EverDrive.

### Cache de tiles da ROM com rolagem (correção para imagens grandes)

O cache VRAM usa **46×32 padrões em H40** e **38×32 em H32**, com até duas colunas/linhas de margem atrás da câmera e margem à frente. A recarga de uma linha agora abrange a margem horizontal, e a recarga de uma coluna abrange a margem vertical, para evitar lacunas ao mudar o sentido do movimento numa imagem de 1024 pixels ou mais. São 1473 slots H40 incluindo tile zero reservado, dentro do limite de 1536 antes da tabela de nomes do plano A. Testes de propriedade verificam a correspondência entre cada posição visível, o name table e seu padrão VRAM após sequências longas e aleatórias de movimentos, inclusive ultrapassando os módulos 32/64 do VDP.
