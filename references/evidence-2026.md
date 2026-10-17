# Base de evidências SEO · GEO · AEO (revisada em out/2026)

Use este arquivo para justificar recomendações e para não vender mito. Cada item traz o nível de evidência:
**S** forte (teste controlado ou documentação oficial), **C** correlacional (grande base observacional),
**A** anedótico, **M** mito ou contestado. Ao citar um número no relatório, cite a fonte.

> Este campo muda rápido. Se a auditoria acontecer mais de 6 meses depois da data acima, faça 3 a 5 buscas
> para confirmar os itens marcados com ⚠ antes de afirmá-los.

## 1. Princípio central

- GEO e AEO são extensões de SEO, não substitutos. O guia oficial do Google para otimização em recursos de IA
  (mai/2026) diz que não há requisito extra: a página precisa estar indexada e elegível a snippet, e o que mais
  pesa é conteúdo original e não comoditizado. **S** · [Google AI features](https://developers.google.com/search/docs/appearance/ai-features), [AI optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
- Por isso a auditoria começa pela fundação técnica e de conteúdo, e só depois entra na camada de IA.

## 2. O que se correlaciona com ser citado por IA

| Fator | Achado | Nível | Fonte |
|---|---|---|---|
| Menções da marca na web | Correlação de ~0,66 com visibilidade em AI Overviews, contra ~0,22 de backlinks (75 mil marcas). Menções no YouTube chegaram a ~0,74 | C | Ahrefs, mai/2025, atual. abr/2026 |
| Mídia conquistada | ~84% de 25 mi de links citados por IA vêm de mídia conquistada (earned) | C | Muck Rack, mai/2026 |
| Reviews e comunidades | Domínios presentes em G2/Capterra/Trustpilot e com muitas menções em Reddit/Quora recebem 2 a 4x mais citações no ChatGPT | C | SE Ranking, nov/2025 (129 mil domínios) |
| Resposta no início | 44% das citações do ChatGPT saem do primeiro terço da página; trechos citados têm ~2x mais definições diretas e alta densidade de nomes próprios | C | Kevin Indig, fev/2026 (18 mil citações) |
| Seções de 120 a 180 palavras | Média de 4,6 citações contra 2,7 em seções com menos de 50 palavras | C | SE Ranking |
| Dados e citações | Páginas com 19+ estatísticas: 5,4 citações vs 2,8; com citações de especialistas: 4,1 vs 2,4 | C | SE Ranking |
| Atualização | Atualizadas há menos de 3 meses: 6,0 citações vs 3,6. URLs citadas por IA são ~26% mais novas que as orgânicas | C | SE Ranking; Ahrefs, jul/2025 |
| Listas "melhores X" | ~44% das fontes do ChatGPT em prompts comerciais são listas; listas de terceiros pesam mais | C | Ahrefs, dez/2025 |
| HTML no servidor | GPTBot, ClaudeBot, PerplexityBot e CCBot não executam JavaScript; ChatGPT, Claude, Perplexity e Copilot leem só o HTML visível em buscas ao vivo | S | Vercel/MERJ, dez/2024; teste de Andre Alpar |
| Experimento GEO original | Adicionar citações, estatísticas e fontes elevou a participação na resposta em até ~40% em simulador. Sem replicação independente; benchmarks posteriores acharam efeito pequeno | S (lab) / contestado | Aggarwal et al., KDD 2024; survey arXiv 2607.14035 |

## 3. Diferenças entre motores ⚠

- Só ~38% das citações de AI Overviews vêm do top 10 orgânico (mar/2026), contra 76% em jul/2025. O fan-out de
  consultas puxa fontes de fora do top 100. **C** · Ahrefs, mar/2026
- AI Overviews e AI Mode compartilham só ~14% das URLs citadas. **C**
- Sobreposição com o top 10 do Google: Perplexity ~29%, ChatGPT ~8%. **C** · Ahrefs, ago/2025
- Claude usa o Brave Search como base; ~87% das URLs citadas aparecem no top do Brave. **A**
- O ChatGPT tem ~99% do tráfego de IA generativa no Brasil (310 mi de visitas em ago/2025). Para clientes
  brasileiros, priorize ChatGPT e Google (AI Overviews/AI Mode); Perplexity em segundo plano. **C** · Similarweb/Cadastra, nov/2025
- As fontes citadas mudam muito: sobreposição de 34 a 42% de um dia para o outro; respostas de recomendação
  repetem a mesma lista em menos de 1% das vezes. **Nunca** audite visibilidade em IA com uma rodada só. **S** · SparkToro/Gumshoe, jan/2026

## 4. Mitos e itens contestados (não pontuam ou pontuam pouco)

| Afirmação | Veredito |
|---|---|
| llms.txt aumenta citações | **M.** ~300 mil domínios, nenhuma correlação (SE Ranking, out/2026); 97% dos arquivos recebem zero acessos (Ahrefs, jun/2026); o Google diz que não usa |
| Schema aumenta citações em IA | **M/contestado.** Teste controlado da Ahrefs (mai/2026) não achou ganho relevante. Mantenha schema para rich results e clareza de entidade, não como alavanca de GEO |
| FAQ schema gera rich result | **Encerrado.** O Google acabou com o rich result de FAQ para todos os sites em 07/05/2026. HowTo saiu em set/2023 |
| Palavra-chave na URL/title aumenta citação | **M.** Correspondência exata alta veio com menos citações nos dados da SE Ranking |
| Rankear em 1º garante AI Overview | **Enfraquecido.** Só 38% das citações vêm do top 10 |
| Headings em pergunta sempre ajudam | **Contestado.** Use quando espelham consultas reais, não como fórmula |
| Ser citado traz cliques | **Parcial.** CTR orgânico cai muito em consultas com AI Overview, mas marcas citadas recebem ~35% mais cliques orgânicos que as não citadas (Seer, nov/2025) |
| Listas "melhores X" em que a própria marca aparece em 1º | Funcionam no curto prazo (~11% das citações em nichos de software), mas há risco reputacional e de rebaixamento. Prefira entrar em listas de terceiros |

## 5. Fatos técnicos de 2026 ⚠

- `Google-Extended` é só um token de controle para treino e grounding do Gemini. Bloqueá-lo **não** tira o site
  dos AI Overviews; isso só acontece via Googlebot, `nosnippet`/`max-snippet`/`noindex` ou o controle de IA
  generativa do Search Console (jun/2026, começou no Reino Unido).
- Bots de usuário (ChatGPT-User, Perplexity-User, Google-Agent) geralmente ignoram robots.txt. Bloqueio, se
  desejado, é no WAF.
- Cloudflare: desde jul/2025 novos domínios bloqueiam bots de IA por padrão; desde 15/09/2026 novos domínios
  bloqueiam bots de treino e de agente em páginas com anúncios, e bloquear treino pode bloquear também Googlebot,
  Bingbot e Applebot (crawlers multiuso). Pay-per-crawl responde HTTP 402 com cabeçalho `crawler-price`.
- Core Web Vitals: LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1, no percentil 75.
- Search Console tem relatório de desempenho em IA generativa (beta desde 03/06/2026, só impressões, nem todas as
  propriedades). Bing Webmaster Tools tem relatório de desempenho em IA (prévia desde fev/2026, mostra citações).
- IndexNow: Bing, Yandex, Seznam, Naver, Yep, Amazon. O Google não participa. Não há confirmação oficial de que o
  ChatGPT use o índice do Bing; o índice próprio é feito pelo OAI-SearchBot.
- Rich results ainda suportados (galeria, out/2026): Article, Breadcrumb, Carousel, Dataset, Discussion forum,
  Event, Image metadata, Job posting, Local business, Movie, Organization, Product, Profile page, Q&A, Recipe,
  Review snippet, Software app, Speakable (beta), Subscription/paywalled, Vacation rental, Video.
- "Fontes preferidas" do Google (preferred sources): só domínios/subdomínios; botão ou deeplink
  `google.com/preferences/source?q=dominio`. Relevante para publishers.

## 6. Medição

- Métricas: taxa de menção (% das respostas que citam a marca em várias rodadas), taxa de citação (% com URL da
  marca), share of voice (menções da marca ÷ menções de todos os concorrentes monitorados), sentimento e
  exatidão dos fatos, mapa de fontes citadas.
- Posição dentro da resposta: reporte só em faixas (primeiro terço, meio, fim).
- GA4: grupo de canais "IA" acima de Referral com regex de origem, por exemplo
  `^(chatgpt\.com|chat\.openai\.com|perplexity\.ai|gemini\.google\.com|claude\.ai|copilot\.microsoft\.com|deepseek\.com|grok\.com)$`.
  Cliques de AI Overviews/AI Mode entram como orgânico e não podem ser separados. Entre 08 e 16/10/2026 o ChatGPT
  perdeu a marcação `utm_source=chatgpt.com` em parte dos links (visitas apareceram como Direto).
- Ferramentas pagas de visibilidade em IA mostram amostras e servem para tendência, não para verdade absoluta.

## Fontes principais

- Ahrefs: [citações de AI Overviews fora do top 10](https://ahrefs.com/blog/ai-overview-citations-top-10), [menções de marca](https://ahrefs.com/blog/ai-overview-brand-correlation/), [frescor](https://ahrefs.com/blog/do-ai-assistants-prefer-to-cite-fresh-content/), [listas](https://ahrefs.com/blog/best-lists-research/), [schema](https://ahrefs.com/blog/schema-ai-citations/), [llms.txt](https://ahrefs.com/blog/llmstxt-study/)
- [SE Ranking via SEJ: fatores de citação do ChatGPT](https://www.searchenginejournal.com/new-data-top-factors-influencing-chatgpt-citations/561954/) · [SE Ranking: llms.txt](https://seranking.com/blog/llms-txt/)
- [Kevin Indig via Search Engine Land](https://searchengineland.com/chatgpt-citations-content-study-469483)
- [SparkToro/Gumshoe via Search Engine Land](https://searchengineland.com/ai-recommendation-lists-rarely-repeat-study-468076)
- [Microsoft Ads: conteúdo para respostas de IA](https://about.ads.microsoft.com/en/blog/post/october-2025/optimizing-your-content-for-inclusion-in-ai-search-answers)
- [Vercel: crawlers de IA e JavaScript](https://vercel.com/blog/the-rise-of-the-ai-crawler)
- [Google FAQPage](https://developers.google.com/search/docs/appearance/structured-data/faqpage) · [Galeria de dados estruturados](https://developers.google.com/search/docs/appearance/structured-data/search-gallery) · [Crawlers do Google](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers)
- [OpenAI bots](https://developers.openai.com/api/docs/bots) · [Anthropic crawlers](https://support.claude.com/en/articles/8896518) · [Perplexity crawlers](https://docs.perplexity.ai/docs/resources/perplexity-crawlers.md)
- [Cloudflare pay-per-crawl](https://blog.cloudflare.com/introducing-pay-per-crawl/)
- [Aleyda Solis: checklist de otimização para busca com IA](https://www.aleydasolis.com/en/ai-search/ai-search-optimization-checklist)
- [Peec AI: domínios mais citados por motor](https://docs.peec.ai/research/most-cited-domains-by-engine)
- [Meio & Mensagem: ChatGPT domina IA no Brasil](https://www.meioemensagem.com.br/marketing/chatgpt-domina-mercado-de-inteligencia-artificial-no-brasil)
- [Seer Interactive: impacto de AI Overviews no CTR](https://www.seerinteractive.com/insights/aio-impact-on-google-ctr-september-2025-update)
