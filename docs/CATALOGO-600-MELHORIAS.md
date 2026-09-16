# Catálogo verificável — 600 melhorias

O catálogo oficial do AutoPack v4 é produzido por `autopack/catalog.py`. Ele contém exatamente 600 requisitos estáveis: 60 domínios de capacidade × dez controles de entrega. Os IDs `AP-001` a `AP-600` são únicos, contíguos e não podem ser reutilizados.

Cada registro possui:

- `id`, `epic` e `control`;
- requisito concreto e critério de aceitação automatizável;
- estado honesto;
- referências separadas de código, testes e execuções reais;
- dependências anteriores.

## Estados

| Estado | Significado |
|---|---|
| `planned` | Requisito definido, ainda sem implementação comprovada. |
| `implemented` | Código e teste existem em `code_refs` e `test_refs`. |
| `verified` | Além da implementação, `evidence_urls` contém uma execução imutável do GitHub Actions. |
| `external-blocked` | O adaptador está pronto, mas a ativação depende de certificado, credencial, conta, hardware ou decisão externa documentada. |
| `not-applicable` | Decisão arquitetural registrada com justificativa verificável. |

O baseline promove apenas controles diretamente sustentados pelo motor, CI e testes atuais. Detecção/plano seguro, extensão Chromium, bundles MCP, detecção de plugin, reprodutibilidade e pinagem por SHA possuem promoções estreitas para `implemented`. Nenhum item está `verified` sem URL de execução associada ao requisito exato. Itens que exigem keystore, identidade de assinatura, conta de loja/gerenciador, tenant corporativo ou hardware físico aparecem como `external-blocked` e nomeiam o requisito externo.

## Validação e exportação

```bash
python autopack-v4/autopack/catalog.py --check
python autopack-v4/autopack/catalog.py --output catalog-600.json
python -m unittest autopack-v4/tests/test_catalog.py -v
```

O JSON exportado é a matriz detalhada completa para CI, issues, dashboards e auditoria. O validador rejeita quantidade diferente de 600, IDs duplicados ou fora de ordem, dependências futuras, requisitos sem aceite e alegações de implementação/verificação sem evidência.

## Estrutura dos IDs

- Cada faixa de dez IDs pertence a um domínio na ordem declarada em `EPICS`.
- Dentro da faixa, os controles são: detectar, planejar, configurar, executar, empacotar, verificar, proteger, diagnosticar, recuperar e documentar.
- Exemplo: `AP-001` detecta linguagens, manifestos e entry points; `AP-002` os representa no plano; `AP-010` documenta limites e evidências.
- `AP-591` a `AP-600` aplicam os mesmos controles a SIEM, políticas, APIs seguras e analytics.

## Regra de promoção

Nenhum item é considerado concluído por associação com um épico ou por uma afirmação na documentação. Promoções exigem alteração explícita do registro e devem satisfazer o validador. Para `verified`, a evidência deve incluir uma execução real; dependências externas permanecem visíveis como `external-blocked`, nunca como sucesso artificial.
