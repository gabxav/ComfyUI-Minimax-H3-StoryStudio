[← README](../README.md)

# Guia rápido · StoryStudio

**Um node para organizar prompts, referências e uma história em várias cenas de até 15 segundos.** Os últimos frames e o áudio de cada cena podem servir de contexto temporal para a próxima. O AudioRefine já está incluído com a correção de retenção de RAM.

![StoryStudio](assets/banner.svg)

## Instalação

1. Tenha um ComfyUI recente com suporte nativo ao MiniMax H3, modelos compatíveis, CLIP e VAEs de vídeo/áudio.
2. Instale o [Director da AIMixer](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director), usado para o contexto temporal.
3. Clone este repositório em `ComfyUI/custom_nodes/ComfyUI-Minimax-H3-StoryStudio`.
4. Instale `requirements.txt` com o Python do ComfyUI. Tenha FFmpeg e ffprobe disponíveis no `PATH`.
5. Aguarde a fila terminar, reinicie o ComfyUI e atualize o navegador.

```bash
cd ComfyUI
git clone https://github.com/gabxav/ComfyUI-Minimax-H3-StoryStudio.git custom_nodes/ComfyUI-Minimax-H3-StoryStudio
```

Com o interpretador que executa o ComfyUI:

```bash
python -m pip install -r custom_nodes/ComfyUI-Minimax-H3-StoryStudio/requirements.txt
```

Ajuste o caminho conforme sua pasta atual. No Windows portable, use o `python_embeded\python.exe`. Se já tiver uma versão local antiga do StoryStudio, mova a pasta antiga para fora de `custom_nodes` antes de reiniciar; mantenha uma única instalação.

O pacote AudioRefine separado não é necessário. KJNodes/SageAttention são opcionais: selecione `attention=disabled` se não estiverem disponíveis.

## Primeira história

Importe [workflows/story_studio.json](../workflows/story_studio.json). O exemplo tem três cenas genéricas, sem arquivos de mídia, e começa em 512 × 512.

1. Selecione os arquivos de **REF2VA**, **FL2VA**, **CLIP**, **VAE de vídeo** e **VAE de áudio** presentes na sua instalação.
2. Escolha a Turbo LoRA e os passos adequados ao seu modelo. REF2VA gera vídeo e áudio; FL2VA é usado somente se o refinamento estiver ligado.
3. Clique em **Abrir Story Studio**.
4. Edite o prompt e a duração de cada cena. Adicione imagens, vídeos e áudios no editor.
5. Clique em **Continuar sequência**.

![Editor de cenas](assets/editor.png)

As referências comuns valem para todas as cenas. As extras valem apenas para a cena selecionada. Use os números apresentados no editor: `<Picture 1>`, `<Video 1>` e `<Audio 1>`. O total comum + individual permite até 9 imagens, 3 vídeos e 3 áudios por cena.

Para vídeo e áudio, escolha o início e o trecho de até 15 segundos. Um vídeo de referência fornece frames; para usar também sua trilha como referência sonora, adicione o mesmo arquivo na coluna de áudios.

Não existem conectores `reference_image`, `reference_video` ou `reference_audio` no node principal. Todas as referências são organizadas dentro do editor.

## Continuar, refazer e pausar

| Botão | Resultado |
| --- | --- |
| **Continuar sequência** | Gera da primeira cena pendente/desatualizada até a última e monta o filme. |
| **Gerar próxima cena** | Gera apenas a próxima pendente. |
| **Gerar / refazer selecionada** | Cria uma nova tomada da cena escolhida. |
| **Parar após esta cena** | Conclui a cena atual e não enfileira outra. |

Salvar no editor atualiza o node aberto. Use também **Salvar workflow** do próprio ComfyUI para conservar suas alterações. A sequência continua no servidor com o editor fechado. Depois de reiniciar o servidor, use **Continuar sequência** para retomar.

Ao refazer uma cena, as seguintes que dependem dela ficam desatualizadas. As tomadas anteriores permanecem no disco. Para começar outro projeto mantendo o roteiro, use **Criar nova história a partir desta**.

## Continuidade e áudio

O padrão usa os **22 frames finais a 24 fps**, cerca de 0,92 segundo, e a cauda correspondente do áudio. Eles são codificados como contexto temporal da próxima geração. Depois, o trecho de contexto e os frames excedentes são removidos: cada cena de 15 segundos exporta 360 frames.

A grade interna H3 é `17k + 5`: a primeira cena usa 362 frames; com 22 frames de contexto, usa 396. Essa janela interna passa de aproximadamente 15 segundos. A qualidade depende do modelo, do prompt e da quantidade de contexto; não há garantia de emenda invisível, rosto perfeito, fala exata ou cenário idêntico.

- **audio_refine:** liga a segunda passagem com FL2VA, sem Turbo LoRA.
- **audio_steps / audio_denoise:** controlam os passos e a intensidade do refinamento.
- **audio_cache:** usa cache `hidden / int4 / auto`, sem cache em disco. É uma aproximação e pode ser desligado para comparação.

## Correção de RAM já incluída

O [PR #1 do AudioRefine](https://github.com/Adudeguyman/ComfyUI-H3-AudioRefine/pull/1) propõe manter os tensores persistentes do cache em memória comum de CPU, com `pin_memory=False`. Isso evita a retenção desses grandes blocos pelo alocador de memória fixada do PyTorch após sucessivas reconstruções do cache. As transferências podem ficar mais lentas que as feitas a partir de RAM fixada.

O StoryStudio inclui os arquivos do commit `34862c6` com essa correção, sem depender da aprovação do PR e sem alterar outra instalação do AudioRefine. [Créditos, hashes e licença](../THIRD_PARTY_NOTICES.md).

## Onde ficam os resultados

Em `ComfyUI/output/story_director/<project_id>/`: vídeos individuais, checkpoints `.pt`, `manifest.json`, `job.json` e filme montado. Guarde os checkpoints para poder continuar a partir das cenas salvas.

A validação inicial gerou três cenas reais de 15 segundos em 512 × 512, testou continuação, refinamento, nova tomada, pausa e retomada, e produziu um filme de 45 segundos. Consulte o [README](../README.md#validation-and-limits) para os testes e limites.
