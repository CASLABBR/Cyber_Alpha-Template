# Catálogo mestre — 600 melhorias

Este catálogo normaliza o contexto funcional em 60 épicos, cada um contendo dez melhorias rastreáveis. Os IDs preservam um backlog total de 600 itens sem copiar a conversa bruta. Cada épico deve ser detalhado em issues antes da implementação.

| IDs | Épico |
|---|---|
| 001–010 | Detecção de linguagens, manifestos e entry points |
| 011–020 | Confiança, evidências e plano reproduzível |
| 021–030 | Python, CLI, GUI e ambientes virtuais |
| 031–040 | .NET, desktop, serviços e publicação autocontida |
| 041–050 | Android, Gradle, APK, AAB e assinaturas |
| 051–060 | Node, npm, pnpm, Yarn e aplicações desktop |
| 061–070 | Sites estáticos, SPA e servidores locais |
| 071–080 | PWA, offline, service worker e TWA |
| 081–090 | Docker, Compose, OCI e ambientes com GPU |
| 091–100 | EXE, portable, launchers e argumentos CLI |
| 101–110 | MSI, MSIX, Inno Setup e componentes opcionais |
| 111–120 | Atualizações, canais, rollback e reparo |
| 121–130 | Metadados, SemVer, ícones e branding |
| 131–140 | Hashes, assinaturas, SBOM e proveniência |
| 141–150 | ISO, mídia offline e catálogo HTML |
| 151–160 | Seleção múltipla e matriz de formatos |
| 161–170 | Filas, lotes, CSV e limites de concorrência |
| 171–180 | Monorepos, workspaces e grafos de dependência |
| 181–190 | Frontend, backend, banco e launcher conjunto |
| 191–200 | Healthchecks, portas, logs e painel local |
| 201–210 | Chrome Extensions Manifest V2/V3 |
| 211–220 | MCP, handshake, ferramentas e configurações |
| 221–230 | Plugins, skills, recursos e instalação isolada |
| 231–240 | GitHub Releases, Pages e lojas de aplicativos |
| 241–250 | WinGet, Chocolatey, Scoop e App Installer |
| 251–260 | Testes unitários, integração e smoke tests |
| 261–270 | Instalação, atualização, reparo e desinstalação |
| 271–280 | Cache, lockfiles, toolchains e mirrors |
| 281–290 | Timeouts, recursos, custos e filas grandes |
| 291–300 | Segurança de secrets, licenças e vulnerabilidades |
| 301–310 | Isolamento, containers e runners descartáveis |
| 311–320 | Relatórios, diagnósticos e erros classificados |
| 321–330 | Observabilidade, métricas e tendências |
| 331–340 | API, webhooks, callbacks e idempotência |
| 341–350 | Interface drag-and-drop e perfis salvos |
| 351–360 | Receipts, tutoriais e documentação offline |
| 361–370 | macOS, DMG, PKG e binário universal |
| 371–380 | Linux, AppImage, DEB, RPM e Flatpak |
| 381–390 | Rust, Go, Java e Kotlin multiplataforma |
| 391–400 | PHP, Ruby, Swift e ecossistemas adicionais |
| 401–410 | HTA, WebView, Electron e Tauri |
| 411–420 | Migração de legado e runtimes descontinuados |
| 421–430 | Compatibilidade de dados e configurações |
| 431–440 | Acessibilidade WCAG, teclado e contraste |
| 441–450 | Tradução, RTL, formatos locais e fusos |
| 451–460 | Governança, RBAC e dupla aprovação |
| 461–470 | Privacidade, retenção e residência de dados |
| 471–480 | Multi-tenant, cotas e isolamento de caches |
| 481–490 | Builds determinísticos e comparação independente |
| 491–500 | Chaos testing, falhas de rede e recuperação |
| 501–510 | IA de planejamento e grafo causal |
| 511–520 | Erlang, Haskell, OCaml, Julia, R, Nim, Zig e WASI |
| 521–530 | Arduino, ESP, Zephyr, UF2 e firmware |
| 531–540 | Auditorias avançadas de acessibilidade e localização |
| 541–550 | Modernização, contratos e compatibilidade futura |
| 551–560 | Fuzzing, propriedades e regressão semântica |
| 561–570 | Intune, GPO, MST, Server Core e serviços Windows |
| 571–580 | Air-gap, USB, volumes e transferência verificada |
| 581–590 | Drivers, DPAPI, bancos locais e backups |
| 591–600 | SIEM, políticas, API segura e analytics |

## Regra de promoção

Uma ideia passa de catálogo para recurso somente quando possui: detector, adaptador, política de segurança, teste automatizado, teste real, documentação e estratégia de falha/rollback.
