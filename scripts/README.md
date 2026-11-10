# Estatísticas locais

Requisitos: Python 3.9+ e GitHub CLI (`gh`) autenticado com leitura dos
repositórios desejados e `fonttools` (`python3 -m pip install fonttools`).
Sem serviço de cards. A fonte Montserrat e sua licença OFL estão em `assets/fonts`.

```sh
python3 scripts/generate_stats.py
```

O script usa apenas a API oficial do GitHub. Publica oito SVGs em
`assets/stats`, com versões claras e escuras para desktop e celular. Os textos são convertidos
em vetores, preservando Montserrat sem downloads externos durante a exibição. Para atualizar o perfil, execute
novamente e faça commit dos SVGs junto ao README.

- Linguagens: percentual do volume de código (bytes informados pelo GitHub) de
  todas as linguagens nos repositórios próprios acessíveis, públicos e privados.
  Exclui forks e repos sem linguagem. Linguagens auxiliares de build, shell,
  marcação ou configuração (como CMake, Makefile, Dockerfile, Shell, PowerShell,
  TeX, Tcl, Rich Text Format, GDB, LLVM, etc.) são agrupadas em “Outras”.
  Isso representa o código dos repositórios, não apenas o código de sua autoria.
- Atividade: calendário oficial de contribuições dos últimos 365 dias, agregado
  por mês, com métricas consistentes do próprio calendário (dias ativos, média
  mensal e pico mensal), incluindo contribuições públicas e privadas. Os meses
  inicial e final são parciais; as datas do intervalo aparecem no gráfico.
- A seleção de linguagens considera repositórios próprios. A atividade segue
  o calendário do perfil e pode incluir contribuições em outros repositórios.
- A inclusão de atividade privada depende do acesso do token e das configurações
  de contribuição do perfil. Dados que a API não disponibiliza não são contados.

Nomes de repositórios, hashes, datas individuais e respostas da API ficam só
em memória. Os SVGs contêm linguagens, porcentagens e totais mensais de contribuições.
Esses agregados passam a ser públicos quando as imagens forem publicadas.
Credenciais são gerenciadas pelo `gh`; não coloque tokens neste repositório.

Não há atualização automática configurada.
