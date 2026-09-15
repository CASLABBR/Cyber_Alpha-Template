# Cyber Alpha Template

Template de repositório com compilação automática via GitHub Actions.

## Workflows incluídos

- **Android**: detecta `gradlew` na raiz ou em `android/`, gera APK de release e publica artifact.
- **Windows .NET**: detecta o primeiro projeto `.csproj`, publica um executável `win-x64` autocontido e salva como artifact.
- **Windows Python**: detecta `main.py`, `app.py` ou `run.py`, instala dependências e gera EXE com PyInstaller.

Os workflows rodam em pushes para `main` ou `master` e também podem ser iniciados manualmente em **Actions**. Quando o tipo de projeto não existe, o workflow termina sem tentar compilar.
