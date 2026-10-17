# Auditoria SEO · GEO · AEO (Metodologia Carratu)

Skill para o Claude que audita a visibilidade de um site na busca tradicional (SEO), nos motores de IA
generativa (GEO: ChatGPT, Perplexity, Gemini, Claude, AI Overviews/AI Mode) e em respostas diretas (AEO),
com base em evidências de 2026, e entrega um relatório DOCX e PDF pronto para cliente.

**Autor:** Ubirajara Carratu · [Carratu Digital](https://carratu.com.br) · Versão 1.1.1 (outubro de 2026)

## O que ela faz de diferente

- **Lê o HTML real** que os buscadores e os bots de IA recebem (não um resumo da página), com um coletor em
  Python e um coletor alternativo que roda no navegador quando o ambiente bloqueia o acesso direto.
- **Checa o acesso dos bots de IA**: robots.txt por bot (separando treino de busca), bloqueio por firewall/CDN
  com teste de user-agent, cobrança por rastreio do Cloudflare (HTTP 402) e conteúdo que só existe com JavaScript.
- **53 checks ponderados** com nível de evidência (teste controlado, correlação, prática de mercado) e itens
  sabidamente sem efeito (llms.txt, FAQ schema) marcados como informativos.
- **Notas de 0 a 100 com índice de confiança**: o relatório mostra quanto da nota foi de fato medido.
- **Saúde técnica de verdade**: links internos quebrados, redirecionamentos e cadeias, URLs do sitemap com erro ou
  noindex, hreflang, verificação no Bing e preço visível em texto (o que a IA usa para responder "quanto custa").
- **Dados externos sob demanda, sem dependência**: pergunta no início quais ferramentas usar. Com Semrush, puxa
  rankings e citações em AI Overviews respeitando um teto de unidades; sem Semrush, usa Search Console, amostra
  por busca na web ou navegador. As mesmas planilhas (`serp.csv`, `prompts.csv`) servem para qualquer fonte.
- **Painel de prompts com método**: várias rodadas por motor, taxa de menção e share of voice, nunca "posição no
  ChatGPT" de uma rodada só.
- **Relatório de agência** em DOCX e PDF: capa com notas, gráfico por pilar, resumo executivo, prioridades por
  impacto e esforço, plano 30/60/90 dias, visibilidade medida, análise check a check com evidência e como corrigir.
- **Diagnóstico de 1 página** com CTA da sua marca, para prospecção e isca de topo de funil.
- **Duas identidades prontas**: relatório completo com a marca Carratu Digital e diagnóstico de 1 página com a
  identidade escura da Carratu revenue growth consulting (Space Grotesk + Inter embutidas no PDF).
- **White label**: troque `assets/brand.json` e `assets/brand-consultoria.json` (cores, fontes, logo, CTA e
  rodapé) para usar com a sua marca.

## Instalação no app do Claude (desktop ou web)

1. Baixe o arquivo `carratu-seo-geo-aeo.zip`.
2. No Claude, abra **Configurações → Capacidades** (ou **Personalizar → Skills**) e adicione uma skill enviando o ZIP.
3. Garanta que a execução de código esteja ativada. Para auditar qualquer site direto pelo Python, libere o acesso
   de rede do ambiente de código; sem isso a skill usa o navegador (Claude in Chrome) ou um modo limitado.
4. Opcional: conecte o Semrush (e outros conectores) para a parte de dados.

## Como usar

> "Faça uma auditoria completa de SEO, GEO e AEO do site exemplo.com.br"
> "Meu site está pronto para aparecer no ChatGPT? acme.com.br"
> "Auditoria rápida de visibilidade em IA para o cliente X, comparando com os concorrentes Y e Z"

A skill faz uma rodada curta de perguntas (tipo de auditoria, contexto do negócio, fontes de dados, objetivo),
coleta, analisa, pontua e entrega o resumo no chat e os arquivos.

## Estrutura

```
carratu-seo-geo-aeo/
├── SKILL.md                    fluxo da auditoria (o Claude lê primeiro)
├── README.md
├── assets/
│   ├── brand.json              identidade do relatório completo (Carratu Digital)
│   ├── brand-consultoria.json  identidade do diagnóstico de 1 página (consultoria, tema escuro)
│   ├── logos/                  logos da consultoria e da Carratu Digital
│   └── fonts/                  Space Grotesk e Inter (licença OFL)
├── references/
│   ├── rubric.json             checks, pesos e níveis de evidência
│   ├── evidence-2026.md        base de evidências e mitos, com fontes
│   ├── manual-checks.md        critérios dos checks qualitativos
│   ├── data-sources.md         Semrush, PageSpeed, prompts, menções externas
│   └── report-schema.md        formato da narrativa e regras de priorização
└── scripts/
    ├── crawl.py                coleta direta (robots, bots de IA, sitemap, páginas)
    ├── browser_collect.js      coleta pelo navegador (mesmo formato de dados)
    ├── from_browser.py         monta os dados da coleta pelo navegador
    ├── extract.py              extração de sinais do HTML
    ├── linkcheck.py            links internos, redirecionamentos e saúde do sitemap
    ├── data_metrics.py         visibilidade medida a partir de serp.csv e prompts.csv
    ├── analyze.py              checks automáticos
    ├── set_check.py            registra checks manuais e de dados
    ├── score.py                notas e confiança
    └── build_report.py         relatório DOCX e PDF (completo e diagnóstico de 1 página)
```

Requisitos: Python 3.10+, `beautifulsoup4`, `python-docx`; `matplotlib` (gráfico) e LibreOffice (PDF) opcionais.

## Manutenção

GEO muda rápido. Revise `references/evidence-2026.md` a cada 6 meses (a própria skill avisa e confirma por busca
os itens marcados com ⚠ quando a base está velha). Ao mudar pesos ou checks, edite `references/rubric.json`; os
checks automáticos novos precisam de uma função correspondente em `scripts/analyze.py`.

## Histórico

**1.1.1** (out/2026): diagnóstico de 1 página com a identidade da Carratu revenue growth consulting (tema escuro,
logo, Space Grotesk e Inter embutidas) e rodapé com a logo da Carratu Digital.

**1.1.0** (out/2026): checks de links quebrados, redirecionamentos, saúde do sitemap, hreflang, Bing e preço
visível; módulo de visibilidade com ou sem Semrush (`data_metrics.py`) e teto de unidades; gráfico por pilar;
diagnóstico de 1 página com CTA.

**1.0.0** (out/2026): primeira versão.
