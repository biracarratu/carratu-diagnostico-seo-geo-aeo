# Critérios para os checks manuais

Leia os arquivos `pages/*.txt` (texto principal de cada página) e use os sinais de `site.json`
(`first_paragraph`, `headings`, `answer_after_question`, `numbers_in_text`, `external_domains`, `word_count`).
Priorize as páginas que geram receita: home, produto/serviço, preços, comparações, cases, e os 3 artigos mais
importantes. Toda avaliação precisa de evidência concreta: cite a página e um trecho curto ou um número.

Escala: **pass** = padrão atendido na maioria das páginas prioritárias · **warn** = parcial ou inconsistente ·
**fail** = ausente ou contrário ao padrão · **na** = não se aplica ao negócio · **unknown** = não deu para avaliar.

## SEO

**seo.search_intent** — Cada página prioritária atende uma intenção clara do ICP?
- pass: home diz o que é, para quem e o resultado; páginas de produto respondem "serve para mim?"; há conteúdo
  para consultas comparativas e de problema.
- warn: intenção certa, mas falta etapa do funil (ex.: só topo de funil no blog, nada de comparação).
- fail: páginas genéricas ("soluções inovadoras") que não casam com nenhuma consulta real.

## GEO

**geo.answer_first** — As primeiras 1 ou 2 frases respondem a pergunta principal da página?
- Olhe `first_paragraph` e o início do texto. Na home: "X é um [categoria] para [público] que [resultado]".
- pass: 70%+ das páginas prioritárias abrem com resposta/definição · warn: 30 a 69% · fail: abrem com slogan,
  história ou contexto.

**geo.passages** — As seções são autocontidas e respondem uma subpergunta cada (referência ~120 a 180 palavras)?
- pass: H2/H3 descritivos, seções que fazem sentido isoladas · warn: seções muito curtas (<50 palavras) ou
  blocos enormes sem subtítulos · fail: texto corrido sem estrutura ou conteúdo em abas/accordions fechados.
- Lembre: o Google diz que não é preciso escrever em "chunks". Trate como clareza, não como truque.

**geo.evidence_density** — Há números concretos com fonte, citações nomeadas, links para fontes confiáveis?
- Use `numbers_in_text` e `external_domains` como apoio, mas leia o texto (número de telefone não é dado).
- pass: artigos com vários dados sourced e páginas comerciais com resultados mensuráveis (cases com números) ·
  warn: dados esparsos ou sem fonte · fail: só afirmações vagas.

**geo.entity_specificity** — O texto nomeia coisas (marca, produto, categoria, integrações, clientes, cidades,
pessoas) ou fala em abstrações?
- pass: entidades claras e consistentes (mesmo nome da marca/produto em todo o site) · warn: mistura ·
  fail: linguagem genérica que serviria para qualquer concorrente.

**geo.information_gain** — Há algo que só este site tem? Pesquisa própria, benchmark, dados de clientes,
metodologia, opinião assinada por especialista.
- pass: pelo menos um ativo original relevante ao ICP · warn: originalidade pontual · fail: conteúdo que repete
  o top 10.

**geo.comparison_assets** — Existem páginas "X vs Y", "alternativas a", "melhores [categoria]" ou guias de
escolha, atualizados no último ano? Use `url_inventory_by_type` (tipo `comparison`) e o sitemap.
- pass: cobre as principais comparações do ICP com honestidade · warn: existe, mas desatualizado ou raso ·
  fail: não existe. Se a única lista é "melhores X" com a própria marca em 1º, marque warn e explique o risco.

## AEO

**aeo.question_coverage** — O site responde as perguntas reais do público?
- Fontes: People Also Ask (busca na web), perguntas de vendas e suporte informadas pelo usuário, Semrush
  (palavras com intenção informacional), subconsultas de fan-out ("o que é", "quanto custa", "como implementar",
  "vale a pena", "X ou Y").
- pass: maioria das perguntas relevantes tem seção própria · warn: metade · fail: quase nenhuma.

**aeo.visible_content** — Respostas-chave (preços, planos, recursos, FAQ) estão em HTML visível?
- Sinais de alerta: preços só em imagem/PDF, FAQ em accordion carregado por JS, página com `likely_client_rendered`.
- pass / warn / fail conforme a proporção de respostas-chave escondidas.

**aeo.local_nap** — Só se o negócio depende de busca local (clínica, loja, escritório que atende presencialmente).
Caso contrário, `na`. Verifique nome, endereço e telefone iguais no site, no schema LocalBusiness e no Google
Business Profile.

## Como registrar

Monte um `checks.json` e aplique de uma vez:

```json
[
  {"id": "geo.answer_first", "status": "warn", "evidence": "Home abre com 'Transformando o futuro'; só /produto diz o que é na 1ª frase.", "pages": ["https://site.com/"]},
  {"id": "geo.comparison_assets", "status": "fail", "evidence": "Nenhuma página de comparação no sitemap (0 de 214 URLs)."}
]
```

`python3 scripts/set_check.py audit_data/findings.json --batch checks.json`
