# Módulos de dados externos (com ou sem Semrush)

Cada módulo é opcional e roda só se o usuário aprovar no briefing. A skill **não depende de nenhuma ferramenta
paga**: todo módulo tem um caminho com Semrush (ou outra ferramenta conectada) e um caminho sem.

Para descobrir o que existe, olhe a lista de ferramentas da sessão (conectores aparecem pelo nome do serviço:
Semrush, HubSpot, Search Console, Google Analytics, Claude in Chrome). Se uma ferramenta estiver como "deferred",
carregue o schema pela busca de ferramentas antes de chamar. Se o usuário quiser um conector que não está
ligado, procure no registro de conectores e sugira; nunca invente acesso.

As duas métricas centrais de visibilidade usam **planilhas padrão**, preenchidas por qualquer fonte:

```bash
python3 SKILL_DIR/scripts/data_metrics.py template audit_data          # cria prompts.csv e serp.csv
python3 SKILL_DIR/scripts/data_metrics.py serp audit_data/serp.csv --domain site.com.br --findings audit_data/findings.json
python3 SKILL_DIR/scripts/data_metrics.py prompts audit_data/prompts.csv --brand "Marca" --aliases "Marca X,site.com.br" --findings audit_data/findings.json
```

O script calcula as taxas, atualiza os checks `vis.*` e grava `audit_data/visibility.json`, que entra sozinho
na seção "Visibilidade medida" do relatório. Listas dentro de uma célula: separe com `|`.

---

## 1. Palavras-chave do ICP → `serp.csv` → `vis.rankings`, `vis.ai_overviews`

**Passo comum:** monte com o usuário de 10 a 25 palavras-chave que geram negócio (categoria, problema,
comparação, preço, local se for o caso). Se ele não souber, proponha a partir do site e do ICP e peça validação.

Colunas: `keyword, intent, source, position, url, aio_present, aio_cites_brand, competitors_top10`

### Com Semrush (conector MCP)

O conector funciona em 3 passos: a ferramenta de descoberta do toolkit lista relatórios, `get_report_schema`
mostra os parâmetros, `execute_report` traz os dados. Use o nome do relatório exatamente como a descoberta devolve.

- **Base:** `br` para sites brasileiros (o padrão do conector é `us`); para outros mercados, o país do ICP.
- **Orçamento de unidades:** cada linha retornada consome unidades de API. Antes de começar, mostre a estimativa
  e peça um teto ao usuário (sugestão: até ~3.000 unidades na auditoria rápida, ~10.000 na completa).
  Use `display_limit` de 10 a 50, filtre por palavra-chave em vez de puxar o domínio inteiro e pare ao atingir o teto.
  Se o resultado trouxer o consumo, some e informe no final.

Roteiro:
1. **Visão do domínio** (`domain_overview`): tráfego orgânico estimado, nº de palavras-chave e tendência
   → evidência para `seo.organic_footprint` (pass se a pegada é coerente com o porte e crescente; warn se
   estagnada ou em queda; fail se quase nula para um site com conteúdo).
2. **Posições nas palavras do ICP** (`organic_research`, relatório de posições do domínio filtrado pelas
   palavras): preencha `position` e `url` no `serp.csv`, `source = semrush`.
3. **AI Overviews:** no mesmo relatório, peça posições do tipo SERP features
   (`display_positions_type=serp_features`) e procure linhas com `position_type = "AI overview"`: indicam que o
   domínio é citado no AI Overview daquela palavra (`aio_cites_brand = 1`). Para saber se a palavra exibe AI
   Overview (`aio_present`), use as colunas de SERP features da palavra (código 52 = AI Overview).
   Em Position Tracking (se houver projeto), o filtro `serp_feature_filter=aio` acompanha isso diariamente.
4. **Concorrentes orgânicos** (`competitors_research`) → coluna `competitors_top10` e escolha dos concorrentes
   do painel de prompts.
5. **Backlinks** (`backlinks_research`): domínios de referência e mídia que linka → apoio a `geo.offsite_presence`.

O conector não expõe o rastreamento de prompts do ChatGPT/AI Mode do AI Visibility Toolkit. Para isso, módulo 4.

### Sem Semrush

Use, nesta ordem, o que houver:
- **Search Console conectado:** consultas, posição média e páginas; `source = gsc` (dado real do Google, o
  melhor substituto).
- **Busca na web:** pesquise cada palavra-chave e registre a posição do domínio nos resultados, se houve
  resposta de IA no topo e se ela cita a marca; `source = websearch`. Diga no relatório que é amostra aproximada
  (resultado varia por localização e personalização). A busca na web do Claude não é o Google: sem Search
  Console ou Semrush, deixe `aio_present` vazio a menos que consiga observar o Google de fato.
- **Navegador (Claude in Chrome), com permissão:** abrir a busca do Google para cada palavra e anotar posição e
  AI Overview; `source = chrome`. Não altere configurações da conta.
- `seo.organic_footprint` sem Semrush nem Search Console: deixe `unknown` e explique em `limitations`.

## 2. Core Web Vitals → `seo.core_web_vitals`

- Endpoint público: `https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=URL&strategy=mobile&category=performance`
- Funciona sem chave, com cota pequena (erro 429 é comum). Rode para a home e 1 ou 2 páginas comerciais.
- Com rede liberada, use Python; sem rede, use a leitura de páginas da web pedindo os valores de campo (CrUX)
  de LCP, INP e CLS e a nota de performance mobile; ou abra pagespeed.web.dev pelo navegador.
- Avalie pelos dados de campo. Sem dados de campo, use laboratório e diga isso na evidência.
- pass: LCP ≤ 2,5 s, INP ≤ 200 ms e CLS ≤ 0,1 · warn: um fora · fail: dois ou mais fora.

## 3. Presença fora do site → `geo.offsite_presence`

Funciona igual com ou sem Semrush (o Semrush só acrescenta backlinks). Busca na web, uma consulta por frente:
- Imprensa e portais do setor nos últimos 12 meses.
- Comunidades: `"Marca" site:reddit.com`, fóruns do nicho.
- Vídeo: `"Marca" site:youtube.com` (canal próprio e de terceiros).
- Reviews B2B: G2, Capterra, B2B Stack, Trustpilot. Reputação no Brasil: Reclame Aqui.
- Entidade: Wikipedia, Wikidata, Crunchbase, LinkedIn da empresa.
- Listas de terceiros: `melhores [categoria] [ano]`, `alternativas a [concorrente]`.

pass: presença ativa em 3+ frentes relevantes ao ICP, incluindo listas de terceiros · warn: 1 ou 2 frentes ·
fail: a marca quase não existe fora do próprio site.

## 4. Painel de prompts em IA → `prompts.csv` → `vis.ai_answers`, `vis.competitors`

O teste mais importante de GEO, e o mais fácil de fazer errado.

1. **Monte o painel** com o usuário: 8 a 15 prompts em PT-BR (alguns em inglês se o ICP for internacional),
   cobrindo `intent`: problema, categoria, comparacao, alternativas, preco, e 1 ou 2 de `marca` (para checar
   exatidão e sentimento). Só os prompts sem o nome da marca entram na taxa de menção.
2. **Rode cada prompt 3+ vezes por motor.** Uma linha do CSV por resposta (`run` = 1, 2, 3).
3. **Como rodar**, do mais confiável ao mais limitado:
   - Ferramenta de visibilidade em IA conectada (ex.: ferramentas de AEO do HubSpot): exporte para o CSV;
     `engine` com o nome do motor.
   - Navegador do usuário (Claude in Chrome), com permissão explícita: chatgpt.com, gemini.google.com,
     perplexity.ai; conversa nova a cada rodada; registrar marcas citadas e domínios das fontes.
   - Busca na web do próprio Claude: proxy do Claude com busca, `engine = Claude (busca web)`.
   - Manual: entregue o CSV ao usuário para ele rodar e colar as respostas.
   Para clientes brasileiros, priorize ChatGPT e Google (AI Mode/AI Overviews).
4. **Por resposta:** `brand_mentioned`, `brand_cited` (URL da marca), `position` (inicio/meio/fim),
   `competitors`, `sources` (domínios citados), `accurate` (só em prompts de marca).
5. **Critérios (aplicados pelo script):** taxa de menção ≥ 50% pass, 15 a 49% warn, < 15% fail.
   Share of voice: pass se a marca tem ≥ 80% da participação do concorrente mais citado; warn ≥ 40%; fail abaixo.
6. O mapa de fontes citadas vira recomendação: onde a marca precisa estar (listas, reviews, mídia, comunidades).

## 5. Search Console, GA4 e Bing Webmaster

- **Search Console:** além do `serp.csv`, veja se a propriedade tem o relatório de IA generativa e exporte as
  páginas com impressões em AI Overviews/AI Mode.
- **GA4:** sessões vindas de `chatgpt.com`, `perplexity.ai`, `gemini.google.com`, `claude.ai`,
  `copilot.microsoft.com` e suas conversões. Sem grupo de canais "IA", recomende criar (regex em
  `evidence-2026.md`).
- **Bing Webmaster Tools:** o check `seo.bing_webmaster` só detecta verificação por meta tag ou arquivo. Se não
  achar, pergunte ao usuário (pode estar verificado por DNS) e registre com `set_check.py --source user`.

## 6. Sem nenhuma ferramenta

A auditoria continua válida para SEO, GEO e AEO de prontidão (o que está no site), e os módulos 2, 3 e 4
funcionam com busca na web e navegador. O que ficar sem dado fica `unknown`: diga em `limitations` exatamente
qual dado aumentaria a confiança e como obtê-lo.
