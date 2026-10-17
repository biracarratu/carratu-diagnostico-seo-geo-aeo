# report.json: narrativa do relatório

`build_report.py` junta `findings.json` (checks e notas) com `report.json` (o que o Claude escreve).
Todos os campos são opcionais, exceto `executive_summary`, `top_priorities` e `recommendations`.

```json
{
  "client_name": "Nome da empresa (aparece na capa; sem isso usa o domínio)",
  "date": "2026-10-17",
  "executive_summary": "3 a 5 frases. Use **negrito** para o achado principal. Parágrafos separados por linha em branco (\\n\\n).",
  "dimension_takeaways": {"SEO": "1 linha", "GEO": "1 linha", "AEO": "1 linha", "VIS": "1 linha"},
  "dimension_narratives": {"GEO": "Parágrafo opcional antes da tabela da dimensão."},
  "top_priorities": ["Prioridade 1 específica", "Prioridade 2", "Prioridade 3"],
  "biggest_strength": "1 frase com evidência",
  "context": {
    "business": "O que a empresa vende",
    "icp": "Para quem",
    "market": "País/idioma",
    "goal": "Objetivo declarado da auditoria",
    "competitors": ["Concorrente A", "Concorrente B"]
  },
  "data_sources": ["Coleta direta do HTML", "Semrush (base BR)", "Painel de 12 prompts x 3 rodadas no ChatGPT"],
  "recommendations": [
    {
      "priority": "Crítica | Alta | Média | Ganho rápido",
      "issue": "O que fazer, no imperativo",
      "how": "Como fazer, 1 a 2 frases (opcional)",
      "dimension": "SEO | GEO | AEO | VIS",
      "effort": "Baixo | Médio | Alto",
      "impact": "Baixo | Médio | Alto",
      "owner": "Dev | Conteúdo | Marketing | PR | Produto"
    }
  ],
  "action_plan": {"30": ["..."], "60": ["..."], "90": ["..."]},
  "visibility": {
    "summary": "Leitura dos dados medidos",
    "ai_method": "Como o painel foi rodado",
    "ai_prompts": [
      {"prompt": "melhor CRM para PME", "engine": "ChatGPT", "runs": 3, "mentioned": "1/3", "cited": "0/3", "competitors": ["A", "B"]}
    ],
    "semrush": {
      "highlights": ["Bullet com número e leitura"],
      "table": {"header": ["Palavra-chave", "Posição", "AI Overview cita a marca?"], "rows": [["...", "4", "Não"]]}
    },
    "extra_tables": [{"title": "Fontes mais citadas nas respostas", "header": ["Fonte", "Vezes"], "rows": [["g2.com", "7"]]}]
  },
  "strengths": [{"title": "Força", "evidence": "Evidência observada"}],
  "limitations": ["O que não foi possível medir e como medir na próxima rodada"],
  "include_glossary": false,
  "cta_title": "Opcional: sobrescreve o CTA de assets/brand.json no diagnóstico de 1 página",
  "cta_text": "Opcional"
}
```

Se `visibility` não vier no `report.json`, o relatório usa `audit_data/visibility.json` gerado por
`data_metrics.py`. Escreva `visibility.summary` à mão só se quiser uma leitura diferente da automática.

## Como priorizar (visão de growth)

1. **Bloqueios de acesso primeiro:** robots/WAF bloqueando bots de busca, noindex, conteúdo só em JavaScript.
   Sem isso, nada mais importa. Prioridade Crítica.
2. **Páginas que geram receita antes de blog:** home, produto, preços, comparações, cases. Um problema numa
   página de preço vale mais que o mesmo problema num artigo antigo.
3. **Impacto ÷ esforço:** ganhos rápidos (baixo esforço, impacto médio/alto) entram no plano de 30 dias.
4. **Presença fora do site** costuma ser o maior gargalo de GEO e o mais lento: comece no plano de 60/90 dias.
5. Não recomende itens marcados como mito em `evidence-2026.md` (llms.txt, FAQ schema para rich result, schema
   como alavanca de citação). Se o cliente pedir, explique a evidência.
6. Entre 6 e 15 recomendações. Cada uma específica ao site (página, número, trecho), nunca genérica.

## Estilo de escrita (padrão Carratu)

- Português do Brasil, direto, frases curtas. Comece pelo achado, depois a explicação.
- Sem travessão (—). Use vírgula, dois-pontos, ponto ou parênteses.
- Números concretos e páginas nomeadas. Evite "otimizar", "alavancar" e jargão vazio.
- Tom calibrado: se o site está bom, diga. Se há risco grave, diga com clareza, sem alarmismo.
- Se o usuário pedir outro idioma, escreva `report.json` nesse idioma (os rótulos fixos do relatório continuam em
  português; avise o usuário).
