# CIAP-PB — Página institucional

Página web responsiva inspirada nas referências visuais fornecidas do Canva para a Central Integrada de Alternativas Penais da Paraíba.

## Como executar

É necessário ter Python 3.9 ou superior instalado.

### Opção 1: uso direto

```bash
python app.py
```

### Opção 2: usar o script de startup

No Windows, pode iniciar com:

```powershell
./start.ps1
```

Ou em CMD:

```bat
start.bat
```

Para usar outra porta:

```powershell
./start.ps1 -Port 8001
```

Depois, abra no navegador:

```text
http://localhost:8000
```

> O script verifica se a porta já está em uso e impede que uma segunda instância do projeto abra sobre a primeira.

## Estrutura

- `app.py`: servidor local em Python, sem dependências externas.
- `index.html`: conteúdo e estrutura editável da página.
- `styles.css`: identidade visual, componentes e responsividade.

O projeto usa apenas HTML, CSS e a biblioteca padrão do Python, facilitando a publicação em qualquer hospedagem estática ou servidor simples.
