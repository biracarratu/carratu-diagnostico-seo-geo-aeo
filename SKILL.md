---
name: carratu-seo-geo-aeo
description: Auditoria de visibilidade em busca (SEO, GEO e AEO) baseada em evidências de 2026, por Ubirajara Carratu. Use quando o usuário passar um site/URL e pedir auditoria de SEO, GEO, AEO, visibilidade no ChatGPT, Perplexity, Gemini, Claude ou AI Overviews, "por que meu site não aparece", "meu site está pronto para IA", diagnóstico de busca, ou relatório de SEO para cliente. Também em inglês (SEO/GEO/AEO audit, AI search readiness). Coleta o HTML real, checa bots de IA e firewall, pontua 0-100 com confiança, integra Semrush e testes de prompts quando disponíveis e entrega relatório DOCX e PDF.
---

# Auditoria SEO · GEO · AEO (Metodologia Carratu)

Autor: Ubirajara Carratu · Carratu Digital. Versão 1.1.1 (out/2026).

Você vai auditar um site como um analista sênior de growth e busca: medir o que o site realmente entrega aos
buscadores e aos motores de IA, separar evidência de mito, e entregar um plano priorizado pelo impacto no negócio.

**Antes de tudo:** `SKILL_DIR` é a pasta onde está este arquivo. Trabalhe numa pasta gravável (ex.: a pasta de
trabalho atual) com a estrutura `audit_data/` e `outputs/`. Rode Python com `python3`.

Referências (leia quando a etapa pedir, não tudo de uma vez):
- `references/rubric.json`: os 53 checks, pesos e níveis de evidência
- `references/evidence-2026.md`: o que a pesquisa mostra e os mitos a evitar
- `references/manual-checks.md`: critérios para os checks que você avalia lendo as páginas
- `references/data-sources.md`: dados externos com e sem Semrush, PageSpeed, painel de prompts, presença externa
- `references/report-schema.md`: formato do `report.json` e como priorizar

---

## Etapa 0: Briefing (uma rodada de perguntas, no máximo)

Antes de coletar, descubra silenciosamente quais ferramentas existem na sessão (conector Semrush, ferramentas
de AEO do HubSpot, Search Console, GA4, navegador Claude in Chrome ou navegador integrado, busca na web).
Depois faça **uma única rodada** de perguntas (use a ferramenta de perguntas de múltipla escolha se houver),
pulando o que o usuário já respondeu:

1. **Tipo de auditoria:** Rápida (~10 páginas, só dados do site, 5 a 10 min) ou Completa (até 60 páginas +
   módulos de dados, 20 a 40 min).
2. **Contexto do negócio:** o que vende, para quem (ICP), mercado/idioma e 2 ou 3 concorrentes. Ofereça a opção
   "descubra pelo site e me mostre para confirmar".
3. **Fontes de dados:** liste só as que estão disponíveis e pergunte quais usar. Ex.: "Semrush (consome unidades
   de API, qual o teto?)", "Search Console", "Painel de prompts no ChatGPT pelo seu navegador", "PageSpeed",
   "Busca de menções externas". **Nenhuma é obrigatória:** sem Semrush, rankings vêm do Search Console ou de
   amostra por busca na web. Se o usuário citar uma ferramenta que não está conectada, procure o conector no
   registro e sugira a conexão; continue sem ela se ele preferir.
   Pergunte também as **palavras-chave do ICP** (10 a 25) ou ofereça propor a partir do site.
4. **Objetivo e formato:** relatório completo (plano para o time ou cliente), diagnóstico de 1 página com CTA
   (prospecção, isca de topo de funil) ou os dois.

Se o usuário não estiver presente para responder, assuma: Rápida, contexto inferido do site, todas as fontes
disponíveis que não custam créditos, e diga no início do relatório o que foi assumido.

## Etapa 1: Coleta (HTML real, não resumo)

Nunca use resumo de página como base técnica: meta tags, canonical e JSON-LD somem em resumos.
Tente os caminhos nesta ordem:

**A. Coleta direta (preferida)**
```bash
python3 SKILL_DIR/scripts/crawl.py https://site.com.br --mode quick --out audit_data   # ou --mode full
```
Instale `beautifulsoup4` se faltar (`pip install beautifulsoup4 --break-system-packages`).
Saída `0` = ok. Saída `3` = a rede do ambiente bloqueia o domínio → vá para B. Saída `4` = a home respondeu
erro ou quase vazia (proxy do ambiente, firewall do site ou bloqueio de robôs) → vá para B e, se o bloqueio for do
site, registre como achado de acesso.

**B. Coleta pelo navegador** (Claude in Chrome ou navegador integrado; leia a skill do navegador antes, se houver)
1. Abra a home do site numa aba nova.
2. Execute o conteúdo de `scripts/browser_collect.js` com a ferramenta de JavaScript, com
   `CONFIG = {discover: true, urls: [], excerptWords: 600}`. Salve o texto retornado em
   `audit_data/browser/discover.json`.
3. `python3 SKILL_DIR/scripts/from_browser.py audit_data --select --mode quick` → devolve lotes de URLs.
4. Para cada lote, execute o JS de novo com `CONFIG = {discover: false, urls: [...lote...], excerptWords: 600}` e
   salve em `audit_data/browser/batch-1.json`, `batch-2.json`...
5. `python3 SKILL_DIR/scripts/from_browser.py audit_data --links-plan --mode quick` → lotes de links e da amostra
   do sitemap. Execute o JS com `CONFIG = {checkLinks: [...lote...], readBody: false}` para links
   (salve em `links-1.json`...) e `readBody: true` para o sitemap (salve em `sitemap-1.json`...).
   Recomendado; se pular, os checks de links ficam como "não avaliado".
6. `python3 SKILL_DIR/scripts/from_browser.py audit_data --build --mode quick`

O JS lê o HTML do servidor por `fetch` (o que os bots veem). Não testa user-agent de bots nem redirect HTTP:
esses checks ficam como "não avaliado" e devem ir para `limitations`.

**C. Sem rede e sem navegador:** avise o usuário que a parte técnica ficará limitada. Use a leitura de páginas
da web só para os checks manuais, marque os técnicos como `unknown` e recomende rodar de novo com navegador.

## Etapa 2: Checks automáticos

```bash
python3 SKILL_DIR/scripts/analyze.py audit_data/site.json
```
Gera `audit_data/findings.json` com ~35 checks calculados (incluindo links quebrados, redirecionamentos, saúde do
sitemap, hreflang e preço visível) e a lista `pending_for_claude`.
Confira rapidamente os achados `fail` contra `site.json` antes de seguir: se algo parecer falso positivo
(ex.: canonical para outra URL que é intencional), corrija com `set_check.py` e explique na evidência.

## Etapa 3: Checks manuais (leitura das páginas)

Leia `references/manual-checks.md` e os arquivos `audit_data/pages/*.txt` das páginas prioritárias.
Avalie cada check manual com evidência concreta e registre em lote:
```bash
python3 SKILL_DIR/scripts/set_check.py audit_data/findings.json --batch audit_data/manual.json
```

## Etapa 4: Módulos de dados (só os aprovados no briefing)

Siga `references/data-sources.md`. Cada módulo tem caminho com e sem Semrush:
- **Rankings e AI Overviews** → `audit_data/serp.csv`, preenchido pelo Semrush (respeitando o teto de unidades),
  pelo Search Console ou por amostra de busca na web. Depois:
  `python3 SKILL_DIR/scripts/data_metrics.py serp audit_data/serp.csv --domain site.com.br --findings audit_data/findings.json`
- **Painel de prompts** (8 a 15 prompts, **3+ rodadas por motor**) → `audit_data/prompts.csv`. Depois:
  `python3 SKILL_DIR/scripts/data_metrics.py prompts audit_data/prompts.csv --brand "Marca" --findings audit_data/findings.json`
  (`data_metrics.py template audit_data` cria as duas planilhas vazias.)
- **PageSpeed:** Core Web Vitals da home e de 1 ou 2 páginas comerciais.
- **Presença externa:** imprensa, Reddit/fóruns, YouTube, G2/Capterra/B2B Stack, Reclame Aqui,
  Wikipedia/Wikidata, listas de terceiros.

Registre o que não passa pelas planilhas com `set_check.py --source semrush|pagespeed|websearch|gsc|user`.

## Etapa 5: Notas

```bash
python3 SKILL_DIR/scripts/score.py audit_data/findings.json
```
Notas 0-100 por dimensão (SEO, GEO, AEO e, com dados, VIS) e índice geral (SEO 35%, GEO 35%, AEO 30%).
A **confiança** mostra quanto do peso foi avaliado. Se algum check manual ficou pendente, resolva antes de seguir.
Não ajuste notas na mão: mude o status do check com evidência.

## Etapa 6: Narrativa e relatório

1. Escreva `audit_data/report.json` seguindo `references/report-schema.md` (prioridades pela visão de growth,
   recomendações específicas, plano 30/60/90, visibilidade medida, limitações).
2. Gere os arquivos:
```bash
python3 SKILL_DIR/scripts/build_report.py audit_data/findings.json audit_data/report.json --out outputs --format full
```
   `--format full` (relatório completo, com gráfico por pilar), `onepager` (diagnóstico de 1 página com CTA da
   marca) ou `both`. Gera `.docx` e, se o LibreOffice existir, `.pdf`. A seção de visibilidade usa
   `audit_data/visibility.json` automaticamente. O relatório completo usa `assets/brand.json` (Carratu Digital);
   o diagnóstico de 1 página usa a identidade apontada em `onepager_brand` (padrão: `assets/brand-consultoria.json`,
   tema escuro da Carratu revenue growth consulting, com o rodapé "Este skill foi produzido pela Carratu Digital").
   Para outra marca: `--brand` e `--onepager-brand` com arquivos no mesmo formato. As fontes da marca
   (`assets/fonts`, licença OFL) são instaladas automaticamente antes de gerar o PDF.
3. Entregue os dois arquivos ao usuário com a ferramenta de envio de arquivos da sessão.

## Etapa 7: Resumo no chat (curto)

```
**[Empresa]: auditoria [rápida/completa] SEO · GEO · AEO** · [n] páginas · [data]

| Dimensão | Nota | Confiança |
|---|---|---|
| Índice geral | XX/100 | |
| SEO | XX | XX% |
| GEO | XX | XX% |
| AEO | XX | XX% |
| Visibilidade medida | XX ou "sem dados" | |

**3 prioridades:** (uma frase cada, específica)
**Maior força:** (uma frase)
```
Depois ofereça um próximo passo real: aprofundar uma dimensão, comparar com um concorrente, gerar briefs das
páginas comparativas, ou agendar o painel de prompts mensalmente para acompanhar a evolução.

---

## Princípios inegociáveis

- **Olhe antes de afirmar.** Só diga que algo falta depois de checar o site inteiro coletado (e o sitemap).
- **Evidência acima de moda.** Use os níveis S/C/A. Não recomende llms.txt, schema FAQ para rich result
  (encerrado em mai/2026) ou schema como alavanca de citação em IA. Explique a evidência se o cliente perguntar.
- **Bloqueio de acesso é crítico.** Bot de busca de IA bloqueado (robots.txt, WAF/Cloudflare), noindex ou
  conteúdo só em JavaScript vêm antes de qualquer melhoria de conteúdo.
- **Bloquear treino ≠ bloquear busca.** GPTBot/ClaudeBot/Google-Extended são treino; OAI-SearchBot,
  Claude-SearchBot, PerplexityBot, Bingbot, Applebot e Googlebot são busca. Trate a política de treino como
  decisão de negócio, não como erro.
- **Seja honesto sobre limites.** Core Web Vitals, backlinks, rankings e visibilidade em IA exigem dados
  externos. Sem eles, diga o que faltou e como medir, e deixe a confiança baixa aparecer.
- **Específico, nunca genérico.** Toda recomendação cita página, número ou trecho do site auditado.
- **Visão de negócio.** Priorize páginas que geram receita e o ICP do cliente. Contexto brasileiro: o ChatGPT
  concentra quase todo o tráfego de IA generativa no Brasil; Reclame Aqui e B2B Stack contam como presença.
- **Campo que muda rápido.** Se a data atual estiver mais de 6 meses depois da revisão de
  `evidence-2026.md`, confirme por busca os itens marcados com ⚠ antes de afirmá-los.
