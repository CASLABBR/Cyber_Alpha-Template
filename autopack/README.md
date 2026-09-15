# AutoPack v3 Ultimate

AutoPack analisa um repositório público, cria um plano reproduzível e encaminha o projeto para um adaptador de build. A detecção é conservadora: manifestos e arquivos-padrão são aceitos como evidência; comandos livres encontrados em README não são executados.

## Princípios

- segurança antes de automação cega;
- metadados e versão crescente em toda entrega;
- saídas somente quando forem compatíveis com o projeto;
- pacote portátil antes do instalador;
- teste do resultado antes da publicação;
- relatório que explica detecção, decisões e falhas.

## Versão

O formato inicial é `AAAA.MM.DD.BUILD`. Projetos que já tenham SemVer poderão preservá-lo em adaptadores especializados e acrescentar `+build.N`.

## Estado

Esta é a fundação do v3. O workflow legado permanece disponível durante a validação. Os adaptadores serão promovidos para produção apenas depois de smoke tests reais.

## Empacotadores disponíveis

- `package-windows.ps1`: cria ZIP portátil, manifesto, hashes e iniciador adequado para CLI ou aplicação web. O conteúdo publicado/autocontido deve ser passado como origem; ele não instala dependências no computador do usuário.
- `collect-android.sh`: coleta APKs e AABs produzidos pelo Gradle, aplica nomes contendo produto/versão/variante e gera SHA-256.
- `package-docker.sh`: valida Compose ou constrói uma imagem OCI, exporta pacote offline compactado e cria iniciadores simples para Docker Desktop.

Os scripts recusam saídas vazias. MSI/MSIX e APK/AAB assinados só devem ser anunciados quando o job possuir certificado/keystore em GitHub Secrets; sem credenciais, a saída é de teste ou portátil. A leitura de README serve para relatório e sugestão, nunca para executar comandos arbitrários.

