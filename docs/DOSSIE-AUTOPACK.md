# Dossiê técnico — AutoPack

## Objetivo

Transformar repositórios públicos em entregas utilizáveis por meio de detecção conservadora, plano reproduzível, adaptadores isolados e artefatos verificáveis. O sistema não executa comandos copiados livremente de README; manifestos e convenções conhecidas são as fontes principais.

## Evolução realizada

- v1/v2: workflows independentes para Android, Python e .NET.
- v3: motor unificado, plano JSON, versão `AAAA.MM.DD.RUN`, Python/yt-dlp, .NET, Android, Docker/Compose, Node, site estático e PWA.
- v4: base versionada separadamente, seleção múltipla, HTA e Tauri para Windows.

## Arquitetura

1. O job `plan` clona a origem sem credenciais persistentes.
2. `engine.py` enumera arquivos ignorando árvores geradas e links simbólicos.
3. Evidências recebem pontuações determinísticas.
4. Caminhos e metadados são sanitizados antes de virarem outputs.
5. Somente o adaptador compatível é executado.
6. Empacotadores geram launchers, manifesto/hashes e arquivo transportável.
7. Smoke tests precedem o upload sempre que o formato permite.

## Comandos principais

```powershell
python -m unittest discover -s tests -v
python autopack-v4/engine.py source --type auto --repository https://github.com/dono/repo --output autopack-plan.json
```

```bash
bash autopack-v4/collect-android.sh source artifacts Produto 2026.09.15.1
bash autopack-v4/package-docker.sh source artifacts Produto 2026.09.15.1
bash autopack-v4/package-node.sh source artifacts Produto 2026.09.15.1
bash autopack-v4/package-static.sh source artifacts Produto 2026.09.15.1
```

```powershell
./autopack-v4/package-windows.ps1 -SourceDirectory dist -OutputDirectory artifacts -Product Produto -Version 2026.09.15.1
./autopack-v4/package-hta.ps1 -SourceDirectory site -OutputDirectory artifacts -Product Produto -Version 2026.09.15.1
```

## Resultados reais validados

- yt-dlp: EXE/portátil Windows, 37 MB, execução v3 nº 6.
- site HTML do MDN: pacote estático, execução v3 nº 7.
- aplicação Node da Heroku: pacote com dependências, execução v3 nº 8.
- minimal-pwa-setup: pacote PWA offline, execução v3 nº 9.
- HTML do MDN: pacote HTA e plano, execução v4 nº 1.
- Uninen/tauri-vue-template: EXE, MSI e instalador NSIS, execução v4 nº 7.

## Segurança e limites

- Origem limitada a repositório público `github.com/dono/repo` e 2 GB.
- Actions críticas são fixadas por SHA; token do workflow é somente leitura.
- Caminhos absolutos, travessia `..`, tipos desconhecidos e artefatos vazios são recusados.
- HTA usa o motor legado do Windows e não substitui Tauri/PWA para sites modernos.
- Tauri executa o build oficial do projeto em runner descartável; assinatura de produção exige certificado em Secrets.
- MSI/MSIX/APK/AAB sem certificado são builds de teste, nunca anunciados como publicação assinada.

## Revisão independente por IAs (2026-09-15)

Consultas independentes a Claude, DeepSeek, Grok, Gemini, Perplexity e Poe foram usadas como revisão, não como evidência de conclusão. As recomendações coincidentes, incorporadas ao backlog rastreável, foram:

- separar build não confiável de assinatura/publicação; certificados, keystores e contas de loja nunca entram em jobs de PR;
- fixar Actions por SHA completo, manter permissões globais `contents: read` e considerar conteúdo de cache como não confiável;
- gerar SBOM e provenance/attestations apenas em uma etapa de release com `id-token: write` e `attestations: write`, sob ambiente protegido;
- testar instalação, atualização, execução e desinstalação em ambiente limpo, além de validar apenas o build;
- registrar matriz de compatibilidade, orçamento de tamanho, toolchain/lockfile e reprodutibilidade explícita;
- usar upgrade code estável para MSI/MSIX, componentes opcionais em Inno Setup, metadados PE, versionCode Android crescente e verificação `apksigner` quando houver keystore;
- expandir fixtures adversariais: monorepos, lockfiles conflitantes, paths Unicode, manifestos ambíguos, timeout, cache contaminado, compose offline e launchers idempotentes.

Itens que exigem identidade de assinatura, GitHub Environment protegido, conta Microsoft/Google/Apple, HSM, loja ou hardware continuam `external-blocked` no catálogo até possuírem evidência real.

## Próximas validações

Validar Android e Docker/Compose em projetos reais; depois MSIX genérico, lotes e pacotes combinados. O MSI genérico x64 já é produzido pela CLI WiX dentro dos jobs Python e .NET, junto ao ZIP portátil. Certificados, publicação em lojas e assinaturas oficiais permanecem dependentes de credenciais externas.
